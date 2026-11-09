//! Our own navigator: what Nav2's bt_navigator and waypoint_follower do for the car, as a
//! plain state machine. No ROS: the node (`navigator-node`) feeds it events and carries
//! out the commands it returns.
//!
//! ```text
//! goal ─▶ plan ─▶ follow ─▶ replan every second (keep the path on the final approach)
//!           │        │
//!           ▼        ▼  a failure Nav2 would recover from
//!   clear global  clear local, follow again
//!           └────────┴─▶ recoveries in turn: clear both costmaps, wait, back up
//!                        (up to 6), then give up
//! ```
//!
//! It follows our behaviour trees (`aav_navigation/behavior_trees/*_car*.xml`), with a
//! few changes, each in PROVENANCE.md:
//! - a failed replan while a good path is being followed doesn't stop the car: it tries
//!   again next period, and only gives up after `replan_failures` in a row;
//! - through-poses drops a pose once the car has passed it along the path, not only
//!   within 1 m of it (a car cutting a bend by 1.5 m never came back for it);
//! - waypoints (and GPS waypoints) run as one through-poses goal by default: no stop
//!   and no turn to face at each one (TODO 140's bends). `WaypointMode::StopAtEach` is
//!   Nav2's way;
//! - the final approach keeps its path on the last leg of a through-poses goal too.

mod machine;
pub mod path;

pub use machine::{Navigator, Progress};

/// A pose in the map frame: metres, radians (REP-103: x forward, yaw counter-clockwise).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Pose {
    pub x: f64,
    pub y: f64,
    pub yaw: f64,
}

impl Pose {
    pub const fn new(x: f64, y: f64, yaw: f64) -> Self {
        Self { x, y, yaw }
    }

    /// Straight-line distance, m.
    pub fn distance(&self, other: &Pose) -> f64 {
        (self.x - other.x).hypot(self.y - other.y)
    }
}

/// What a goal asks for.
#[derive(Debug, Clone, PartialEq)]
pub enum Mission {
    /// `navigate_to_pose`: drive to one pose.
    ToPose(Pose),
    /// `navigate_through_poses`: one path through each pose in turn.
    ThroughPoses(Vec<Pose>),
    /// `follow_waypoints`, and `follow_gps_waypoints` once on the map: as
    /// [`Settings::waypoints`] says.
    Waypoints(Vec<Pose>),
}

/// How waypoints are driven.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WaypointMode {
    /// One through-poses goal: the car passes each waypoint without stopping (ours).
    PassThrough,
    /// Nav2's waypoint_follower: a to-pose goal per waypoint, stopping at each.
    StopAtEach,
}

/// Backing up, one of the recoveries (only where the car may reverse).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BackUp {
    /// m.
    pub distance: f64,
    /// m/s, positive.
    pub speed: f64,
}

/// The navigator's numbers. The defaults are our behaviour trees' and nav2.yaml's.
#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    /// s between plans for a to-pose goal (the trees' RateController, 1 Hz).
    pub replan_period: f64,
    /// s between plans for through-poses (0.333 Hz).
    pub through_replan_period: f64,
    /// m: within this of the goal the path is kept, not replanned (vehicle.final_approach).
    pub final_approach: f64,
    /// m: ... as long as the path still ends this close to the goal ...
    pub path_end_tolerance: f64,
    /// s: ... and is younger than this.
    pub path_max_age: f64,
    /// Recoveries before giving up (the outer RecoveryNode's retries).
    pub retries: u32,
    /// s: the Wait recovery.
    pub wait: f64,
    /// The BackUp recovery; None: forward only (the car's default).
    pub backup: Option<BackUp>,
    /// m: a through-pose this close to the car is passed (RemovePassedGoals' radius).
    pub pass_radius: f64,
    /// m: a through-pose counts as on the path within this (to be passed along it).
    pub on_path: f64,
    pub waypoints: WaypointMode,
    /// StopAtEach: a waypoint that fails ends the goal (waypoint_follower's own flag).
    pub stop_on_failure: bool,
    /// Failed replans in a row tolerated while a path is followed (ours; Nav2's tree: 0).
    pub replan_failures: u32,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            replan_period: 1.0,
            through_replan_period: 3.0,
            final_approach: 8.0,
            path_end_tolerance: 0.5,
            path_max_age: 20.0,
            retries: 6,
            wait: 5.0,
            backup: None,
            pass_radius: 1.0,
            on_path: 2.0,
            waypoints: WaypointMode::PassThrough,
            stop_on_failure: false,
            replan_failures: 3,
        }
    }
}

/// A request's number: an answer carries it back, so a late answer is known as late.
pub type Token = u64;

/// Why a step failed: Nav2's error codes, as the planner and follower send them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Failure {
    /// ComputePathToPose (200s) or ComputePathThroughPoses (300s).
    Plan { code: u16, message: String },
    /// FollowPath (100s).
    Follow { code: u16, message: String },
}

impl Failure {
    /// Nav2's error code.
    pub fn code(&self) -> u16 {
        match self {
            Self::Plan { code, .. } | Self::Follow { code, .. } => *code,
        }
    }

    pub fn message(&self) -> &str {
        match self {
            Self::Plan { message, .. } | Self::Follow { message, .. } => message,
        }
    }

    /// WouldAPlannerRecoveryHelp: unknown, no valid path, timeout (to-pose and through);
    /// and ours: the start occupied (205, 305). On the campus the lidar's marks beside a
    /// lot exit made the car's own spot "occupied" (8 Nov); clearing the global costmap
    /// forgets them, and the lidar marks again only what it still sees.
    pub fn planner_recovery_helps(&self) -> bool {
        matches!(self, Self::Plan { code, .. }
            if matches!(code, 200 | 205 | 207 | 208 | 300 | 305 | 307 | 308))
    }

    /// WouldAControllerRecoveryHelp: unknown, patience exceeded, no progress, no valid
    /// control.
    pub fn controller_recovery_helps(&self) -> bool {
        matches!(self, Self::Follow { code, .. } if matches!(code, 100 | 104 | 105 | 106))
    }

    /// Either: the outer recovery runs only then.
    pub fn recovery_helps(&self) -> bool {
        self.planner_recovery_helps() || self.controller_recovery_helps()
    }
}

impl std::fmt::Display for Failure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let (who, code, message) = match self {
            Self::Plan { code, message } => ("the planner", code, message),
            Self::Follow { code, message } => ("the follower", code, message),
        };
        if message.is_empty() {
            write!(f, "{who} failed (error {code})")
        } else {
            write!(f, "{who} failed (error {code}): {message}")
        }
    }
}

/// How a goal ended.
#[derive(Debug, Clone, PartialEq)]
pub enum Outcome {
    /// There (waypoints: `missed` holds those not reached, by index).
    Succeeded {
        missed: Vec<usize>,
    },
    /// Given up. `code`: Nav2's code from the step that failed (0: none, such as an empty
    /// goal or a newer goal in its place).
    Aborted {
        code: u16,
        message: String,
        missed: Vec<usize>,
    },
    Cancelled,
}

/// What the node must do.
#[derive(Debug, Clone, PartialEq)]
pub enum Command {
    /// Ask the planner for a path from the car: one goal, ComputePathToPose; more,
    /// ComputePathThroughPoses. Answer with [`Navigator::planned`].
    Plan { token: Token, goals: Vec<Pose> },
    /// Send the follower this path (FollowPath; it replaces the one before without a
    /// stop). Answer with [`Navigator::followed`].
    Follow { token: Token, path: Vec<Pose> },
    /// Cancel the follower's goal: the car stops.
    StopFollowing,
    /// Clear costmaps. Answer with [`Navigator::recovered`].
    Clear {
        token: Token,
        local: bool,
        global: bool,
    },
    /// Back up. Answer with [`Navigator::recovered`].
    BackUp {
        token: Token,
        distance: f64,
        speed: f64,
    },
    /// The goal `id` ended.
    Finished { id: u64, outcome: Outcome },
}
