//! spine_sim: the spine, on a laptop (bench mode).
//!
//! The firmware's real logic (spine-core) runs here on the CAN frames spine_bridge sends,
//! and drives a model of the car instead of motors. It answers with the frames the real
//! spine sends, so nothing above it can tell the difference.
//!
//! Subscribes  /to_can_bus            can_msgs/Frame    what spine_bridge puts on the bus
//!             /bench/hw_estop        std_msgs/Bool     true = the hardware e-stop is pressed
//!             /bench/driver_faults   std_msgs/UInt16   pretend a driver failed (fault bits)
//! Publishes   /from_can_bus          can_msgs/Frame    VEHICLE_FEEDBACK 50 Hz, VEHICLE_STATUS 10 Hz
//!             /bench/truth           nav_msgs/Odometry where the model car really is (map
//!                                                      frame, 50 Hz), for the pretend sensors
//! Parameters  wheelbase (m), max_steering (rad), start_x, start_y (m), start_yaw (rad)
//!
//! A thread runs the spine at 100 Hz, like the board's main loop; the main thread spins.

use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

use anyhow::{bail, Result};
use bench_car::{Bench, PlantConfig, Pose};
use rclrs::*;
use ros_env::builtin_interfaces::msg::Time;
use ros_env::can_msgs::msg::Frame;
use ros_env::nav_msgs::msg::Odometry;
use ros_env::std_msgs::msg::{Bool, UInt16};

/// The spine's tick, as on the board (ms).
const TICK_MS: u32 = 10;

fn main() -> Result<()> {
    let context = Context::default_from_env()?;
    let mut executor = context.create_basic_executor();
    let node = executor.create_node("spine_sim")?;

    let param = |name: &str, default: f64| -> Result<f64> {
        Ok(node
            .declare_parameter(name)
            .default(default)
            .read_only()?
            .get())
    };
    let plant = PlantConfig {
        wheelbase: param("wheelbase", 1.57)? as f32,
        max_steering: param("max_steering", 0.5)? as f32,
        ..PlantConfig::default()
    };
    let start = Pose {
        x: param("start_x", 0.0)?,
        y: param("start_y", 0.0)?,
        yaw: param("start_yaw", 0.0)?,
        ..Pose::default()
    };
    let bench = Arc::new(Mutex::new(Bench::new(Default::default(), plant, start)));
    log_info!(
        node.logger(),
        "The spine's firmware logic, driving a model car (wheelbase {} m). Arm it with \
         /spine/arm, as on the real car.",
        plant.wheelbase
    );

    let _frames_in = {
        let bench = Arc::clone(&bench);
        node.create_subscription::<Frame, _>("/to_can_bus", move |f: Frame| {
            if !f.is_extended && !f.is_rtr && !f.is_error && f.id <= 0x7FF {
                let len = (f.dlc as usize).min(8);
                bench.lock().unwrap().receive(f.id as u16, &f.data[..len]);
            }
        })?
    };
    let _estop = {
        let bench = Arc::clone(&bench);
        node.create_subscription::<Bool, _>("/bench/hw_estop", move |m: Bool| {
            bench.lock().unwrap().set_hw_estop(m.data);
        })?
    };
    let _faults = {
        let bench = Arc::clone(&bench);
        node.create_subscription::<UInt16, _>("/bench/driver_faults", move |m: UInt16| {
            bench.lock().unwrap().set_driver_faults(m.data);
        })?
    };
    let frames_out = node.create_publisher::<Frame>("/from_can_bus")?;
    let truth = node.create_publisher::<Odometry>("/bench/truth")?;

    let running = Arc::new(AtomicBool::new(true));
    let commands = Arc::clone(executor.commands());
    {
        let running = Arc::clone(&running);
        let commands = Arc::clone(&commands);
        ctrlc::set_handler(move || {
            running.store(false, Ordering::SeqCst);
            commands.halt_spinning();
        })?;
    }

    let spine_loop = {
        let node = Arc::clone(&node);
        let running = Arc::clone(&running);
        thread::spawn(move || -> Result<()> {
            let clock = node.get_clock();
            let period = Duration::from_millis(TICK_MS as u64);
            let mut next = Instant::now() + period;
            let mut ticks: u64 = 0;
            while running.load(Ordering::SeqCst) {
                let (frames, pose) = {
                    let mut b = bench.lock().unwrap();
                    (b.tick(TICK_MS), b.pose())
                };
                let stamp = clock.now().to_ros_msg().unwrap_or_default();
                for (id, data) in frames {
                    frames_out.publish(frame(id, data, stamp.clone()))?;
                }
                ticks += 1;
                if ticks % 2 == 0 {
                    truth.publish(odometry(&pose, stamp))?;
                }
                // Keep a steady 100 Hz; if a tick runs late, don't try to catch up.
                let now = Instant::now();
                if next > now {
                    thread::sleep(next - now);
                    next += period;
                } else {
                    next = now + period;
                }
            }
            commands.halt_spinning();
            Ok(())
        })
    };

    executor.spin(SpinOptions::default()).first_error()?;
    running.store(false, Ordering::SeqCst);
    match spine_loop.join() {
        Ok(result) => result,
        Err(_) => bail!("the spine loop panicked"),
    }
}

fn frame(id: u16, data: [u8; 8], stamp: Time) -> Frame {
    let mut f = Frame::default();
    f.header.stamp = stamp;
    f.id = id as u32;
    f.dlc = 8;
    f.data = data;
    f
}

fn odometry(p: &Pose, stamp: Time) -> Odometry {
    let mut o = Odometry::default();
    o.header.stamp = stamp;
    o.header.frame_id = "map".into();
    o.child_frame_id = "base_link".into();
    o.pose.pose.position.x = p.x;
    o.pose.pose.position.y = p.y;
    o.pose.pose.orientation.z = (p.yaw / 2.0).sin();
    o.pose.pose.orientation.w = (p.yaw / 2.0).cos();
    o.twist.twist.linear.x = p.speed as f64;
    o.twist.twist.angular.z = p.yaw_rate as f64;
    o
}
