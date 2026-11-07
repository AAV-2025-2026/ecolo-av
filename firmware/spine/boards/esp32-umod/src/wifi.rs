//! `wifi-status`: the board on a WiFi, read only. Off by default.
//!
//! | Path (port 80) | Gives |
//! |---|---|
//! | `/`, `/status` | `page.html`: graphs of steering, brake and throttle, from `/ws` (`/status` is the C++'s path for its page) |
//! | `/status.json` | the latest `status` line |
//! | `/health` | the latest `health` line: the Pi link's verdict, the age of its last frame, the counter moving, its counts, the devices, the faults, the uptime, the last reset, the build |
//! | `/config` | the latest `config` line: the build, its features and the numbers it runs with |
//! | `/scan` | starts an I2C scan if none is going (a few addresses a tick, only while stopped and not armed), and says what it has found so far, with the C++'s names for the car's four devices |
//! | `/ws` | a WebSocket: every status line (`firmware/status`), as text messages |
//! | `/log` | a WebSocket: the text log, line by line, as the cable has it (the C++'s port 81 log); nothing in a `json-log` build, whose text lines are off |
//!
//! **Read only.** No path takes a command, a setting or an update, and nothing here can
//! reach the spine's inputs: the tick hands lines out ([`publish`]) and reads one flag
//! ([`take_scan_request`]). What a WebSocket client sends is read and thrown away.
//!
//! **The tick never waits on the WiFi.** These tasks share the main executor with the tick;
//! each runs only between the tick's awaits, and every hand-off is a critical section of a
//! few microseconds: [`publish`] drops the oldest line for a slow reader rather than wait.
//! The radio's own work runs in esp-rtos's threads and interrupts, which can still delay a
//! tick: the timing test in README.md measures that.
//!
//! The WiFi's name and password come from `src/wifi_secrets.rs`, which git ignores; they
//! are never logged or served.

use core::cell::RefCell;
use core::fmt::{self, Write as _};
use core::sync::atomic::{AtomicBool, Ordering};
use embassy_executor::Spawner;
use embassy_net::{Runner, Stack, StackResources};
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::pubsub::{PubSubChannel, WaitResult};
use embassy_time::{Duration, Timer};
use esp_radio::wifi::sta::StationConfig;
use esp_radio::wifi::{
    AuthenticationMethodConfig, Config, ConnectionError, Interface, WifiController,
};
use log::{info, warn};
use picoserve::response::ws::{Message, SocketRx, SocketTx, WebSocketCallback};
use picoserve::response::{Content, File, WebSocketUpgrade};
use picoserve::routing::{get, get_service};
use spine_board::calibration::Addresses;
use spine_board::cpp_log::scan_label;
use spine_board::{BusScan, ScanState};
use static_cell::StaticCell;
use status_lines::{Body, Line, LineBuf};

/// The WiFi's name and password: build.rs's copy of `src/wifi_secrets.rs`.
#[cfg(wifi_secrets)]
// UPDATE_PASSWORD is for wifi-update only.
#[cfg_attr(not(feature = "wifi-update"), allow(dead_code))]
pub(crate) mod secrets {
    include!(concat!(env!("OUT_DIR"), "/wifi_secrets.rs"));
}
/// Without the file, main.rs's `compile_error!` says how to make it; this only keeps
/// that the one error.
#[cfg(not(wifi_secrets))]
#[allow(dead_code)]
pub(crate) mod secrets {
    pub const SSID: &str = "";
    pub const PASSWORD: &str = "";
    pub const UPDATE_PASSWORD: &str = "";
}

/// The heap the radio needs (esp-radio allocates its buffers). It lives in the RAM the
/// bootloader used (`dram2`, 96 KB on the ESP32, free once the program runs), not beside
/// the statics and the stack: there it pushed the statics past the end of DRAM.
const HEAP_BYTES: usize = 72 * 1024;

/// Clients at once: HTTP connections, each with its own task; a WebSocket holds one.
const WEB_TASKS: usize = 3;
/// Lines a slow WebSocket client can fall behind before it loses the oldest.
const QUEUE: usize = 8;
/// WebSocket clients at once: each holds one of the web tasks.
const STREAMS: usize = 2;
/// Text lines a slow `/log` client can fall behind.
const LOG_QUEUE: usize = 4;

/// The page (`page.html`, beside this file's folder).
const PAGE: &str = include_str!("../page.html");

/// Every line, for the WebSockets: a slow one loses the oldest.
static LINES: PubSubChannel<CriticalSectionRawMutex, LineBuf, QUEUE, STREAMS, 0> =
    PubSubChannel::new();
/// The text log's lines, for `/log`: a slow reader loses the oldest.
static LOG_LINES: PubSubChannel<CriticalSectionRawMutex, LineBuf, LOG_QUEUE, STREAMS, 0> =
    PubSubChannel::new();
/// The car's four I2C addresses, for `/scan`'s names.
static ADDRESSES: Mutex<CriticalSectionRawMutex, RefCell<Option<Addresses>>> =
    Mutex::new(RefCell::new(None));
/// The latest status line, for `/status.json`.
static LATEST: Mutex<CriticalSectionRawMutex, RefCell<LineBuf>> =
    Mutex::new(RefCell::new(LineBuf::new()));
/// The latest health and config lines, for `/health` and `/config`.
static LATEST_HEALTH: Mutex<CriticalSectionRawMutex, RefCell<LineBuf>> =
    Mutex::new(RefCell::new(LineBuf::new()));
static LATEST_CONFIG: Mutex<CriticalSectionRawMutex, RefCell<LineBuf>> =
    Mutex::new(RefCell::new(LineBuf::new()));
/// `/scan` asked for a scan; the tick takes it.
static SCAN_ASKED: AtomicBool = AtomicBool::new(false);
/// The scan as the tick last left it.
static SCAN: Mutex<CriticalSectionRawMutex, RefCell<BusScan>> =
    Mutex::new(RefCell::new(BusScan::new()));

/// From the tick: one line, to every WebSocket, and (a status, health or config line) to
/// its path. It never waits: with a client behind, the oldest line it hasn't read is
/// dropped.
pub fn publish(line: &Line<'_>) {
    let mut buf = LineBuf::new();
    if buf.set(line).is_err() {
        return; // can't happen with MAX_LINE; never worth stopping the tick for
    }
    let latest = match line.body {
        Body::Status(_) => Some(&LATEST),
        Body::Health(_) => Some(&LATEST_HEALTH),
        Body::Config(_) => Some(&LATEST_CONFIG),
        _ => None,
    };
    if let Some(latest) = latest {
        latest.lock(|latest| latest.borrow_mut().clone_from(&buf));
    }
    LINES.immediate_publisher().publish_immediate(buf);
}

/// From the tick: one text log line, to every `/log` client. It never waits.
pub fn publish_text(text: &impl fmt::Display) {
    let mut buf = LineBuf::new();
    if buf.set_text(text).is_ok() {
        LOG_LINES.immediate_publisher().publish_immediate(buf);
    }
}

/// From the tick: true once after each `/scan`.
pub fn take_scan_request() -> bool {
    SCAN_ASKED.swap(false, Ordering::Relaxed)
}

/// From the tick: where the scan is.
pub fn set_scan(scan: &BusScan) {
    SCAN.lock(|s| *s.borrow_mut() = *scan);
}

/// Start the radio, the network and the web server, as tasks on `spawner`. Nothing waits
/// for the WiFi: if it never joins, the tasks just keep trying.
pub fn start(
    spawner: Spawner,
    wifi: esp_hal::peripherals::WIFI<'static>,
    addresses: Addresses,
    #[cfg(feature = "wifi-update")] flash: esp_hal::peripherals::FLASH<'static>,
) {
    esp_alloc::heap_allocator!(#[esp_hal::ram(reclaimed)] size: HEAP_BYTES);
    ADDRESSES.lock(|a| *a.borrow_mut() = Some(addresses));

    let controller = match WifiController::new(wifi, Default::default()) {
        Ok(c) => c,
        Err(e) => {
            warn!("WiFi: the radio didn't start ({e:?}); the spine runs without it");
            return;
        }
    };
    let device = Interface::station();
    let seed = u64::from(esp_hal::rng::Rng::new().random()) << 32
        | u64::from(esp_hal::rng::Rng::new().random());

    // A socket for each web task, DHCP's, and the update server's.
    static RESOURCES: StaticCell<StackResources<{ WEB_TASKS + 2 }>> = StaticCell::new();
    let (stack, runner) = embassy_net::new(
        device,
        embassy_net::Config::dhcpv4(Default::default()),
        RESOURCES.init(StackResources::new()),
        seed,
    );

    static CONFIG: picoserve::Config = picoserve::Config::new(picoserve::Timeouts {
        start_read_request: Duration::from_secs(5),
        persistent_start_read_request: Duration::from_secs(1),
        read_request: Duration::from_secs(1),
        write: Duration::from_secs(1),
    });

    let spawned = (|| -> Result<(), embassy_executor::SpawnError> {
        spawner.spawn(connection(controller)?);
        spawner.spawn(network(runner)?);
        for id in 0..WEB_TASKS {
            spawner.spawn(web(id, stack, &CONFIG)?);
        }
        Ok(())
    })();
    #[cfg(feature = "wifi-update")]
    crate::update::start(spawner, stack, flash);
    if let Err(e) = spawned {
        warn!("WiFi: a task didn't start ({e:?})");
    }
}

/// Join the WiFi, and join again whenever it drops (the router going away included).
#[embassy_executor::task]
async fn connection(mut controller: WifiController<'static>) {
    let config = match (secrets::SSID.try_into(), secrets::PASSWORD.try_into()) {
        (Ok(ssid), Ok(password)) => Config::Station(
            StationConfig::default()
                .with_ssid(ssid)
                .with_authentication(AuthenticationMethodConfig::Wpa2Personal(password)),
        ),
        // Never say what they were.
        _ => {
            warn!("WiFi: the name or password in src/wifi_secrets.rs is too long");
            return;
        }
    };
    loop {
        if let Err(e) = controller.set_config(&config) {
            warn!("WiFi: set up failed ({e:?}); again in 5 s");
            Timer::after(Duration::from_secs(5)).await;
            continue;
        }
        match controller.connect_async().await {
            Ok(_) => {
                info!("WiFi: joined");
                let reason = controller.wait_for_disconnect_async().await;
                warn!("WiFi: dropped ({:?})", reason.map(|d| d.reason));
            }
            // Only the reason: the rest of `DisconnectedInfo` names the network.
            Err(ConnectionError::Failed(info)) => warn!("WiFi: couldn't join ({:?})", info.reason),
            Err(ConnectionError::WifiError(e)) => warn!("WiFi: couldn't join ({e:?})"),
            Err(_) => warn!("WiFi: couldn't join"),
        }
        Timer::after(Duration::from_secs(2)).await;
    }
}

#[embassy_executor::task]
async fn network(mut runner: Runner<'static, Interface>) -> ! {
    runner.run().await
}

#[embassy_executor::task(pool_size = WEB_TASKS)]
async fn web(id: usize, stack: Stack<'static>, config: &'static picoserve::Config) -> ! {
    let app = router();
    stack.wait_config_up().await;
    if id == 0 {
        if let Some(v4) = stack.config_v4() {
            let ip = v4.address.address();
            info!("WiFi -> {ip}: serving http://{ip}/ (the status page; also /status, /status.json, /health, /config, /ws, /log)");
            info!("Scan -> http://{ip}/scan");
            #[cfg(feature = "wifi-update")]
            info!(
                "OTA  -> http://{ip}:{}/update (POST, with the update password; README.md)",
                crate::update::PORT
            );
        }
    }
    let mut tcp_rx = [0; 1024];
    let mut tcp_tx = [0; 2048];
    let mut http = [0; 1024];
    loop {
        picoserve::Server::new(&app, config, &mut http)
            .listen_and_serve(id, stack, 80, &mut tcp_rx, &mut tcp_tx)
            .await
            .into_never()
    }
}

/// GET only: anything else is picoserve's 404 or 405.
fn router() -> picoserve::Router<impl picoserve::routing::PathRouter> {
    picoserve::Router::new()
        .route("/", get_service(File::html(PAGE)))
        .route("/status", get_service(File::html(PAGE)))
        .route("/status.json", get(async || latest(&LATEST)))
        .route("/health", get(async || latest(&LATEST_HEALTH)))
        .route("/config", get(async || latest(&LATEST_CONFIG)))
        .route(
            "/scan",
            get(async || {
                SCAN_ASKED.store(true, Ordering::Relaxed);
                let scan = SCAN.lock(|s| *s.borrow());
                let mut body = Json::new();
                let _ = write_scan(&mut body, &scan);
                body
            }),
        )
        .route(
            "/ws",
            get(async |upgrade: WebSocketUpgrade| upgrade.on_upgrade(Stream(&LINES))),
        )
        .route(
            "/log",
            get(async |upgrade: WebSocketUpgrade| upgrade.on_upgrade(Stream(&LOG_LINES))),
        )
}

/// The latest line of a kind, as a reply; before the first, an empty object.
fn latest(line: &Mutex<CriticalSectionRawMutex, RefCell<LineBuf>>) -> Json {
    let mut body = Json::new();
    line.lock(|latest| {
        let latest = latest.borrow();
        let _ = body.write_str(if latest.is_empty() {
            "{}"
        } else {
            latest.as_str()
        });
    });
    body
}

/// `{"scan":"running","found":[4,5,12,32],"names":[{"address":4,"name":"JRK brake"},…]}`:
/// the addresses in decimal, as JSON has it; then the C++'s names for those it knows.
fn write_scan(w: &mut impl fmt::Write, scan: &BusScan) -> fmt::Result {
    let state = match scan.state() {
        ScanState::Idle => "starting",
        ScanState::Running { .. } => "running",
        ScanState::Paused { .. } => "paused: the car is armed or driving",
        ScanState::Done => "done",
    };
    write!(w, r#"{{"scan":"{state}","found":["#)?;
    for (i, address) in scan.found().enumerate() {
        if i > 0 {
            w.write_char(',')?;
        }
        write!(w, "{address}")?;
    }
    w.write_str(r#"],"names":["#)?;
    if let Some(a) = ADDRESSES.lock(|a| *a.borrow()) {
        let named = scan
            .found()
            .filter_map(|address| scan_label(address, &a).map(|name| (address, name)));
        for (i, (address, name)) in named.enumerate() {
            if i > 0 {
                w.write_char(',')?;
            }
            write!(w, r#"{{"address":{address},"name":"{name}"}}"#)?;
        }
    }
    w.write_str("]}")
}

/// A WebSocket that sends every line of its channel and takes nothing.
struct Stream<const Q: usize>(
    &'static PubSubChannel<CriticalSectionRawMutex, LineBuf, Q, STREAMS, 0>,
);

impl<const Q: usize> WebSocketCallback for Stream<Q> {
    async fn run<R: picoserve::io::Read, W: picoserve::io::Write<Error = R::Error>>(
        self,
        mut rx: SocketRx<R>,
        mut tx: SocketTx<W>,
    ) -> Result<(), W::Error> {
        let Ok(mut lines) = self.0.subscriber() else {
            // Every stream is taken.
            return tx.close(Some((1013, "busy: two clients already"))).await;
        };
        let mut buf = [0; 128];
        loop {
            match rx.next_message(&mut buf, lines.next_message()).await? {
                picoserve::futures::Either::First(Ok(Message::Ping(data))) => {
                    tx.send_pong(data).await?
                }
                picoserve::futures::Either::First(Ok(Message::Close(_)))
                | picoserve::futures::Either::First(Err(_)) => break,
                // Read only: whatever else a client sends is dropped.
                picoserve::futures::Either::First(Ok(_)) => {}
                picoserve::futures::Either::Second(WaitResult::Message(line)) => {
                    tx.send_text(line.as_str()).await?
                }
                // The reader sees the gap in `seq`.
                picoserve::futures::Either::Second(WaitResult::Lagged(_)) => {}
            }
        }
        tx.close(None).await
    }
}

/// A small JSON reply, built in place.
struct Json {
    buf: [u8; status_lines::MAX_LINE],
    len: usize,
}

impl Json {
    const fn new() -> Self {
        Json {
            buf: [0; status_lines::MAX_LINE],
            len: 0,
        }
    }
}

impl fmt::Write for Json {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        let end = self.len + s.len();
        let dest = self.buf.get_mut(self.len..end).ok_or(fmt::Error)?;
        dest.copy_from_slice(s.as_bytes());
        self.len = end;
        Ok(())
    }
}

impl Content for Json {
    fn content_type(&self) -> &'static str {
        "application/json"
    }

    fn content_length(&self) -> usize {
        self.len
    }

    async fn write_content<W: picoserve::io::Write>(self, mut writer: W) -> Result<(), W::Error> {
        writer.write_all(&self.buf[..self.len]).await
    }
}
