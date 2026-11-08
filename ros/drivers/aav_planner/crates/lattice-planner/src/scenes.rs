//! Hand-made maps for the tests and `examples/scenes.rs`: our car, our lattice file and
//! nav2.yaml's global costmap (0.25 m cells, 3 m of inflation at scaling 1.0).

use costmap::cost::LETHAL;
use costmap::{footprint, Grid, Inflation};

use crate::{Lattice, Planner, Pose, Settings};

/// vehicle.yaml's body (2.0 m x 1.0 m, the rear axle 0.2 m from the back), as
/// `vehicle.footprint_points` gives it.
pub const CAR: [(f64, f64); 4] = [(1.8, 0.5), (1.8, -0.5), (-0.2, -0.5), (-0.2, 0.5)];
/// nav2.yaml's global costmap.
pub const PADDING: f64 = 0.05;
pub const RESOLUTION: f64 = 0.25;
pub const INFLATION_RADIUS: f64 = 3.0;
pub const COST_SCALING: f64 = 1.0;

/// Our lattice file (aav_navigation's config/lattice_ackermann.json).
pub fn lattice() -> Lattice {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../aav_navigation/config/lattice_ackermann.json"
    );
    let text = std::fs::read_to_string(path).expect("aav_navigation's lattice file");
    Lattice::parse(&text).expect("a good lattice file")
}

pub fn outline() -> Vec<(f64, f64)> {
    footprint::padded(&CAR, PADDING)
}

pub fn inflation() -> Inflation {
    Inflation {
        inflation_radius: INFLATION_RADIUS,
        cost_scaling_factor: COST_SCALING,
        inscribed_radius: footprint::radii(&outline()).0,
    }
}

/// A planner as navigation.launch.py starts ours.
pub fn planner(reversing: bool) -> Planner {
    let settings = Settings {
        allow_reverse: reversing,
        ..Settings::default()
    };
    Planner::new(lattice(), settings, &outline(), Some(&inflation()))
}

/// One scene: a map, a start, a goal, and whether a path must exist with and without
/// reversing.
pub struct Scene {
    pub name: &'static str,
    pub grid: Grid,
    pub start: Pose,
    pub goal: Pose,
    pub forward_ok: bool,
    pub reverse_ok: bool,
}

/// An empty map, `w` x `h` m, origin at (0, 0).
fn open(w: f64, h: f64) -> Grid {
    Grid::new(
        (0.0, 0.0),
        RESOLUTION,
        (w / RESOLUTION) as usize,
        (h / RESOLUTION) as usize,
        0,
    )
}

/// Mark a box (m) lethal.
fn wall(grid: &mut Grid, x0: f64, y0: f64, x1: f64, y1: f64) {
    let r = grid.resolution;
    for cy in (y0 / r) as usize..(y1 / r).ceil() as usize {
        for cx in (x0 / r) as usize..(x1 / r).ceil() as usize {
            if cx < grid.width && cy < grid.height {
                grid.set(cx, cy, LETHAL);
            }
        }
    }
}

fn inflated(mut grid: Grid) -> Grid {
    inflation().apply(&mut grid);
    grid
}

/// The scenes.
pub fn all() -> Vec<Scene> {
    let mut out = Vec::new();

    out.push(Scene {
        name: "straight",
        grid: inflated(open(40.0, 20.0)),
        start: Pose::new(5.0, 10.0, 0.0),
        goal: Pose::new(30.0, 10.0, 0.0),
        forward_ok: true,
        reverse_ok: true,
    });

    out.push(Scene {
        name: "u-turn",
        grid: inflated(open(40.0, 30.0)),
        start: Pose::new(15.0, 12.0, 0.0),
        goal: Pose::new(15.0, 18.0, std::f64::consts::PI),
        forward_ok: true,
        reverse_ok: true,
    });

    // A U-turn in an 8 m road (walls each side): too narrow to turn forward, so only a
    // three-point turn (reversing) gets round.
    let mut road = open(60.0, 20.0);
    wall(&mut road, 0.0, 0.0, 60.0, 6.0);
    wall(&mut road, 0.0, 14.0, 60.0, 20.0);
    out.push(Scene {
        name: "u-turn in a road",
        grid: inflated(road),
        start: Pose::new(20.0, 8.5, 0.0),
        goal: Pose::new(20.0, 11.5, std::f64::consts::PI),
        forward_ok: false,
        reverse_ok: true,
    });

    // Parked nose-in between two cars, a wall ahead: only reversing gets out.
    let mut lot = open(30.0, 30.0);
    wall(&mut lot, 10.0, 6.0, 15.0, 8.4); // the car on the right
    wall(&mut lot, 10.0, 11.6, 15.0, 14.0); // the car on the left
    wall(&mut lot, 15.0, 5.0, 16.0, 15.0); // the wall ahead
    out.push(Scene {
        name: "parking-lot exit",
        grid: inflated(lot),
        start: Pose::new(12.0, 10.0, 0.0),
        goal: Pose::new(4.0, 22.0, std::f64::consts::FRAC_PI_2),
        forward_ok: false,
        reverse_ok: true,
    });

    // A wall across with a 2.5 m gap: through it.
    let mut gap = open(40.0, 30.0);
    wall(&mut gap, 19.0, 0.0, 21.0, 13.75);
    wall(&mut gap, 19.0, 16.25, 21.0, 30.0);
    out.push(Scene {
        name: "narrow gap",
        grid: inflated(gap),
        start: Pose::new(8.0, 15.0, 0.0),
        goal: Pose::new(32.0, 15.0, 0.0),
        forward_ok: true,
        reverse_ok: true,
    });

    // The same wall with a 1.0 m gap: the car (1.1 m wide padded) can't pass.
    let mut shut = open(40.0, 30.0);
    wall(&mut shut, 19.0, 0.0, 21.0, 14.5);
    wall(&mut shut, 19.0, 15.5, 21.0, 30.0);
    out.push(Scene {
        name: "no path",
        grid: inflated(shut),
        start: Pose::new(8.0, 15.0, 0.0),
        goal: Pose::new(32.0, 15.0, 0.0),
        forward_ok: false,
        reverse_ok: false,
    });
    out
}
