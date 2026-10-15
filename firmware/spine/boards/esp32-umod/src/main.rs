//! The spine on today's control board: the SparkFun ESP32 MicroMod (the original ESP32,
//! Xtensa) on the AAV carrier, beside the Motor-Pi. The Rust replacement for
//! `firmware/legacy/aav_umod_esp32`.
//!
//! It puts `spine-board` and `spine-core` on the ESP32's peripherals, with the same pins
//! and devices as the C++ ([`pins`]). The computer's commands come from one of two links,
//! chosen when it is built:
//!
//! | Feature | Link | Use |
//! |---|---|---|
//! | `legacy-uart` (default) | the Motor-Pi's 13-byte frames on UART1 | today: a drop-in for the C++, with `aav_legacy`'s `legacy_uart_bridge` |
//! | `can` | `firmware/can/aav.dbc` on the TWAI controller | the KEFC plan: the Orin's `spine_bridge` |
//!
//! | Part | How |
//! |---|---|
//! | the spine's loop | `SpineBoard::tick` every 10 ms, on Embassy's thread executor |
//! | steering, brake, throttle, direction | the two Jrk G2s, the DAC and the PCA9555, on one blocking I2C bus at 100 kHz |
//! | the RC receiver | iBUS on UART2, read from its 128-byte FIFO each tick (about 28 ms of iBUS) |
//! | the Motor-Pi | UART1, read the same way (`legacy-uart`) |
//! | CAN | TWAI at 500 kbit/s, polled each tick (`can`) |
//! | the wheel speed | none on this board (the encoder talks to the Motor-Pi): the speed loop runs open loop |
//! | the e-stop's spare contact | an input, with `estop-input`, once it is wired (Q6) |
//! | the hardware watchdog | TIMG1's: fed after every tick; a hang or a panic resets the chip within 100 ms |
//! | the log | UART0, the USB cable: a status line every 200 ms, as the C++ printed |
//!
//! After any reset the spine is safe by itself: `SpineBoard::init` puts the throttle at 0
//! and the brake on, and `spine-core` boots latched: it drives only after a stop (a stop
//! frame, or `armed = 0` on CAN), then a drive command.
//!
//! The e-stop rule (Ben): the red button always stops the car, whatever this program does.
//! It stays wired as it is; this program only reads a spare contact. No output of this
//! program is in its path.
#![no_std]
#![no_main]

#[cfg(all(feature = "legacy-uart", feature = "can"))]
compile_error!(
    "pick one link: `legacy-uart` (the default) or `can` (--no-default-features --features can)"
);
#[cfg(not(any(feature = "legacy-uart", feature = "can")))]
compile_error!("pick a link: `legacy-uart` or `can`");

#[cfg(feature = "can")]
mod can;
mod pins;

use core::cell::RefCell;
use embassy_executor::Spawner;
use embassy_time::{Duration, Ticker};
use embedded_hal_bus::i2c::RefCellDevice;
use esp_hal::gpio::{AnyPin, Level, Output, OutputConfig};
use esp_hal::i2c::master::{self as i2c, I2c};
use esp_hal::time::{Instant, Rate};
use esp_hal::timer::timg::{MwdtStage, TimerGroup};
use esp_hal::uart::{self, UartRx};
use log::{info, warn};
use spine_board::{Board, Calibration, CanFrame, Devices, SpineBoard, WheelCount};
use spine_core::protocol::Mode;
use spine_core::{Outputs, SpeedFeedback, SpineConfig};
use {esp_backtrace as _, esp_println as _};

esp_bootloader_esp_idf::esp_app_desc!();

// --- Settings -------------------------------------------------------------------------

/// The spine's loop: about 100 times a second (`spine-board`).
const TICK: Duration = Duration::from_millis(10);

/// TIMG1's watchdog: when a tick doesn't end within this, the chip resets. Ten ticks; a
/// tick takes a few milliseconds of I2C.
const WATCHDOG_MS: u64 = 100;

/// I2C to the Jrk G2s, the DAC and the expander: 100 kHz, as the C++ (`Wire`'s default).
const I2C_KHZ: u32 = 100;

/// The car's top speed at full throttle, for the open speed loop: this board has no wheel
/// speed. The same guess as `legacy.yaml`'s `full_throttle_speed`. TODO(Q4): measure.
const FULL_THROTTLE_SPEED: f32 = 3.0;

/// The brake while nobody drives, from boot on. The C++ kept it full on (3500), and this
/// board has no e-stop input yet to hold it, so it does the same until the team settles
/// spine-core's `IDLE_BRAKE` (proposed 0.0: released). TODO(Ben): decide.
const IDLE_BRAKE: f32 = 1.0;

/// The status line on the USB cable, as often as the C++'s `publishStatus()`.
const STATUS_EVERY_TICKS: u32 = 20;

/// The status LED blinks slowly while commands come in, fast while they don't.
const BLINK_OK_TICKS: u32 = 50;
const BLINK_NO_LINK_TICKS: u32 = 10;

// --- The board ---------------------------------------------------------------------------

/// What this board gives `spine-board`: the clock, the e-stop, the wheel counter, CAN.
struct Esp32Umod {
    #[cfg(feature = "can")]
    can: can::CanPort,
    #[cfg(feature = "estop-input")]
    estop: esp_hal::gpio::Input<'static>,
    leds: Leds,
}

impl Board for Esp32Umod {
    fn now_ms(&mut self) -> u32 {
        now_ms()
    }

    fn estop_open(&mut self) -> bool {
        #[cfg(feature = "estop-input")]
        {
            self.estop.level() == pins::ESTOP_OPEN
        }
        // Not wired yet (Q6): the red button still stops the car on its own.
        #[cfg(not(feature = "estop-input"))]
        {
            false
        }
    }

    /// No wheel encoder on this board: it talks to the Motor-Pi over Ethernet.
    fn wheel(&mut self) -> WheelCount {
        WheelCount::default()
    }

    fn can_receive(&mut self) -> Option<CanFrame> {
        #[cfg(feature = "can")]
        {
            self.can.receive()
        }
        #[cfg(not(feature = "can"))]
        {
            None
        }
    }

    fn can_send(&mut self, _frame: &CanFrame) -> bool {
        #[cfg(feature = "can")]
        {
            self.can.send(_frame)
        }
        #[cfg(not(feature = "can"))]
        {
            false
        }
    }
}

/// The four LEDs the C++ drove.
struct Leds {
    /// GPIO2, on the processor board: the heartbeat.
    status: Output<'static>,
    /// A fault is reported.
    red: Output<'static>,
    /// The computer drives.
    green: Output<'static>,
    /// The RC transmitter drives.
    blue: Output<'static>,
}

impl Leds {
    fn show(&mut self, out: &Outputs, ticks: u32) {
        let level = |on: bool| if on { Level::High } else { Level::Low };
        self.red.set_level(level(out.faults != 0));
        self.green.set_level(level(out.mode == Mode::Computer));
        self.blue.set_level(level(out.mode == Mode::Rc));
        let half_period = if out.mode == Mode::Computer {
            BLINK_OK_TICKS
        } else {
            BLINK_NO_LINK_TICKS
        };
        if ticks.is_multiple_of(half_period) {
            self.status.toggle();
        }
    }
}

/// Milliseconds since boot. It wraps after 49 days, as `spine-core` expects.
fn now_ms() -> u32 {
    Instant::now().duration_since_epoch().as_millis() as u32
}

// --- The program -------------------------------------------------------------------------

#[esp_rtos::main]
async fn main(_spawner: Spawner) -> ! {
    esp_println::logger::init_logger(log::LevelFilter::Info);
    let p = esp_hal::init(esp_hal::Config::default());

    // Embassy's clock, on TIMG0.
    let timg0 = TimerGroup::new(p.TIMG0);
    esp_rtos::start(timg0.timer0, p.FROM_CPU_INTR0);

    // The watchdog first: from here on, a hang anywhere resets the chip.
    let mut watchdog = TimerGroup::new(p.TIMG1).wdt;
    watchdog.set_timeout(
        MwdtStage::Stage0,
        esp_hal::time::Duration::from_millis(WATCHDOG_MS),
    );
    watchdog.enable();
    info!(
        "spine-esp32-umod {}, link: {}; the last reset: {:?}",
        env!("CARGO_PKG_VERSION"),
        if cfg!(feature = "can") {
            "CAN"
        } else {
            "Motor-Pi UART"
        },
        esp_hal::system::reset_reason()
    );

    // The pin map (src/pins.rs, docs/rust-firmware.md).
    let pins = pins::take_pins!(p);

    let i2c_config = i2c::Config::default().with_frequency(Rate::from_khz(I2C_KHZ));
    let i2c_bus = match I2c::new(p.I2C0, i2c_config) {
        Ok(i2c) => RefCell::new(i2c.with_sda(pins.sda).with_scl(pins.scl)),
        Err(e) => panic!("I2C at {} kHz: {:?}", I2C_KHZ, e), // a constant: never on the car
    };

    let ibus_config = uart::Config::default().with_baudrate(ibus::BAUD);
    let ibus_rx = UartRx::new(p.UART2, ibus_config)
        .map(|rx| rx.with_rx(pins.ibus_rx))
        .unwrap_or_else(|e| panic!("iBUS UART: {:?}", e));

    let output = |pin: AnyPin<'static>, level| Output::new(pin, level, OutputConfig::default());
    let leds = Leds {
        status: output(pins.status_led.into(), Level::High),
        red: output(pins.red_led.into(), Level::Low),
        green: output(pins.green_led.into(), Level::Low),
        blue: output(pins.blue_led.into(), Level::Low),
    };

    let board = Esp32Umod {
        #[cfg(feature = "can")]
        can: {
            use esp_hal::twai::{BaudRate, TwaiConfiguration, TwaiMode};
            let config = TwaiConfiguration::new(
                p.TWAI0,
                pins.can_rx,
                pins.can_tx,
                BaudRate::B500K,
                TwaiMode::Normal,
            );
            can::CanPort::new(config.start())
        },
        #[cfg(feature = "estop-input")]
        estop: esp_hal::gpio::Input::new(
            pins.estop,
            esp_hal::gpio::InputConfig::default().with_pull(esp_hal::gpio::Pull::Up),
        ),
        leds,
    };

    // The spine: the devices first, safe at once (throttle 0, brake on).
    let cal = Calibration::TODAY;
    let devices = Devices::new(
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        RefCellDevice::new(&i2c_bus),
        &cal,
    );
    let config = SpineConfig {
        speed_feedback: SpeedFeedback::None {
            full_throttle_speed: FULL_THROTTLE_SPEED,
        },
        idle_brake: IDLE_BRAKE,
        ..SpineConfig::default()
    };

    #[cfg(feature = "legacy-uart")]
    let mut spine = {
        let motor_pi_config = uart::Config::default().with_baudrate(legacy_link::BAUD);
        let motor_pi_rx = UartRx::new(p.UART1, motor_pi_config)
            .map(|rx| rx.with_rx(pins.motor_pi_rx))
            .unwrap_or_else(|e| panic!("Motor-Pi UART: {:?}", e));
        let link = spine_board::LegacyLink::new(motor_pi_rx, cal);
        SpineBoard::with_link(board, devices, ibus_rx, link, cal, config)
    };
    #[cfg(feature = "can")]
    let mut spine = {
        let _ = pins.motor_pi_rx; // the Motor-Pi's UART stays unused
        SpineBoard::new(board, devices, ibus_rx, cal, config)
    };

    let faults = spine.init();
    if faults != 0 {
        warn!(
            "power-up: device faults {:#x}; the car stays stopped until a stop, then a command",
            faults
        );
    }

    let mut ticker = Ticker::every(TICK);
    let mut ticks: u32 = 0;
    loop {
        let out = spine.tick();
        let board = spine.board();
        board.leds.show(&out, ticks);
        #[cfg(feature = "can")]
        board.can.service(now_ms());
        if ticks.is_multiple_of(STATUS_EVERY_TICKS) {
            status_line(&out);
        }
        watchdog.feed();
        ticks = ticks.wrapping_add(1);
        ticker.next().await;
    }
}

/// One line on the USB cable: what the spine decided, and its faults.
fn status_line(out: &Outputs) {
    info!(
        "STATUS mode={:?} armed={} throttle={:.2} brake={:.2} reverse={} steer={:.3} faults={:#06x}",
        out.mode,
        out.armed,
        out.throttle,
        out.brake,
        out.reverse,
        out.steering_target,
        out.faults
    );
}
