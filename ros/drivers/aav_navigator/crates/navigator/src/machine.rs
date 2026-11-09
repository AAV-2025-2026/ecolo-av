//! The goal state machine: one goal at a time.

use crate::path;
use crate::{Command, Failure, Mission, Outcome, Pose, Settings, Token, WaypointMode};

/// How the active goal is driven.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Kind {
    /// One pose (navigate_to_pose).
    ToPose,
    /// One path through the poses left (navigate_through_poses; waypoints, PassThrough).
    Through,
    /// A to-pose goal per waypoint (waypoints, StopAtEach).
    EachInTurn,
}

/// One of the outer recoveries, taken in turn (the trees' RoundRobin).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Recovery {
    ClearBoth,
    Wait,
    BackUp,
}

#[derive(Debug, Clone, PartialEq)]
enum Stage {
    /// Planning and following.
    Driving,
    /// Clearing the global costmap before planning once more (the planner's own recovery).
    ClearingForPlan(Token),
    /// Clearing the local costmap before following once more (the follower's own).
    ClearingForFollow(Token),
    /// An outer recovery: until its answer (token) or a time (Wait).
    Recovering {
        token: Option<Token>,
        until: Option<f64>,
    },
}

/// The path being followed, and when it was made.
#[derive(Debug, Clone)]
struct Held {
    poses: Vec<Pose>,
    made: f64,
}

#[derive(Debug, Clone)]
struct Active {
    id: u64,
    kind: Kind,
    /// Through: the poses still ahead. ToPose and EachInTurn: every pose given.
    targets: Vec<Pose>,
    /// EachInTurn: the waypoint driven to now. Through: how many have been passed.
    index: usize,
    total: usize,
    missed: Vec<usize>,
    started: f64,
    stage: Stage,
    path: Option<Held>,
    /// A plan asked for and not answered yet.
    plan: Option<Token>,
    last_plan: Option<f64>,
    plan_retry_used: bool,
    replans_failed: u32,
    /// The follower's goal now, if it is driving.
    following: Option<Token>,
    follow_retry_used: bool,
    recoveries: u32,
    next_recovery: usize,
}

impl Active {
    /// The poses the planner must reach next.
    fn goals(&self) -> Vec<Pose> {
        match self.kind {
            Kind::Through => self.targets.clone(),
            Kind::ToPose => vec![self.targets[0]],
            Kind::EachInTurn => vec![self.targets[self.index]],
        }
    }

    /// Where this leg ends.
    fn end(&self) -> Pose {
        match self.kind {
            Kind::EachInTurn => self.targets[self.index],
            _ => *self.targets.last().expect("a goal has a pose"),
        }
    }

    /// A fresh start for the next waypoint, or after an outer recovery.
    fn reset_attempt(&mut self) {
        self.stage = Stage::Driving;
        self.path = None;
        self.plan = None;
        self.last_plan = None;
        self.plan_retry_used = false;
        self.replans_failed = 0;
        self.following = None;
        self.follow_retry_used = false;
    }
}

/// How far along a goal is, for its feedback.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Progress {
    /// Goal number, as given to [`Navigator::start`].
    pub id: u64,
    /// m along the path to its end (the straight line with no path yet).
    pub distance_remaining: f64,
    pub recoveries: u32,
    /// Waypoints: the one driven to now (EachInTurn), or how many passed (PassThrough).
    pub waypoint: usize,
    /// Poses still ahead (through-poses' feedback).
    pub poses_remaining: usize,
    /// When it started (the clock given to [`Navigator::start`]).
    pub started: f64,
}

/// Nav2's navigator for the car, as a state machine. Every method returns what the node
/// must do now; times are seconds on any one clock.
#[derive(Debug)]
pub struct Navigator {
    settings: Settings,
    active: Option<Active>,
    tokens: Token,
}

impl Navigator {
    pub fn new(settings: Settings) -> Self {
        Self {
            settings,
            active: None,
            tokens: 0,
        }
    }

    pub fn settings(&self) -> &Settings {
        &self.settings
    }

    /// The goal now, if any.
    pub fn goal(&self) -> Option<u64> {
        self.active.as_ref().map(|a| a.id)
    }

    fn token(&mut self) -> Token {
        self.tokens += 1;
        self.tokens
    }

    /// A new goal. One already running ends as aborted ("replaced"), as Nav2 does when a
    /// goal is preempted; the follower keeps driving until the new path arrives.
    pub fn start(&mut self, id: u64, mission: Mission, now: f64) -> Vec<Command> {
        let mut out = Vec::new();
        if let Some(old) = self.active.take() {
            out.push(Command::Finished {
                id: old.id,
                outcome: Outcome::Aborted {
                    code: 0,
                    message: "replaced by a newer goal".into(),
                    missed: Vec::new(),
                },
            });
        }
        let (kind, targets) = match mission {
            Mission::ToPose(p) => (Kind::ToPose, vec![p]),
            Mission::ThroughPoses(poses) => (Kind::Through, poses),
            Mission::Waypoints(poses) => match self.settings.waypoints {
                WaypointMode::PassThrough => (Kind::Through, poses),
                WaypointMode::StopAtEach => (Kind::EachInTurn, poses),
            },
        };
        if targets.is_empty() || targets.iter().any(|p| !finite(p)) {
            out.push(Command::StopFollowing);
            out.push(Command::Finished {
                id,
                outcome: Outcome::Aborted {
                    code: 0,
                    message: "no poses, or a pose that is not all numbers".into(),
                    missed: Vec::new(),
                },
            });
            return out;
        }
        let total = targets.len();
        self.active = Some(Active {
            id,
            kind,
            targets,
            index: 0,
            total,
            missed: Vec::new(),
            started: now,
            stage: Stage::Driving,
            path: None,
            plan: None,
            last_plan: None,
            plan_retry_used: false,
            replans_failed: 0,
            following: None,
            follow_retry_used: false,
            recoveries: 0,
            next_recovery: 0,
        });
        out
    }

    /// The goal `id` is cancelled: the car stops.
    pub fn cancel(&mut self, id: u64) -> Vec<Command> {
        if self.goal() != Some(id) {
            return Vec::new();
        }
        self.active = None;
        vec![
            Command::StopFollowing,
            Command::Finished {
                id,
                outcome: Outcome::Cancelled,
            },
        ]
    }

    /// The clock moved on; `car` is where the car is on the map, if known.
    pub fn tick(&mut self, now: f64, car: Option<&Pose>) -> Vec<Command> {
        let settings = self.settings.clone();
        let Some(a) = self.active.as_mut() else {
            return Vec::new();
        };
        match a.stage {
            Stage::Recovering {
                until: Some(t),
                token: None,
            } if now >= t => {
                a.reset_attempt();
            }
            Stage::Driving => {}
            _ => return Vec::new(),
        }
        if a.kind == Kind::Through {
            if let Some(car) = car {
                drop_passed(a, car, &settings);
            }
        }
        if a.plan.is_some() {
            return Vec::new();
        }
        let period = if a.kind == Kind::Through {
            settings.through_replan_period
        } else {
            settings.replan_period
        };
        let due = a.last_plan.is_none_or(|t| now - t >= period);
        if !due || keep_path(a, car, now, &settings) {
            return Vec::new();
        }
        let goals = a.goals();
        let token = self.token();
        let a = self.active.as_mut().expect("checked above");
        a.plan = Some(token);
        a.last_plan = Some(now);
        vec![Command::Plan { token, goals }]
    }

    /// The planner's answer to [`Command::Plan`]: a path, or Nav2's error code and why.
    pub fn planned(
        &mut self,
        token: Token,
        answer: Result<Vec<Pose>, (u16, String)>,
        now: f64,
    ) -> Vec<Command> {
        let settings = self.settings.clone();
        let Some(a) = self.active.as_mut() else {
            return Vec::new();
        };
        if a.plan != Some(token) {
            return Vec::new(); // late: a newer plan, goal or recovery took its place
        }
        a.plan = None;
        let answer = match answer {
            Ok(p) if p.is_empty() => Err((208, "the planner sent an empty path".to_string())),
            other => other,
        };
        match answer {
            Ok(poses) => {
                a.plan_retry_used = false;
                a.replans_failed = 0;
                a.path = Some(Held {
                    poses: poses.clone(),
                    made: now,
                });
                let token = self.token();
                let a = self.active.as_mut().expect("checked above");
                a.following = Some(token);
                vec![Command::Follow { token, path: poses }]
            }
            Err((code, message)) => {
                let failure = Failure::Plan { code, message };
                // Ours: a good path is still being followed; try again next period.
                if a.following.is_some() && a.replans_failed < settings.replan_failures {
                    a.replans_failed += 1;
                    return Vec::new();
                }
                if !a.plan_retry_used && failure.planner_recovery_helps() {
                    a.plan_retry_used = true;
                    let token = self.token();
                    let a = self.active.as_mut().expect("checked above");
                    a.stage = Stage::ClearingForPlan(token);
                    return vec![Command::Clear {
                        token,
                        local: false,
                        global: true,
                    }];
                }
                self.attempt_failed(failure, now)
            }
        }
    }

    /// The follower's answer to [`Command::Follow`]: there, or Nav2's error code and why.
    pub fn followed(
        &mut self,
        token: Token,
        answer: Result<(), (u16, String)>,
        now: f64,
    ) -> Vec<Command> {
        let Some(a) = self.active.as_mut() else {
            return Vec::new();
        };
        if a.following != Some(token) {
            return Vec::new(); // replaced by a newer path, or stopped on purpose
        }
        a.following = None;
        match answer {
            Ok(()) => self.arrived(),
            Err((code, message)) => {
                let failure = Failure::Follow { code, message };
                if !a.follow_retry_used && failure.controller_recovery_helps() {
                    if let Some(held) = &a.path {
                        let poses = held.poses.clone();
                        a.follow_retry_used = true;
                        a.plan = None; // a plan answered meanwhile would only race this
                        let token = self.token();
                        let a = self.active.as_mut().expect("checked above");
                        a.stage = Stage::ClearingForFollow(token);
                        // The path to follow again is kept in `path`.
                        a.path = Some(Held {
                            poses,
                            made: a.path.as_ref().map_or(now, |h| h.made),
                        });
                        return vec![Command::Clear {
                            token,
                            local: true,
                            global: false,
                        }];
                    }
                }
                self.attempt_failed(failure, now)
            }
        }
    }

    /// The answer to [`Command::Clear`] or [`Command::BackUp`]. A recovery that failed
    /// still counts; the goal carries on (the next recovery is another kind).
    pub fn recovered(&mut self, token: Token, ok: bool, now: f64) -> Vec<Command> {
        let Some(a) = self.active.as_mut() else {
            return Vec::new();
        };
        match a.stage.clone() {
            Stage::ClearingForPlan(t) if t == token => {
                a.stage = Stage::Driving;
                if !ok {
                    let failure = Failure::Plan {
                        code: 200,
                        message: "clearing the global costmap failed".into(),
                    };
                    return self.attempt_failed(failure, now);
                }
                a.last_plan = None; // plan again at once
                self.tick(now, None)
            }
            Stage::ClearingForFollow(t) if t == token => {
                a.stage = Stage::Driving;
                let Some(held) = a.path.clone() else {
                    return Vec::new();
                };
                let token = self.token();
                let a = self.active.as_mut().expect("checked above");
                a.following = Some(token);
                vec![Command::Follow {
                    token,
                    path: held.poses,
                }]
            }
            Stage::Recovering {
                token: Some(t),
                until: None,
            } if t == token => {
                a.reset_attempt();
                self.tick(now, None)
            }
            _ => Vec::new(),
        }
    }

    /// How far along the goal is.
    pub fn progress(&self, car: Option<&Pose>) -> Option<Progress> {
        let a = self.active.as_ref()?;
        let end = a.end();
        let distance_remaining = match (&a.path, car) {
            (Some(h), Some(c)) => path::remaining(&h.poses, c),
            (None, Some(c)) => c.distance(&end),
            _ => f64::NAN,
        };
        Some(Progress {
            id: a.id,
            distance_remaining,
            recoveries: a.recoveries,
            waypoint: a.index,
            poses_remaining: match a.kind {
                Kind::Through => a.targets.len(),
                Kind::ToPose => 1,
                Kind::EachInTurn => a.total - a.index,
            },
            started: a.started,
        })
    }

    /// The follower says the car is at the end of its path.
    fn arrived(&mut self) -> Vec<Command> {
        let a = self.active.as_mut().expect("called with a goal");
        if a.kind == Kind::EachInTurn && a.index + 1 < a.total {
            a.index += 1;
            a.recoveries = 0;
            a.next_recovery = 0;
            a.reset_attempt();
            return Vec::new();
        }
        let a = self.active.take().expect("called with a goal");
        vec![Command::Finished {
            id: a.id,
            outcome: Outcome::Succeeded { missed: a.missed },
        }]
    }

    /// The plan-and-follow attempt failed: the next recovery, or give up.
    fn attempt_failed(&mut self, failure: Failure, now: f64) -> Vec<Command> {
        let settings = self.settings.clone();
        let mut out = vec![Command::StopFollowing];
        let token = self.token();
        let a = self.active.as_mut().expect("called with a goal");
        a.following = None;
        a.plan = None;
        if !failure.recovery_helps() || a.recoveries >= settings.retries {
            out.extend(self.leg_failed(failure));
            return out;
        }
        a.recoveries += 1;
        let mut turns = vec![Recovery::ClearBoth, Recovery::Wait];
        if settings.backup.is_some() {
            turns.push(Recovery::BackUp);
        }
        let pick = turns[a.next_recovery % turns.len()];
        a.next_recovery += 1;
        match (pick, settings.backup) {
            (Recovery::ClearBoth, _) => {
                a.stage = Stage::Recovering {
                    token: Some(token),
                    until: None,
                };
                out.push(Command::Clear {
                    token,
                    local: true,
                    global: true,
                });
            }
            (Recovery::BackUp, Some(b)) => {
                a.stage = Stage::Recovering {
                    token: Some(token),
                    until: None,
                };
                out.push(Command::BackUp {
                    token,
                    distance: b.distance,
                    speed: b.speed,
                });
            }
            _ => {
                a.stage = Stage::Recovering {
                    token: None,
                    until: Some(now + settings.wait),
                };
            }
        }
        out
    }

    /// No more recoveries for this leg: the goal fails, or (waypoints, each in turn, not
    /// stop_on_failure) the waypoint is missed and the next one starts.
    fn leg_failed(&mut self, failure: Failure) -> Vec<Command> {
        let stop_on_failure = self.settings.stop_on_failure;
        let a = self.active.as_mut().expect("called with a goal");
        if a.kind == Kind::EachInTurn && !stop_on_failure && a.index + 1 < a.total {
            a.missed.push(a.index);
            a.index += 1;
            a.recoveries = 0;
            a.next_recovery = 0;
            a.reset_attempt();
            return Vec::new();
        }
        let a = self.active.take().expect("called with a goal");
        let mut missed = a.missed;
        match a.kind {
            Kind::EachInTurn => missed.push(a.index),
            Kind::Through => missed.extend(a.index..a.total),
            Kind::ToPose => {}
        }
        vec![Command::Finished {
            id: a.id,
            outcome: Outcome::Aborted {
                code: failure.code(),
                message: failure.to_string(),
                missed,
            },
        }]
    }
}

fn finite(p: &Pose) -> bool {
    p.x.is_finite() && p.y.is_finite() && p.yaw.is_finite()
}

/// Through-poses: drop the poses the car has passed (never the last one).
fn drop_passed(a: &mut Active, car: &Pose, settings: &Settings) {
    while a.targets.len() > 1 {
        let next = a.targets[0];
        let near = next.distance(car) <= settings.pass_radius;
        let along = a
            .path
            .as_ref()
            .is_some_and(|h| path::passed_along(&h.poses, &next, car, settings.on_path));
        if !(near || along) {
            break;
        }
        a.targets.remove(0);
        a.index += 1;
    }
}

/// The final approach: near the goal, keep a path that still ends there and is young
/// enough, instead of replanning (TODO 17: replans there made the car circle the goal).
fn keep_path(a: &Active, car: Option<&Pose>, now: f64, settings: &Settings) -> bool {
    let (Some(car), Some(held)) = (car, &a.path) else {
        return false;
    };
    let last_leg = match a.kind {
        Kind::Through => a.targets.len() == 1,
        _ => true,
    };
    let end = a.end();
    let path_end = held.poses.last().expect("paths are never empty");
    last_leg
        && car.distance(&end) <= settings.final_approach
        && path_end.distance(&end) <= settings.path_end_tolerance
        && now - held.made < settings.path_max_age
}
