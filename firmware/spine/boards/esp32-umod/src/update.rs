//! `wifi-update`: a new firmware over WiFi, the Rust twin of the 2025-26 C++'s `/update`
//! page. **Off by default, never in the car-day build, never flashed yet.**
//!
//! The C++ took any upload from anyone on the WiFi. This one writes an upload only when
//! every check passes (`app-update`'s rules), and restarts into it only once it is written
//! whole and read back the same:
//!
//! | Step | Check | Refused with |
//! |---|---|---|
//! | 1 | the `X-Update-Password` header is the build's `UPDATE_PASSWORD` (`src/wifi_secrets.rs`, git ignores it); 10 s lockout after a wrong one | 403 |
//! | 2 | the car parked: stopped, not armed, no throttle, the brake full on; checked again at every 4 KB | 409 |
//! | 3 | the board has two app slots (`partitions-ota.csv`, flashed over USB once) | 409 |
//! | 4 | an ESP32 app image of this program (`spine-esp32-umod`), with its SHA-256, small enough for the slot; checked as it comes, before the first write | 400, 413 |
//! | 5 | written to the slot not running, 4 KB at a time, the tick running between | 500 |
//! | 6 | read back: the same CRC-32 as what came, and its SHA-256 right on flash | 500 |
//! | 7 | the car still parked: only then is the slot made the one to boot | 409 |
//! | 8 | the reply goes out; 1 s later the tick restarts the chip, if the car is still parked | - |
//!
//! Its own server on port 8080, one connection at a time, with a long read timeout for the
//! upload; port 80's pages keep their short ones. Send an image with:
//!
//! ```text
//! espflash save-image --chip esp32 <elf> app.bin
//! curl --data-binary @app.bin -H "X-Update-Password: <the password>" http://<board>:8080/update
//! ```
//!
//! The password crosses the WiFi in plain text (HTTP, no TLS): anyone who can listen on
//! that WiFi can learn it. The bench WiFi only (README.md).
//!
//! Each 4 KB erase holds the chip with its interrupts off for about 45 ms (up to 400 ms on
//! a slow flash chip): the tick waits that long, which is why the car must be parked. A
//! watchdog reset in the middle is safe: the slot written isn't the one to boot until
//! step 7.

use crate::wifi::secrets;
use app_update::{may_update, CarState, Expect, Guard, ImageCheck, ImageError, NotNow};
use core::cell::{Cell, RefCell};
use core::fmt::{self, Write as _};
use core::sync::atomic::{AtomicU32, Ordering};
use embassy_executor::Spawner;
use embassy_net::Stack;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::mutex::Mutex as AsyncMutex;
use embassy_time::{Duration, Timer};
use esp_bootloader_esp_idf::ota_updater::OtaUpdater;
use esp_bootloader_esp_idf::partitions::{self, PartitionType, PARTITION_TABLE_MAX_LEN};
use esp_storage::FlashStorage;
use log::{info, warn};
use picoserve::io::Read;
use picoserve::request::Request;
use picoserve::response::{Content, IntoResponse, ResponseWriter, StatusCode};
use picoserve::routing::MethodHandlerService;
use picoserve::ResponseSent;

/// The update's own port.
pub const PORT: u16 = 8080;
/// The example file's password: never taken.
const EXAMPLE_PASSWORD: &str = "example-update-password";
/// Bytes written at a time: one flash sector.
const CHUNK: usize = FlashStorage::SECTOR_SIZE as usize;
/// After each erase or write, the tick's turn.
const YIELD: Duration = Duration::from_millis(15);
/// From the reply to the restart: time for the reply to leave.
const RESTART_AFTER_MS: u32 = 1000;

/// The car as the latest tick left it; parked is never assumed.
static CAR: Mutex<CriticalSectionRawMutex, Cell<CarState>> = Mutex::new(Cell::new(CarState {
    stopped: false,
    armed: true,
    throttle: 0.0,
    brake: 0.0,
}));
/// The clock's ms at which the tick restarts the chip: 0 for never.
static RESTART_AT: AtomicU32 = AtomicU32::new(0);
/// The password's guard (its lockout).
static GUARD: Mutex<CriticalSectionRawMutex, RefCell<Guard<'static>>> = Mutex::new(RefCell::new(
    Guard::new(secrets::UPDATE_PASSWORD, EXAMPLE_PASSWORD),
));

/// From the tick: the car now.
pub fn set_car(state: CarState) {
    CAR.lock(|c| c.set(state));
}

/// From the tick: restart now? Only after an update was written, checked and made the
/// one to boot, 1 s after its reply, and only while the car is parked.
pub fn restart_due(now_ms: u32) -> bool {
    let at = RESTART_AT.load(Ordering::Relaxed);
    at != 0 && now_ms.wrapping_sub(at) < u32::MAX / 2 && may_update(&car()).is_ok()
}

fn car() -> CarState {
    CAR.lock(|c| c.get())
}

/// The update server, on `stack`, owning the flash.
pub fn start(spawner: Spawner, stack: Stack<'static>, flash: esp_hal::peripherals::FLASH<'static>) {
    match server(stack, FlashStorage::new(flash)) {
        Ok(task) => spawner.spawn(task),
        Err(e) => warn!("update: its task didn't start ({e:?})"),
    }
}

#[embassy_executor::task]
async fn server(stack: Stack<'static>, flash: FlashStorage<'static>) -> ! {
    // Long enough for a 2 MB image on a slow WiFi, with every erase.
    static CONFIG: picoserve::Config = picoserve::Config::new(picoserve::Timeouts {
        start_read_request: Duration::from_secs(5),
        persistent_start_read_request: Duration::from_secs(1),
        read_request: Duration::from_secs(300),
        write: Duration::from_secs(2),
    });
    let flash = AsyncMutex::new(flash);
    let app = picoserve::Router::new().route_service("/update", Upload { flash: &flash });
    stack.wait_config_up().await;
    let mut tcp_rx = [0; 1536];
    let mut tcp_tx = [0; 512];
    let mut http = [0; 1024];
    loop {
        picoserve::Server::new(&app, &CONFIG, &mut http)
            .listen_and_serve(99, stack, PORT, &mut tcp_rx, &mut tcp_tx)
            .await
            .into_never()
    }
}

/// `/update`: GET says how; POST takes an image.
struct Upload<'f> {
    flash: &'f AsyncMutex<CriticalSectionRawMutex, FlashStorage<'static>>,
}

impl MethodHandlerService for Upload<'_> {
    async fn call_method_handler_service<R: Read, W: ResponseWriter<Error = R::Error>>(
        &self,
        _state: &(),
        _path: (),
        method: &str,
        mut request: Request<'_, R>,
        response_writer: W,
    ) -> Result<ResponseSent, W::Error> {
        let (status, body) = match method {
            "POST" => {
                // One upload at a time.
                match self.flash.try_lock() {
                    Err(_) => (
                        StatusCode::CONFLICT,
                        Text::from("an update is already running\n"),
                    ),
                    Ok(mut flash) => match receive(&mut request, &mut flash).await {
                        Ok(body) => (StatusCode::OK, body),
                        Err((status, body)) => {
                            warn!("update: refused ({}): {}", status.as_u16(), body.as_str());
                            (status, body)
                        }
                    },
                }
            }
            "GET" => (StatusCode::OK, Text::from(HOW)),
            _ => (StatusCode::METHOD_NOT_ALLOWED, Text::from("GET or POST\n")),
        };
        (status, body)
            .write_to(request.body_connection.finalize().await?, response_writer)
            .await
    }
}

const HOW: &str = "POST an ESP32 app image of spine-esp32-umod (espflash save-image --chip esp32 <elf> app.bin):\n  curl --data-binary @app.bin -H \"X-Update-Password: ...\" http://<board>:8080/update\nOnly while the car is parked: stopped, not armed, no throttle, the brake full on.\n";

type Refused = (StatusCode, Text);

fn refused(status: StatusCode, args: fmt::Arguments<'_>) -> Refused {
    let mut t = Text::new();
    let _ = t.write_fmt(args);
    let _ = t.write_char('\n');
    (status, t)
}

fn not_now(n: NotNow) -> Refused {
    refused(
        StatusCode::CONFLICT,
        format_args!("not now: {}", n.reason()),
    )
}

fn bad_image(e: ImageError) -> Refused {
    let status = if matches!(e, ImageError::TooBig { .. }) {
        StatusCode::PAYLOAD_TOO_LARGE
    } else {
        StatusCode::BAD_REQUEST
    };
    refused(
        status,
        format_args!("not this program's ESP32 app image: {e:?}"),
    )
}

fn flash_error(what: &str, e: partitions::Error) -> Refused {
    refused(
        StatusCode::INTERNAL_SERVER_ERROR,
        format_args!("{what}: {e:?}; the running firmware stays"),
    )
}

/// Steps 1 to 7 (the module docs). The reply's body on success.
async fn receive<R: Read>(
    request: &mut Request<'_, R>,
    flash: &mut FlashStorage<'static>,
) -> Result<Text, Refused> {
    // 1. The password.
    let given = request
        .parts
        .headers()
        .get("x-update-password")
        .map_or(&[][..], |v| v.as_raw());
    GUARD
        .lock(|g| g.borrow_mut().check(given, crate::now_ms()))
        .map_err(|e| refused(StatusCode::FORBIDDEN, format_args!("{}", e.reason())))?;
    // 2. Parked.
    may_update(&car()).map_err(not_now)?;
    let len = request.body_connection.content_length();
    if len == 0 {
        return Err(refused(
            StatusCode::BAD_REQUEST,
            format_args!("no image: send it as the request's body"),
        ));
    }
    // 3. Two slots.
    let mut table = [0; PARTITION_TABLE_MAX_LEN];
    let (slot, info) = {
        let mut ota = OtaUpdater::new(flash, &mut table).map_err(|_| {
            refused(
                StatusCode::CONFLICT,
                format_args!(
                    "this board has no OTA slots: flash the wifi-update build once over USB with partitions-ota.csv (README.md)"
                ),
            )
        })?;
        let (mut region, slot) = ota
            .next_partition()
            .map_err(|e| flash_error("no slot to write", e))?;
        let slot_len = region.partition_size() as u32;
        if len > slot_len as usize {
            return Err(bad_image(ImageError::TooBig { slot_len }));
        }
        info!("update: {len} bytes into {slot:?}, the car parked");
        // 4 and 5: checked as it comes, written a sector at a time.
        let mut check = ImageCheck::new(Expect {
            project: env!("CARGO_PKG_NAME"),
            slot_len,
        });
        let mut reader = request.body_connection.body().reader();
        let mut chunk = [0u8; CHUNK];
        let mut written: u32 = 0;
        loop {
            let mut filled = 0;
            while filled < CHUNK {
                match reader.read(&mut chunk[filled..]).await {
                    Ok(0) => break,
                    Ok(n) => filled += n,
                    Err(_) => {
                        return Err(refused(
                            StatusCode::BAD_REQUEST,
                            format_args!(
                                "the upload broke off at {} bytes",
                                written as usize + filled
                            ),
                        ))
                    }
                }
            }
            if filled == 0 {
                break;
            }
            check.push(&chunk[..filled]).map_err(bad_image)?;
            if !check.ready_to_write() {
                return Err(bad_image(ImageError::NoAppDescriptor));
            }
            may_update(&car()).map_err(not_now)?;
            region
                .erase(written, written + CHUNK as u32)
                .map_err(|e| flash_error("erase", e))?;
            Timer::after(YIELD).await;
            region
                .write(written, &chunk[..filled])
                .map_err(|e| flash_error("write", e))?;
            Timer::after(YIELD).await;
            written += filled as u32;
        }
        let info = check.finish().map_err(bad_image)?;
        // 6. Read back.
        let mut crc = app_update::Crc32::new();
        let mut at = 0;
        while at < info.len {
            let n = (info.len - at).min(CHUNK as u32);
            region
                .read(at, &mut chunk[..n as usize])
                .map_err(|e| flash_error("read back", e))?;
            crc.push(&chunk[..n as usize]);
            at += n;
            Timer::after(Duration::from_millis(1)).await;
        }
        if crc.value() != info.crc32 {
            return Err(refused(
                StatusCode::INTERNAL_SERVER_ERROR,
                format_args!("the slot doesn't read back as written; the running firmware stays"),
            ));
        }
        (slot, info)
    };
    // 6. Its SHA-256, on flash.
    {
        let pt = partitions::read_partition_table(flash, &mut table)
            .map_err(|e| flash_error("partition table", e))?;
        let entry = pt
            .find_partition(PartitionType::App(slot))
            .map_err(|e| flash_error("partition table", e))?
            .ok_or_else(|| flash_error("the slot", partitions::Error::Invalid))?;
        entry
            .sha256(flash)
            .map_err(|e| flash_error("its SHA-256 on flash", e))?;
    }
    // 7. Still parked: make it the one to boot.
    may_update(&car()).map_err(not_now)?;
    {
        let mut ota = OtaUpdater::new(flash, &mut table).map_err(|e| flash_error("OTA data", e))?;
        let (_, next) = ota
            .next_partition()
            .map_err(|e| flash_error("OTA data", e))?;
        if next != slot {
            return Err(flash_error(
                "the slot changed",
                partitions::Error::InvalidState,
            ));
        }
        ota.activate_next_partition()
            .map_err(|e| flash_error("switching slots", e))?;
    }
    // 8. The tick restarts the chip, once the reply is out.
    RESTART_AT.store(
        crate::now_ms().wrapping_add(RESTART_AFTER_MS).max(1),
        Ordering::Relaxed,
    );
    warn!(
        "update: version {} ({} bytes) written and checked in {slot:?}; restarting in 1 s while parked",
        info.version_str(),
        info.len
    );
    let mut body = Text::new();
    let _ = writeln!(
        body,
        "written and checked: version {}, {} bytes, {slot:?}; restarting in 1 s while the car stays parked",
        info.version_str(),
        info.len
    );
    Ok(body)
}

/// A short text reply, built in place.
struct Text {
    buf: [u8; 256],
    len: usize,
}

impl Text {
    const fn new() -> Self {
        Text {
            buf: [0; 256],
            len: 0,
        }
    }

    fn as_str(&self) -> &str {
        core::str::from_utf8(&self.buf[..self.len]).unwrap_or("")
    }
}

impl From<&str> for Text {
    fn from(s: &str) -> Self {
        let mut t = Text::new();
        let _ = t.write_str(s);
        t
    }
}

impl fmt::Write for Text {
    /// Keeps what fits.
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for c in s.chars() {
            let mut utf8 = [0; 4];
            let bytes = c.encode_utf8(&mut utf8).as_bytes();
            let end = self.len + bytes.len();
            let Some(dest) = self.buf.get_mut(self.len..end) else {
                return Err(fmt::Error);
            };
            dest.copy_from_slice(bytes);
            self.len = end;
        }
        Ok(())
    }
}

impl Content for Text {
    fn content_type(&self) -> &'static str {
        "text/plain"
    }

    fn content_length(&self) -> usize {
        self.len
    }

    async fn write_content<W: picoserve::io::Write>(self, mut writer: W) -> Result<(), W::Error> {
        writer.write_all(&self.buf[..self.len]).await
    }
}
