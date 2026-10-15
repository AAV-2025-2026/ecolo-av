//! The bench car: the spine's real logic (spine-core) driving a simple model of the car.
//!
//! Bench mode runs the whole car's software on a laptop. This crate is the bottom of it:
//! where the spine board and the actuators will be. No ROS here, so the tests run anywhere:
//! `cargo test -p bench-car`.

pub mod bench;
pub mod plant;

pub use bench::{
    Bench, Frame, BENCH_WHEELS, FEEDBACK_PERIOD_MS, STATUS_PERIOD_MS, WHEEL_PERIOD_MS,
};
pub use plant::{Plant, PlantConfig, Pose};
