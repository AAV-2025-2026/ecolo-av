//! The spine's board program, for a Raspberry Pi Pico 2 (RP2350) on the bench.
//!
//! It puts `spine-board` and `spine-core` on the chip's peripherals. The pin map is one
//! table in `docs/rust-firmware.md`; `main` assigns the pins in the same order.
//!
//! | Part | How |
//! |---|---|
//! | the spine's loop | `SpineBoard::tick` every 10 ms, in thread mode |
//! | CAN | an MCP2515 on SPI0, polled each tick ([`can::CanPort`]) |
//! | steering, brake, throttle, direction | the four I2C devices on one blocking I2C0 bus |
//! | the RC receiver | UART1, receive only; its interrupt fills a buffer, so no byte is lost while a tick waits on I2C |
//! | the wheel's spoke sensors | read every millisecond by a task in a higher-priority executor, which preempts the loop |
//! | the e-stop | an input with a pull-up, on a spare contact of the button: read only |
//! | the hardware watchdog | fed after every tick: a program that hangs or panics resets within 100 ms |
//!
//! After any reset the spine is safe by itself: `SpineBoard::init` puts the throttle at 0
//! and the brake on, and `spine-core` boots latched, so it drives only once ROS disarms,
//! then arms.
//!
//! The e-stop rule (Ben): the red button always stops the car, whatever this program does.
//! It stays wired as it is; the spine only reads a spare contact, and tells ROS. No output
//! of this program is in its path.
#![no_std]
#![no_main]

mod can;

use can::CanPort;
use core::cell::{Cell, RefCell};
use defmt::{info, warn, Debug2Format};
use embassy_executor::{InterruptExecutor, Spawner};
use embassy_rp::gpio::{Input, Level, Output, Pull};
use embassy_rp::i2c::{self, I2c};
// Both the module and the #[interrupt] attribute: a plain `use` brings the two.
use embassy_rp::interrupt;
use embassy_rp::interrupt::{InterruptExt, Priority};
use embassy_rp::peripherals::{SPI0, UART1};
use embassy_rp::spi::{self, Spi};
use embassy_rp::uart::{self, BufferedInterruptHandler, BufferedUartRx};
use embassy_rp::watchdog::Watchdog;
use embassy_rp::{bind_interrupts, pac};
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_time::{Duration, Instant, Ticker};
use embedded_hal_bus::i2c::RefCellDevice;
use embedded_hal_bus::spi::{ExclusiveDevice, NoDelay};
use mcp2515::{Bitrate, Crystal, Mcp2515, Mode};
use spine_board::{Board, Calibration, CanFrame, Devices, SpineBoard, SpokeSensors, WheelCount};
use spine_core::SpineConfig;
use static_cell::ConstStaticCell;
use {defmt_rtt as _, panic_probe as _};

// --- Settings -------------------------------------------------------------------------

/// The spine's loop: about 100 times a second (`spine-board`).
const TICK: Duration = Duration::from_millis(10);

/// The RP2350's watchdog: when a tick doesn't end within this, the chip resets. Ten ticks;
/// a tick takes a few milliseconds of I2C.
const WATCHDOG: Duration = Duration::from_millis(100);

/// The MCP2515 module's crystal: read it off its can ("8.000" or "16.000").
const CAN_CRYSTAL: Crystal = Crystal::MHZ_8;
/// The car's bus (`firmware/can/aav.dbc`).
const CAN_BITRATE: Bitrate = Bitrate::KBPS_500;
/// `Mode::Loopback` checks the SPI wiring with no bus at all (the spine then hears only
/// itself, and drops it: the filters keep only ROS's frames).
const CAN_MODE: Mode = Mode::Normal;
/// The MCP2515's SPI clock; it takes up to 10 MHz.
const CAN_SPI_HZ: u32 = 4_000_000;
/// How often the chip's health is read, and how often a chip that isn't up is tried again.
const CAN_CHECK_MS: u32 = 100;
const CAN_RETRY_MS: u32 = 1000;

/// I2C to the Jrk G2s, the DAC and the expander: 100 kHz, as today (`spine-board`).
const I2C_HZ: u32 = 100_000;

/// The e-stop's spare contact closes to ground while the button is out. The pin then reads
/// high when the button is pressed, and also when the wire is cut. TODO(Q6): the contact.
const ESTOP_OPEN: Level = Level::High;

/// How often the wheel's two spoke sensors are read: the 2025-26 encoder's 1 ms.
const WHEEL_SAMPLE: Duration = Duration::from_millis(1);

/// The LED blinks slowly while all runs, and fast while CAN isn't up (ticks a half-period).
const BLINK_OK_TICKS: u32 = 50;
const BLINK_NO_CAN_TICKS: u32 = 10;

// --- Interrupts, executors, shared state -------------------------------------------------

bind_interrupts!(struct Irqs {
    UART1_IRQ => BufferedInterruptHandler<UART1>;
});

/// The wheel sampler runs here, above the loop: the loop spends milliseconds of each tick
/// waiting on I2C, and the sampler must not miss a spoke meanwhile.
static SAMPLER: InterruptExecutor = InterruptExecutor::new();

#[interrupt]
unsafe fn SWI_IRQ_1() {
    // SAFETY: SWI_IRQ_1 belongs to SAMPLER alone; main starts it there, once.
    unsafe { SAMPLER.on_interrupt() }
}

/// The wheel's counter: written by the sampler, read by the loop.
static WHEEL: Mutex<CriticalSectionRawMutex, Cell<WheelCount>> =
    Mutex::new(Cell::new(WheelCount { count: 0, at_ms: 0 }));

/// The RC receiver's bytes, between its interrupt and the loop: 115 arrive every tick.
static IBUS_BUFFER: ConstStaticCell<[u8; 512]> = ConstStaticCell::new([0; 512]);

// --- The board ---------------------------------------------------------------------------

type CanSpi = ExclusiveDevice<Spi<'static, SPI0, spi::Blocking>, Output<'static>, NoDelay>;

/// What this board gives `spine-board`: the clock, the e-stop, the wheel counter, CAN.
struct Pico2 {
    can: CanPort<CanSpi>,
    estop: Input<'static>,
    led: Output<'static>,
}

impl Board for Pico2 {
    fn now_ms(&mut self) -> u32 {
        now_ms()
    }

    fn estop_open(&mut self) -> bool {
        self.estop.get_level() == ESTOP_OPEN
    }

    fn wheel(&mut self) -> WheelCount {
        WHEEL.lock(Cell::get)
    }

    fn can_receive(&mut self) -> Option<CanFrame> {
        self.can.receive()
    }

    fn can_send(&mut self, frame: &CanFrame) -> bool {
        self.can.send(frame)
    }
}

impl Pico2 {
    /// After each tick: CAN's health, and the LED.
    fn after_tick(&mut self, ticks: u32) {
        self.can.service(now_ms());
        let half_period = if self.can.is_up() {
            BLINK_OK_TICKS
        } else {
            BLINK_NO_CAN_TICKS
        };
        if ticks.is_multiple_of(half_period) {
            self.led.toggle();
        }
    }
}

/// Milliseconds since boot. It wraps after 49 days, as `spine-core` expects.
fn now_ms() -> u32 {
    Instant::now().as_millis() as u32
}

// --- The program -------------------------------------------------------------------------

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    let p = embassy_rp::init(Default::default());

    // The watchdog first: from here on, a hang anywhere resets the chip.
    let mut watchdog = Watchdog::new(p.WATCHDOG);
    let reset_by = watchdog.reset_reason();
    watchdog.pause_on_debug(true);
    watchdog.start(WATCHDOG);
    reset_all_but_the_oscillators();
    info!(
        "spine-pico2 {} started; the last reset: {}",
        env!("CARGO_PKG_VERSION"),
        Debug2Format(&reset_by)
    );

    // The pin map (docs/rust-firmware.md). Change the table with it.
    let mut spi_config = spi::Config::default(); // mode 0, as the MCP2515 takes
    spi_config.frequency = CAN_SPI_HZ;
    let can_bus = Spi::new_blocking(p.SPI0, p.PIN_18, p.PIN_19, p.PIN_16, spi_config); // SCK, SI, SO
    let can_cs = Output::new(p.PIN_17, Level::High);
    let Ok(can_spi) = ExclusiveDevice::new_no_delay(can_bus, can_cs);

    let mut i2c_config = i2c::Config::default(); // with the pins' own pull-ups as a fallback
    i2c_config.frequency = I2C_HZ;
    let i2c_bus = RefCell::new(I2c::new_blocking(p.I2C0, p.PIN_5, p.PIN_4, i2c_config)); // SCL, SDA

    let mut uart_config = uart::Config::default();
    uart_config.baudrate = ibus::BAUD;
    let ibus_rx = BufferedUartRx::new(p.UART1, Irqs, p.PIN_9, IBUS_BUFFER.take(), uart_config);

    let estop = Input::new(p.PIN_15, Pull::Up);
    let wheel_a = Input::new(p.PIN_10, Pull::Up);
    let wheel_b = Input::new(p.PIN_11, Pull::Up);
    let led = Output::new(p.PIN_25, Level::Low);

    // The wheel sampler, above the loop.
    interrupt::SWI_IRQ_1.set_priority(Priority::P2);
    let sampler = SAMPLER.start(interrupt::SWI_IRQ_1);
    sampler.spawn(sample_wheel(wheel_a, wheel_b).expect("main spawns the sampler once"));

    // The spine: the devices first, safe at once (throttle 0, brake on), then CAN.
    let cal = Calibration::TODAY;
    let devices = Devices::new(
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        &cal,
    );
    let board = Pico2 {
        can: CanPort::new(Mcp2515::new(can_spi), now_ms()),
        estop,
        led,
    };
    let mut spine = SpineBoard::new(board, devices, ibus_rx, cal, SpineConfig::default());
    let faults = spine.init();
    if faults != 0 {
        warn!(
            "power-up: device faults {:#x}; the car stays stopped until ROS arms it",
            faults
        );
    }
    spine.board().can.service(now_ms());

    let mut ticker = Ticker::every(TICK);
    let mut ticks: u32 = 0;
    loop {
        spine.tick();
        spine.board().after_tick(ticks);
        watchdog.feed(WATCHDOG);
        ticks = ticks.wrapping_add(1);
        ticker.next().await;
    }
}

/// The wheel's two spoke sensors, every millisecond, counted the 2025-26 way.
#[embassy_executor::task]
async fn sample_wheel(a: Input<'static>, b: Input<'static>) {
    let mut sensors = SpokeSensors::TODAY;
    let mut ticker = Ticker::every(WHEEL_SAMPLE);
    loop {
        let count = sensors.update(a.is_high(), b.is_high(), now_ms());
        WHEEL.lock(|wheel| wheel.set(count));
        ticker.next().await;
    }
}

/// What the watchdog resets: every part but the two oscillators, as the Pico SDK does
/// (RP2350 datasheet, 12.9.6.1; the bits are Table 564). embassy-rp 0.10 writes the RP2040's
/// bits here instead: on the RP2350 they select bits 2 to 16, from the ring oscillator to
/// SRAM6, so the reset runs from the ring oscillator onwards (7.4.1) rather than as the
/// vendor's SDK sets it.
fn reset_all_but_the_oscillators() {
    let mut parts = pac::psm::regs::Wdsel(0x01FF_FFFF); // bits 0 to 24: every part
    parts.set_rosc(false);
    parts.set_xosc(false);
    pac::PSM.wdsel().write_value(parts);
}
