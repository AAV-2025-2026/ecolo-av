//! The status display's board program, for a Raspberry Pi Pico 2 (RP2350): the Rust
//! version of the 2025-26 `AAV_sentinel` Pico 2.
//!
//! An I2C device at 0x42. A computer on the car writes it a 46-byte telemetry packet; it
//! shows it. All the deciding is in the `sentinel` crate; this program only moves pins.
//! The pin map is one table in `docs/rust-firmware.md`; `main` assigns the pins in the
//! same order.
//!
//! | Part | How |
//! |---|---|
//! | the packets | I2C0 as a device at 0x42 (`embassy-rp`'s `I2cSlave`), in its own task |
//! | the 16x2 LCD | an HD44780 on six GPIO pins, 4-bit (`hd44780`); a line is written only when it changes |
//! | the 8x8 matrix | a MAX7219 on SPI1 (`max7219`) |
//! | the LED bar | ten GPIO outputs: the computers and ROS nodes that are up |
//! | the knob and the button | read every millisecond by a task in a higher-priority executor |
//! | the buzzer | its own task: a beep never holds anything else up |
//! | the hardware watchdog | fed every loop, 5 ms: a hang or a panic resets the chip within 0.5 s |
#![no_std]
#![no_main]

use defmt::{info, warn, Debug2Format};
use embassy_executor::{InterruptExecutor, Spawner};
use embassy_rp::gpio::{Input, Level, Output, Pull};
use embassy_rp::i2c_slave::{self, Command, I2cSlave};
// Both the module and the #[interrupt] attribute: a plain `use` brings the two.
use embassy_rp::interrupt;
use embassy_rp::interrupt::{InterruptExt, Priority};
use embassy_rp::peripherals::I2C0;
use embassy_rp::spi::{self, Spi};
use embassy_rp::watchdog::Watchdog;
use embassy_rp::{bind_interrupts, i2c, pac};
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use embassy_time::{Delay, Duration, Instant, Ticker, Timer};
use embedded_hal_bus::spi::ExclusiveDevice;
use hd44780::{Hd44780, Lines, Pins};
use max7219::MAX7219;
use sentinel::{Beep, Button, Input as UserInput, Knob, Pattern, Screen, Sentinel};
use {defmt_rtt as _, panic_probe as _};

// --- Settings ----------------------------------------------------------------------------

/// The display's loop: inputs, the clock, the displays.
const LOOP: Duration = Duration::from_millis(5);
/// The RP2350's watchdog: a hundred loops.
const WATCHDOG: Duration = Duration::from_millis(500);
/// The knob and the button are read this often.
const SAMPLE_EVERY: Duration = Duration::from_millis(1);
/// The MAX7219's SPI clock: the 2025-26 1 MHz (the chip takes up to 10).
const MATRIX_SPI_HZ: u32 = 1_000_000;
/// The matrix's brightness, 0 to 15: the 2025-26 8.
const MATRIX_INTENSITY: u8 = 8;
/// The largest I2C write kept: a packet is 46 bytes.
const WRITE_MAX: usize = 64;

// --- Interrupts, executors, shared state -------------------------------------------------

bind_interrupts!(struct Irqs {
    I2C0_IRQ => i2c::InterruptHandler<I2C0>;
});

/// The knob's sampler runs here, above the loop: an LCD update takes 2 ms of busy waiting,
/// and the knob must not lose a step meanwhile.
static SAMPLER: InterruptExecutor = InterruptExecutor::new();

#[interrupt]
unsafe fn SWI_IRQ_1() {
    // SAFETY: SWI_IRQ_1 belongs to SAMPLER alone; main starts it there, once.
    unsafe { SAMPLER.on_interrupt() }
}

/// One I2C write, from the I2C task to the loop.
struct Write {
    bytes: [u8; WRITE_MAX],
    len: usize,
}

static WRITES: Channel<CriticalSectionRawMutex, Write, 4> = Channel::new();
static INPUTS: Channel<CriticalSectionRawMutex, UserInput, 8> = Channel::new();
static BEEPS: Channel<CriticalSectionRawMutex, Beep, 4> = Channel::new();

/// Play a beep; if four are already waiting, this one is dropped.
fn beep(b: Beep) {
    if BEEPS.try_send(b).is_err() {
        warn!("buzzer busy: {}", Debug2Format(&b));
    }
}

/// Milliseconds since boot. It wraps after 49 days; only differences matter.
fn now_ms() -> u32 {
    Instant::now().as_millis() as u32
}

// --- The program -------------------------------------------------------------------------

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_rp::init(Default::default());

    // The watchdog first: from here on, a hang anywhere resets the chip.
    let mut watchdog = Watchdog::new(p.WATCHDOG);
    let reset_by = watchdog.reset_reason();
    watchdog.pause_on_debug(true);
    watchdog.start(WATCHDOG);
    reset_all_but_the_oscillators();
    info!(
        "sentinel-pico2 {} started; the last reset: {}",
        env!("CARGO_PKG_VERSION"),
        Debug2Format(&reset_by)
    );

    // The pin map (docs/rust-firmware.md), the 2025-26 one. Change the table with it.
    let mut i2c_config = i2c_slave::Config::default();
    i2c_config.addr = u16::from(sentinel::I2C_ADDRESS);
    i2c_config.general_call = false; // the internal pull-ups stay on, as before
    let i2c = I2cSlave::new(p.I2C0, p.PIN_1, p.PIN_0, Irqs, i2c_config); // SCL, SDA

    let knob_clk = Input::new(p.PIN_2, Pull::Up);
    let knob_dt = Input::new(p.PIN_3, Pull::Up);
    let knob_switch = Input::new(p.PIN_4, Pull::Up);
    let home_button = Input::new(p.PIN_5, Pull::Up);
    let buzzer = Output::new(p.PIN_6, Level::Low);

    let lcd_pins = Pins {
        rs: Output::new(p.PIN_7, Level::Low),
        e: Output::new(p.PIN_8, Level::Low),
        d4: Output::new(p.PIN_9, Level::Low),
        d5: Output::new(p.PIN_10, Level::Low),
        d6: Output::new(p.PIN_11, Level::Low),
        d7: Output::new(p.PIN_12, Level::Low),
    };

    let mut spi_config = spi::Config::default(); // mode 0, as the MAX7219 takes
    spi_config.frequency = MATRIX_SPI_HZ;
    let matrix_bus = Spi::new_blocking_txonly(p.SPI1, p.PIN_14, p.PIN_15, spi_config); // CLK, DIN
    let matrix_cs = Output::new(p.PIN_13, Level::High);

    let mut bar = [
        Output::new(p.PIN_28, Level::Low), // LED 0
        Output::new(p.PIN_27, Level::Low),
        Output::new(p.PIN_26, Level::Low),
        Output::new(p.PIN_22, Level::Low),
        Output::new(p.PIN_21, Level::Low),
        Output::new(p.PIN_20, Level::Low),
        Output::new(p.PIN_19, Level::Low),
        Output::new(p.PIN_18, Level::Low),
        Output::new(p.PIN_17, Level::Low),
        Output::new(p.PIN_16, Level::Low), // LED 9
    ];
    let _power_led = Output::new(p.PIN_25, Level::High); // on while the program runs

    // The buzzer, then the boot beep.
    spawner.spawn(play_beeps(buzzer).expect("main spawns the buzzer once"));
    beep(Beep::Boot);

    // The displays.
    let mut lcd = Hd44780::new(lcd_pins, Delay, Lines::Two);
    let Ok(()) = lcd.init();
    let Ok(matrix_spi) = ExclusiveDevice::new_no_delay(matrix_bus, matrix_cs);
    let mut matrix = MAX7219::from_spi(1, matrix_spi)
        .and_then(|mut m| {
            m.power_on()?;
            m.set_intensity(0, MATRIX_INTENSITY)?;
            Ok(m)
        })
        .map_err(|e| warn!("the matrix: {}", Debug2Format(&e)))
        .ok();
    watchdog.feed(WATCHDOG);

    // The inputs, above the loop; then the I2C device.
    interrupt::SWI_IRQ_1.set_priority(Priority::P2);
    let sampler = SAMPLER.start(interrupt::SWI_IRQ_1);
    sampler.spawn(
        sample_controls(knob_clk, knob_dt, knob_switch, home_button)
            .expect("main spawns the sampler once"),
    );
    spawner.spawn(listen(i2c).expect("main spawns the I2C device once"));
    beep(Beep::Ready);
    info!("listening on I2C at {:#x}", sentinel::I2C_ADDRESS);

    // The loop: everything in, the displays out, only what changed.
    let mut sentinel = Sentinel::new(now_ms());
    let mut shown_screen: Option<Screen> = None;
    let mut shown_pattern: Option<Pattern> = None;
    let mut shown_leds: Option<[bool; 10]> = None;
    let mut ticker = Ticker::every(LOOP);
    loop {
        let now = now_ms();
        while let Ok(write) = WRITES.try_receive() {
            match sentinel.on_write(&write.bytes[..write.len], now) {
                Ok(b) => b.into_iter().for_each(beep),
                Err(e) => warn!("refused a write: {}", Debug2Format(&e)),
            }
        }
        while let Ok(input) = INPUTS.try_receive() {
            beep(sentinel.on_input(input, now));
        }
        if let Some(b) = sentinel.tick(now) {
            beep(b);
        }

        let screen = sentinel.screen();
        if shown_screen != Some(screen) {
            let Ok(()) = lcd.write_line(0, screen.top.bytes());
            let Ok(()) = lcd.write_line(1, screen.bottom.bytes());
            shown_screen = Some(screen);
        }
        let pattern = sentinel.pattern(now);
        if shown_pattern != Some(pattern) {
            if let Some(m) = matrix.as_mut() {
                if let Err(e) = m.write_raw(0, &pattern.rows()) {
                    warn!("the matrix: {}", Debug2Format(&e));
                }
            }
            shown_pattern = Some(pattern);
        }
        let leds = sentinel.leds();
        if shown_leds != Some(leds) {
            bar.iter_mut()
                .zip(leds)
                .for_each(|(pin, on)| pin.set_level(on.into()));
            shown_leds = Some(leds);
        }

        watchdog.feed(WATCHDOG);
        ticker.next().await;
    }
}

/// The I2C device: each write goes to the loop. A read gets zeros: the 2025-26 display
/// had nothing to say either.
#[embassy_executor::task]
async fn listen(mut i2c: I2cSlave<'static, I2C0>) {
    let mut buffer = [0u8; WRITE_MAX];
    loop {
        let read_wanted = match i2c.listen(&mut buffer).await {
            Ok(Command::Write(len)) => {
                forward(&buffer, len);
                false
            }
            Ok(Command::WriteRead(len)) => {
                forward(&buffer, len);
                true
            }
            Ok(Command::Read) => true,
            Ok(Command::GeneralCall(_)) => false,
            Err(i2c_slave::Error::PartialWrite(len)) => {
                warn!("a write longer than {} bytes: refused", len);
                false
            }
            Err(e) => {
                warn!("I2C: {}", e);
                false
            }
        };
        if read_wanted {
            if let Err(e) = i2c.respond_till_stop(0).await {
                warn!("I2C read: {}", e);
            }
        }
    }
}

/// Hand a write to the loop; if four are already waiting, this one is dropped.
fn forward(buffer: &[u8; WRITE_MAX], len: usize) {
    let write = Write {
        bytes: *buffer,
        len,
    };
    if WRITES.try_send(write).is_err() {
        warn!("a write was dropped: the loop is behind");
    }
}

/// The knob and the button, every millisecond.
#[embassy_executor::task]
async fn sample_controls(
    clk: Input<'static>,
    dt: Input<'static>,
    switch: Input<'static>,
    home: Input<'static>,
) {
    let mut knob = Knob::new(clk.is_high(), dt.is_high());
    let mut knob_button = Button::new();
    let mut home_button = Button::new();
    let mut ticker = Ticker::every(SAMPLE_EVERY);
    loop {
        let now = now_ms();
        let inputs = [
            knob.update(clk.is_high(), dt.is_high())
                .map(UserInput::Turn),
            knob_button
                .pressed(switch.is_high(), now)
                .then_some(UserInput::KnobPress),
            home_button
                .pressed(home.is_high(), now)
                .then_some(UserInput::HomePress),
        ];
        for input in inputs.into_iter().flatten() {
            // Eight waiting means the loop has stopped: the watchdog will act.
            let _ = INPUTS.try_send(input);
        }
        ticker.next().await;
    }
}

/// The buzzer: plays each beep in turn.
#[embassy_executor::task]
async fn play_beeps(mut buzzer: Output<'static>) {
    loop {
        let beep = BEEPS.receive().await;
        for tone in beep.tones() {
            buzzer.set_high();
            Timer::after_millis(tone.on_ms.into()).await;
            buzzer.set_low();
            Timer::after_millis(tone.off_ms.into()).await;
        }
    }
}

/// What the watchdog resets: every part but the two oscillators, as the Pico SDK does.
/// embassy-rp 0.10 writes the RP2040's bits here instead (see `boards/pico2/src/main.rs`).
fn reset_all_but_the_oscillators() {
    let mut parts = pac::psm::regs::Wdsel(0x01FF_FFFF); // bits 0 to 24: every part
    parts.set_rosc(false);
    parts.set_xosc(false);
    pac::PSM.wdsel().write_value(parts);
}
