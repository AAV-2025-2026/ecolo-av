//! A first rclrs node: prints what ego tells the car to do.
//!
//! Subscribes  /ego/actuator_cmd  ackermann_msgs/AckermannDriveStamped
//!
//! Run it next to the turtle profile: `pixi run rust-listener` (see README.md).

use anyhow::Result;
use rclrs::*;
use ros_env::ackermann_msgs::msg::AckermannDriveStamped;

fn main() -> Result<()> {
    let context = Context::default_from_env()?;
    let mut executor = context.create_basic_executor();
    let node = executor.create_node("rust_listener")?;

    let _subscription = node.create_subscription::<AckermannDriveStamped, _>(
        "/ego/actuator_cmd",
        |msg: AckermannDriveStamped| {
            println!(
                "ego: speed {:+.2} m/s, steering {:+.3} rad",
                msg.drive.speed, msg.drive.steering_angle
            );
        },
    )?;

    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
