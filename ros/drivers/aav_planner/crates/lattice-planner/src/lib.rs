//! Our own path planner: Nav2's Smac State Lattice planner, ported to Rust (no ROS).
//!
//! Given a costmap (the `costmap` crate's `Grid`), the car's outline and our lattice
//! primitives file, `Planner::plan` finds a path a car can drive from a start pose to a
//! goal pose: A* over the moves in the file (forward, and backward if allowed), finishing
//! with a Reeds-Shepp or Dubins curve when one is clear, then smoothed. The costs and
//! penalties are nav2.yaml's (`Settings::default`). PROVENANCE.md says what came from
//! where and what changed.
//!
//! ```text
//! start ─▶ search (search.rs) ─▶ curve to the goal (curves.rs) ─▶ smoother (smoother.rs) ─▶ path
//!            │  moves: lattice.rs        fits?: collision.rs        how far?: heuristic.rs
//! ```

pub mod collision;
pub mod curves;
pub mod heuristic;
pub mod lattice;
pub mod scenes;
pub mod search;
pub mod smoother;

use std::time::Instant;

use costmap::{footprint, Grid, Inflation};

pub use collision::Checker;
pub use curves::CurveKind;
pub use lattice::Lattice;
pub use smoother::SmootherSettings;

use heuristic::DistanceTable;
use search::Search;

/// A pose: x, y (m or cells), yaw (rad).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Pose {
    pub x: f64,
    pub y: f64,
    pub yaw: f64,
}

impl Pose {
    pub const fn new(x: f64, y: f64, yaw: f64) -> Self {
        Self { x, y, yaw }
    }
}

/// The planner's settings: nav2.yaml's `Lattice` block (the defaults are its values).
#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    /// The car may reverse (reversing:=true): Reeds-Shepp curves and backward moves.
    pub allow_reverse: bool,
    /// Unknown cells may be driven through.
    pub allow_unknown: bool,
    /// m: a path ending this close to the goal will do, if the goal can't be reached.
    pub tolerance: f64,
    pub max_iterations: usize,
    /// Iterations to keep looking once within the tolerance.
    pub max_on_approach_iterations: usize,
    /// s.
    pub max_planning_time: f64,
    /// Iterations between checks of the clock and of a cancel.
    pub terminal_checking_interval: usize,
    pub reverse_penalty: f64,
    pub change_penalty: f64,
    pub non_straight_penalty: f64,
    pub cost_penalty: f64,
    pub retrospective_penalty: f64,
    pub rotation_penalty: f64,
    pub analytic_expansion_ratio: f64,
    /// m.
    pub analytic_expansion_max_length: f64,
    pub analytic_expansion_max_cost: f64,
    pub analytic_expansion_max_cost_override: bool,
    /// m: the side of the curve-length table round the goal.
    pub lookup_table_size: f64,
    pub smooth_path: bool,
    pub smoother: SmootherSettings,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            allow_reverse: false,
            allow_unknown: true,
            tolerance: 0.5,
            max_iterations: 1_000_000,
            max_on_approach_iterations: 1000,
            max_planning_time: 5.0,
            terminal_checking_interval: 5000,
            reverse_penalty: 2.0,
            change_penalty: 0.05,
            non_straight_penalty: 1.05,
            cost_penalty: 2.0,
            retrospective_penalty: 0.015,
            rotation_penalty: 5.0,
            analytic_expansion_ratio: 3.5,
            analytic_expansion_max_length: 3.0,
            analytic_expansion_max_cost: 200.0,
            analytic_expansion_max_cost_override: false,
            lookup_table_size: 20.0,
            smooth_path: true,
            smoother: SmootherSettings::default(),
        }
    }
}

/// Why there is no path (Nav2's `ComputePathToPose` error codes).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PlanError {
    StartOutsideMap,
    GoalOutsideMap,
    StartOccupied,
    GoalOccupied,
    /// Out of time or iterations.
    Timeout,
    NoValidPath,
    Cancelled,
    /// The costmap's cells aren't the primitives file's.
    WrongResolution,
}

impl std::fmt::Display for PlanError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let text = match self {
            Self::StartOutsideMap => "the start is off the costmap",
            Self::GoalOutsideMap => "the goal is off the costmap",
            Self::StartOccupied => "the car doesn't fit at the start",
            Self::GoalOccupied => "the car doesn't fit at the goal",
            Self::Timeout => "out of time or iterations",
            Self::NoValidPath => "no path",
            Self::Cancelled => "cancelled",
            Self::WrongResolution => "the costmap's cells aren't the lattice file's",
        };
        f.write_str(text)
    }
}

impl std::error::Error for PlanError {}

/// A path found.
#[derive(Debug, Clone)]
pub struct Plan {
    /// World poses (m, rad), start first. The car faces `yaw`: on a reversing stretch the
    /// path runs behind it.
    pub poses: Vec<Pose>,
    /// The search's poses, before smoothing.
    pub raw: Vec<Pose>,
    pub iterations: usize,
    /// s of wall time: the search, and the whole plan with smoothing.
    pub search_time: f64,
    pub total_time: f64,
}

/// The planner: the lattice, the car, and the tables built once.
pub struct Planner {
    lattice: Lattice,
    settings: Settings,
    checker: Checker,
    distances: DistanceTable,
    kind: CurveKind,
}

impl Planner {
    /// `outline`: the car's footprint (m, base_link), already padded. `inflation`: the
    /// costmap's inflation settings (its cost at the circumscribed radius lets most poses
    /// skip the outline check); None if the costmap has none.
    pub fn new(
        lattice: Lattice,
        settings: Settings,
        outline: &[(f64, f64)],
        inflation: Option<&Inflation>,
    ) -> Self {
        let possible = inflation.and_then(|i| {
            let (_, circumscribed) = footprint::radii(outline);
            (i.inflation_radius >= circumscribed)
                .then(|| i.cost(circumscribed / lattice.resolution, lattice.resolution))
        });
        let checker = Checker::new(outline, possible, settings.allow_unknown);
        let kind = if settings.allow_reverse {
            CurveKind::ReedsShepp
        } else {
            CurveKind::Dubins
        };
        let radius = lattice.turning_radius / lattice.resolution;
        let cells = (settings.lookup_table_size / lattice.resolution) as usize;
        let distances = DistanceTable::new(kind, radius, &lattice.headings, cells);
        Self {
            lattice,
            settings,
            checker,
            distances,
            kind,
        }
    }

    pub fn settings(&self) -> &Settings {
        &self.settings
    }

    pub fn lattice(&self) -> &Lattice {
        &self.lattice
    }

    /// Plan from `start` to `goal` (world poses on `grid`'s frame). `cancelled` is asked
    /// now and then; true stops the search.
    pub fn plan(
        &self,
        grid: &Grid,
        start: &Pose,
        goal: &Pose,
        cancelled: &dyn Fn() -> bool,
    ) -> Result<Plan, PlanError> {
        let began = Instant::now();
        if (grid.resolution - self.lattice.resolution).abs() > 1e-6 {
            return Err(PlanError::WrongResolution);
        }
        let to_cells = |p: &Pose| {
            (
                (p.x - grid.origin_x) / grid.resolution,
                (p.y - grid.origin_y) / grid.resolution,
            )
        };
        let inside = |(x, y): (f64, f64)| {
            x >= 0.0 && y >= 0.0 && x < grid.width as f64 && y < grid.height as f64
        };
        let (sx, sy) = to_cells(start);
        if !inside((sx, sy)) {
            return Err(PlanError::StartOutsideMap);
        }
        let (gx, gy) = to_cells(goal);
        if !inside((gx, gy)) {
            return Err(PlanError::GoalOutsideMap);
        }
        // Start and goal in the same cell: the start, facing the goal's way (as Nav2).
        if sx.floor() == gx.floor() && sy.floor() == gy.floor() {
            let only = vec![Pose::new(start.x, start.y, goal.yaw)];
            return Ok(Plan {
                poses: only.clone(),
                raw: only,
                iterations: 0,
                search_time: 0.0,
                total_time: began.elapsed().as_secs_f64(),
            });
        }
        let search = Search {
            lattice: &self.lattice,
            settings: &self.settings,
            checker: &self.checker,
            distances: &self.distances,
            kind: self.kind,
        };
        let found = search.run(
            grid,
            (sx, sy, self.lattice.nearest_heading(start.yaw)),
            (gx, gy, self.lattice.nearest_heading(goal.yaw)),
            cancelled,
        )?;
        let mut raw: Vec<Pose> = Vec::with_capacity(found.poses.len());
        for p in &found.poses {
            let w = Pose::new(
                grid.origin_x + p.x * grid.resolution,
                grid.origin_y + p.y * grid.resolution,
                p.yaw,
            );
            // Drop repeats (Nav2 does too).
            if raw.last().is_some_and(|l: &Pose| {
                (l.x - w.x).abs() < 1e-4
                    && (l.y - w.y).abs() < 1e-4
                    && curves::wrap(l.yaw - w.yaw).abs() < 1e-4
            }) {
                continue;
            }
            raw.push(w);
        }
        let search_time = began.elapsed().as_secs_f64();
        let mut poses = raw.clone();
        if self.settings.smooth_path && found.iterations > 1 {
            let left = self.settings.max_planning_time - search_time;
            smoother::smooth(
                &mut poses,
                grid,
                self.lattice.turning_radius,
                &self.settings.smoother,
                left,
            );
        }
        Ok(Plan {
            poses,
            raw,
            iterations: found.iterations,
            search_time,
            total_time: began.elapsed().as_secs_f64(),
        })
    }
}

/// A path's length, m.
pub fn length(poses: &[Pose]) -> f64 {
    poses
        .windows(2)
        .map(|w| (w[1].x - w[0].x).hypot(w[1].y - w[0].y))
        .sum()
}

/// The tightest turn along a path, as a radius in m: from each three poses about `span`
/// m apart, within each stretch between changes of direction (infinite if straight).
pub fn tightest_turn(poses: &[Pose], span: f64) -> f64 {
    let mut cuts = vec![0];
    cuts.extend((1..poses.len().saturating_sub(1)).filter(|&i| {
        let (a, b, c) = (&poses[i - 1], &poses[i], &poses[i + 1]);
        (b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y) < 0.0
    }));
    cuts.push(poses.len().saturating_sub(1));
    cuts.windows(2)
        .map(|w| tightest_in(&poses[w[0]..=w[1]], span))
        .fold(f64::INFINITY, f64::min)
}

fn tightest_in(poses: &[Pose], span: f64) -> f64 {
    // The index about `span` m along from `from`, and whether there was that far to go.
    let ahead = |from: usize| {
        let mut d = 0.0;
        let mut j = from;
        while j + 1 < poses.len() && d < span {
            d += (poses[j + 1].x - poses[j].x).hypot(poses[j + 1].y - poses[j].y);
            j += 1;
        }
        (j, d >= span)
    };
    let mut tightest = f64::INFINITY;
    for i in 0..poses.len() {
        let (j, far1) = ahead(i);
        let (k, far2) = ahead(j);
        if !(far1 && far2) {
            break;
        }
        let (a, b, c) = (poses[i], poses[j], poses[k]);
        let ab = (b.x - a.x).hypot(b.y - a.y);
        let bc = (c.x - b.x).hypot(c.y - b.y);
        let ca = (a.x - c.x).hypot(a.y - c.y);
        let cross = ((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)).abs();
        if cross > 1e-9 {
            tightest = tightest.min(ab * bc * ca / (2.0 * cross));
        }
    }
    tightest
}

/// How many times a path changes direction (forward to reverse or back).
pub fn cusps(poses: &[Pose]) -> usize {
    poses
        .windows(3)
        .filter(|w| {
            (w[1].x - w[0].x) * (w[2].x - w[1].x) + (w[1].y - w[0].y) * (w[2].y - w[1].y) < 0.0
        })
        .count()
}
