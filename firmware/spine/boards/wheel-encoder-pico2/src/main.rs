//! The wheel encoder's board program, for a Raspberry Pi Pico 2 (RP2350) with a WIZnet
//! W5500 Ethernet chip: the Rust version of the 2025-26 `Wheel_Encoders` Pico 2.
//!
//! It counts the wheel's spokes and sends the count to the Motor Pi over UDP, every 100 ms,
//! byte for byte as before, so `aav_legacy`'s `encoder_udp` reads it unchanged. The pin
//! map is one table in `docs/rust-firmware.md`; `main` assigns the pins in the same order.
//!
//! | Part | How |
//! |---|---|
//! | the two spoke sensors | read every millisecond by a task in a higher-priority executor, counted by `wheel_encoder::SpokeSensors` |
//! | the packet | every 100 ms: the spokes since the last one, as a big-endian int32 (`wheel_encoder::SpokeDelta`) |
//! | Ethernet | the W5500 on SPI0, through `embassy-net-wiznet`; an address from DHCP, as before |
//! | the hardware watchdog | fed after every packet: a program that hangs or panics resets within 1 s |
//! | the LED | blinks slowly once it has an address, fast while it waits for one |
//!
//! What changed from the 2025-26 sketch (`wiznet.ino`): the counter only runs on, and the
//! sender remembers what it sent, so no spoke is lost between reading and clearing it; it
//! waits for DHCP instead of stopping for good when the first try fails; and it needs no
//! USB serial console to start.
#![no_std]
#![no_main]

use core::cell::Cell;
use defmt::{debug, info, warn, Debug2Format};
use embassy_executor::{InterruptExecutor, Spawner};
use embassy_net::udp::{PacketMetadata, UdpSocket};
use embassy_net::{IpEndpoint, Ipv4Address, Stack, StackResources};
use embassy_net_wiznet::chip::W5500;
use embassy_net_wiznet::{Device, Runner, State};
use embassy_rp::clocks::RoscRng;
use embassy_rp::gpio::{Input, Level, Output, Pull};
// Both the module and the #[interrupt] attribute: a plain `use` brings the two.
use embassy_rp::interrupt;
use embassy_rp::interrupt::{InterruptExt, Priority};
use embassy_rp::peripherals::{DMA_CH0, DMA_CH1, SPI0};
use embassy_rp::spi::{self, Async, Spi};
use embassy_rp::watchdog::Watchdog;
use embassy_rp::{bind_interrupts, dma, pac};
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_time::{Delay, Duration, Instant, Ticker};
use embedded_hal_bus::spi::ExclusiveDevice;
use static_cell::StaticCell;
use wheel_encoder::{Reporter, SpokeSensors, WheelCount};
use {defmt_rtt as _, panic_probe as _};

// --- Settings: the 2025-26 ones (wiznet.ino) ---------------------------------------------

/// The W5500's MAC address: the 2025-26 one, the bytes of "Tempel" (54:65:6d:70:65:6c).
/// Kept, so a DHCP reservation for it on the car's router still works. TODO: it isn't a
/// locally administered address; 02:... would be the proper choice for a home-made board.
const MAC: [u8; 6] = *b"Tempel";

/// The Motor Pi, where `encoder_udp` listens.
const MOTOR_PI: IpEndpoint = IpEndpoint::new(
    embassy_net::IpAddress::Ipv4(Ipv4Address::new(192, 168, 1, 193)),
    10111,
);
/// This board's own UDP port: the packets come from it.
const LOCAL_PORT: u16 = 11101;

/// One packet every 100 ms.
const SEND_EVERY: Duration = Duration::from_millis(100);
/// The spoke sensors are read every millisecond.
const SAMPLE_EVERY: Duration = Duration::from_millis(1);
/// For the logs: the spokes on one wheel turn.
const SPOKES_PER_REV: u16 = 8;

/// The W5500's SPI clock: the chip takes up to 80 MHz; Embassy's example runs it at 50.
const W5500_SPI_HZ: u32 = 50_000_000;

/// The RP2350's watchdog: ten packets' time.
const WATCHDOG: Duration = Duration::from_millis(1000);

/// The LED: a slow blink (every 5 packets) with an address, a fast one (every packet) without.
const BLINK_UP_PACKETS: u32 = 5;
const BLINK_DOWN_PACKETS: u32 = 1;

// --- Interrupts, executors, shared state -------------------------------------------------

bind_interrupts!(struct Irqs {
    DMA_IRQ_0 => dma::InterruptHandler<DMA_CH0>, dma::InterruptHandler<DMA_CH1>;
});

/// The spoke sampler runs here, above the network: smoltcp and the SPI transfers must never
/// make it miss a spoke.
static SAMPLER: InterruptExecutor = InterruptExecutor::new();

#[interrupt]
unsafe fn SWI_IRQ_1() {
    // SAFETY: SWI_IRQ_1 belongs to SAMPLER alone; main starts it there, once.
    unsafe { SAMPLER.on_interrupt() }
}

/// The wheel's counter: written by the sampler, read by the sender.
static WHEEL: Mutex<CriticalSectionRawMutex, Cell<WheelCount>> =
    Mutex::new(Cell::new(WheelCount { count: 0, at_ms: 0 }));

type W5500Spi = ExclusiveDevice<Spi<'static, SPI0, Async>, Output<'static>, Delay>;

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
        "wheel-encoder-pico2 {} started; the last reset: {}",
        env!("CARGO_PKG_VERSION"),
        Debug2Format(&reset_by)
    );

    // The pin map (docs/rust-firmware.md). Change the table with it.
    let sensor_a = Input::new(p.PIN_2, Pull::None); // the IR modules drive their outputs
    let sensor_b = Input::new(p.PIN_10, Pull::None);

    let mut spi_config = spi::Config::default();
    spi_config.frequency = W5500_SPI_HZ;
    let spi = Spi::new(
        p.SPI0, p.PIN_18, p.PIN_19, p.PIN_16, p.DMA_CH0, p.DMA_CH1, Irqs, spi_config,
    ); // SCK, MOSI, MISO
    let cs = Output::new(p.PIN_17, Level::High);
    let w5500_int = Input::new(p.PIN_21, Pull::Up);
    let w5500_reset = Output::new(p.PIN_20, Level::High);
    let mut led = Output::new(p.PIN_25, Level::Low);

    // The spoke sampler, above everything else.
    interrupt::SWI_IRQ_1.set_priority(Priority::P2);
    let sampler = SAMPLER.start(interrupt::SWI_IRQ_1);
    sampler.spawn(sample_spokes(sensor_a, sensor_b).expect("main spawns the sampler once"));

    // The W5500, then the IP stack on it. Without the chip this panics, and the watchdog
    // tries again from the start.
    static W5500_STATE: StaticCell<State<8, 8>> = StaticCell::new();
    let Ok(spi) = ExclusiveDevice::new(spi, cs, Delay);
    let (device, w5500) = embassy_net_wiznet::new(
        MAC,
        W5500_STATE.init(State::new()),
        spi,
        w5500_int,
        w5500_reset,
    )
    .await
    .expect("the W5500 answers on SPI0");
    spawner.spawn(run_w5500(w5500).expect("main spawns the W5500 once"));

    static RESOURCES: StaticCell<StackResources<2>> = StaticCell::new();
    let (stack, net) = embassy_net::new(
        device,
        embassy_net::Config::dhcpv4(Default::default()),
        RESOURCES.init(StackResources::new()),
        RoscRng.next_u64(),
    );
    spawner.spawn(run_net(net).expect("main spawns the IP stack once"));

    // The sender. It starts at once, and sends nothing until DHCP gives an address.
    let mut rx_meta = [PacketMetadata::EMPTY; 1];
    let mut rx_buffer = [0; 16];
    let mut tx_meta = [PacketMetadata::EMPTY; 4];
    let mut tx_buffer = [0; 64];
    let mut socket = UdpSocket::new(
        stack,
        &mut rx_meta,
        &mut rx_buffer,
        &mut tx_meta,
        &mut tx_buffer,
    );
    if let Err(e) = socket.bind(LOCAL_PORT) {
        warn!("UDP port {}: {}", LOCAL_PORT, e);
    }

    let mut reporter = Reporter::new(WHEEL.lock(Cell::get));
    let mut was_up = false;
    let mut ticker = Ticker::every(SEND_EVERY);
    let mut packets: u32 = 0;
    loop {
        ticker.next().await;
        let delta = reporter.report(WHEEL.lock(Cell::get));
        let up = announce(stack, &mut was_up);
        if up {
            // A full queue or no route only loses this packet; the next one carries on.
            if let Err(e) = socket.send_to(&delta.to_bytes(), MOTOR_PI).await {
                warn!("packet not sent: {}", e);
            }
        }
        debug!(
            "spokes {} | {} rpm | {}",
            delta.0,
            delta.rpm(SPOKES_PER_REV, SEND_EVERY.as_millis() as u32),
            Debug2Format(&delta.direction())
        );

        let half_period = if up {
            BLINK_UP_PACKETS
        } else {
            BLINK_DOWN_PACKETS
        };
        if packets.is_multiple_of(half_period) {
            led.toggle();
        }
        packets = packets.wrapping_add(1);
        watchdog.feed(WATCHDOG);
    }
}

/// Whether the network is up; logs the address when it comes, and when it goes.
fn announce(stack: Stack<'_>, was_up: &mut bool) -> bool {
    let config = stack.config_v4();
    let up = config.is_some();
    match (config, *was_up) {
        (Some(c), false) => info!("address {} from DHCP: sending to {}", c.address, MOTOR_PI),
        (None, true) => warn!("lost the network address: waiting for DHCP"),
        _ => {}
    }
    *was_up = up;
    up
}

/// The two spoke sensors, every millisecond, counted the 2025-26 way.
#[embassy_executor::task]
async fn sample_spokes(a: Input<'static>, b: Input<'static>) {
    let mut sensors = SpokeSensors::TODAY;
    let mut ticker = Ticker::every(SAMPLE_EVERY);
    loop {
        let count = sensors.update(a.is_high(), b.is_high(), now_ms());
        WHEEL.lock(|wheel| wheel.set(count));
        ticker.next().await;
    }
}

/// The W5500's driver: moves Ethernet frames between the chip and the IP stack.
#[embassy_executor::task]
async fn run_w5500(runner: Runner<'static, W5500, W5500Spi, Input<'static>, Output<'static>>) -> ! {
    runner.run().await
}

/// The IP stack: DHCP, ARP, UDP.
#[embassy_executor::task]
async fn run_net(mut runner: embassy_net::Runner<'static, Device<'static>>) -> ! {
    runner.run().await
}

/// Milliseconds since boot. It wraps after 49 days; only differences matter.
fn now_ms() -> u32 {
    Instant::now().as_millis() as u32
}

/// What the watchdog resets: every part but the two oscillators, as the Pico SDK does.
/// embassy-rp 0.10 writes the RP2040's bits here instead (see `boards/pico2/src/main.rs`).
fn reset_all_but_the_oscillators() {
    let mut parts = pac::psm::regs::Wdsel(0x01FF_FFFF); // bits 0 to 24: every part
    parts.set_rosc(false);
    parts.set_xosc(false);
    pac::PSM.wdsel().write_value(parts);
}
