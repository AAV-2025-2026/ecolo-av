//! The map window's logic, with no ROS and no raylib, so it is tested on any laptop.
//!
//! The map window (`map`, in hud-app's workspace) is the big screen's program: Nav2's
//! map, the car on it, the planned path and the goal, and how far is left.
//!
//! | Module | What it holds |
//! |---|---|
//! | [`config`] | the topic names, from `config/map.yaml` |
//! | [`geom`] | points and poses in the map frame (metres, radians) |
//! | [`grid`] | Nav2's occupancy grid, and its pixels for the screen |
//! | [`route`] | the planned path: the nearest point to the car, the distance left |
//! | [`car`] | the car's outline, from `vehicle.yaml` |
//! | [`view`] | map to screen and back: follow the car, the whole map, zoom, the scale bar |
//! | [`trip`] | NO GOAL, DRIVING, ARRIVED... and the time left |
//! | [`state`] | everything above, as one value the screen draws |

pub mod car;
pub mod config;
pub mod geom;
pub mod grid;
pub mod route;
pub mod state;
pub mod trip;
pub mod view;
