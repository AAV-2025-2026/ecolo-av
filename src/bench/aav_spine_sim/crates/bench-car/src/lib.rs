//! The bench car: the spine's real logic (spine-core) driving a simple model of the car.
//!
//! Bench mode runs the whole car's software on a laptop. This crate is the bottom of it:
//! where the spine board and the actuators will be. No ROS here, so the tests run anywhere:
//! `cargo test -p bench-car`.
//!
//! The same spine can drive a car measured elsewhere instead of the model ([`MeasuredCar`]):
//! Gazebo's, in the simulator's spine profile (sim.launch.py spine:=true).

pub mod bench;
pub mod car;
pub mod plant;

pub use bench::{
    Bench, Frame, BENCH_WHEELS, FEEDBACK_PERIOD_MS, STATUS_PERIOD_MS, WHEEL_PERIOD_MS,
};
pub use car::{Car, MeasuredCar};
pub use plant::{Plant, PlantConfig, Pose};
