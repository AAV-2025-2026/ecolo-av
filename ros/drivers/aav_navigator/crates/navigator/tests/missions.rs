//! The navigator against a pretend planner and follower: the trees' paths through it.

use navigator::{BackUp, Command, Mission, Navigator, Outcome, Pose, Settings, WaypointMode};

fn straight(to: &Pose) -> Vec<Pose> {
    (0..=10)
        .map(|i| Pose::new(to.x * i as f64 / 10.0, to.y * i as f64 / 10.0, to.yaw))
        .collect()
}

fn plan_token(out: &[Command]) -> (u64, Vec<Pose>) {
    out.iter()
        .find_map(|c| match c {
            Command::Plan { token, goals } => Some((*token, goals.clone())),
            _ => None,
        })
        .unwrap_or_else(|| panic!("no plan in {out:?}"))
}

fn follow_token(out: &[Command]) -> u64 {
    out.iter()
        .find_map(|c| match c {
            Command::Follow { token, .. } => Some(*token),
            _ => None,
        })
        .unwrap_or_else(|| panic!("no follow in {out:?}"))
}

fn finished(out: &[Command]) -> Option<(u64, Outcome)> {
    out.iter().find_map(|c| match c {
        Command::Finished { id, outcome } => Some((*id, outcome.clone())),
        _ => None,
    })
}

const GOAL: Pose = Pose::new(30.0, 0.0, 0.0);

#[test]
fn plan_follow_arrive() {
    let mut nav = Navigator::new(Settings::default());
    assert!(nav.start(1, Mission::ToPose(GOAL), 0.0).is_empty());
    let (t, goals) = plan_token(&nav.tick(0.0, Some(&Pose::default())));
    assert_eq!(goals, vec![GOAL]);
    let f = follow_token(&nav.planned(t, Ok(straight(&GOAL)), 0.1));
    // Nothing new before the second is up; then a replan, the follower gets it.
    assert!(nav.tick(0.5, Some(&Pose::default())).is_empty());
    let (t2, _) = plan_token(&nav.tick(1.0, Some(&Pose::new(1.0, 0.0, 0.0))));
    let f2 = follow_token(&nav.planned(t2, Ok(straight(&GOAL)), 1.1));
    // The first follow goal's answer is late now: ignored.
    assert!(nav.followed(f, Err((0, "replaced".into())), 1.2).is_empty());
    let out = nav.followed(f2, Ok(()), 20.0);
    assert_eq!(
        finished(&out),
        Some((1, Outcome::Succeeded { missed: vec![] }))
    );
    assert_eq!(nav.goal(), None);
}

#[test]
fn final_approach_keeps_the_path() {
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, Some(&Pose::default())));
    nav.planned(t, Ok(straight(&GOAL)), 0.0);
    // 5 m out: no replan for up to 20 s.
    let near = Pose::new(25.0, 0.5, 0.0);
    assert!(nav.tick(3.0, Some(&near)).is_empty());
    assert!(nav.tick(19.0, Some(&near)).is_empty());
    // The path is too old now: plan again.
    plan_token(&nav.tick(21.0, Some(&near)));
}

#[test]
fn a_failed_replan_while_driving_keeps_going_then_recovers() {
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, None));
    nav.planned(t, Ok(straight(&GOAL)), 0.0);
    let mut now = 1.0;
    for _ in 0..3 {
        let (t, _) = plan_token(&nav.tick(now, None));
        assert!(nav.planned(t, Err((208, "no path".into())), now).is_empty());
        now += 1.0;
    }
    // The fourth in a row: the planner's own recovery, the global costmap cleared.
    let (t, _) = plan_token(&nav.tick(now, None));
    let out = nav.planned(t, Err((208, "no path".into())), now);
    assert!(matches!(
        out[..],
        [Command::Clear {
            local: false,
            global: true,
            ..
        }]
    ));
}

#[test]
fn the_follower_failing_clears_local_then_recoveries_in_turn_then_gives_up() {
    let settings = Settings {
        retries: 2,
        ..Settings::default()
    };
    let mut nav = Navigator::new(settings);
    nav.start(7, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, None));
    let f = follow_token(&nav.planned(t, Ok(straight(&GOAL)), 0.0));
    // No progress: clear the local costmap, follow the same path again.
    let out = nav.followed(f, Err((105, "no progress".into())), 10.0);
    let Command::Clear {
        token,
        local: true,
        global: false,
    } = out[0]
    else {
        panic!("{out:?}")
    };
    let f = follow_token(&nav.recovered(token, true, 10.1));
    // Again: the first outer recovery, both costmaps.
    let out = nav.followed(f, Err((105, "no progress".into())), 20.0);
    assert_eq!(out[0], Command::StopFollowing);
    let Command::Clear {
        token,
        local: true,
        global: true,
    } = out[1]
    else {
        panic!("{out:?}")
    };
    // After it, a new plan at once.
    let (t, _) = plan_token(&nav.recovered(token, true, 20.5));
    let f = follow_token(&nav.planned(t, Ok(straight(&GOAL)), 20.6));
    let out = nav.followed(f, Err((105, "no progress".into())), 30.0);
    let out = if matches!(out[..], [Command::Clear { .. }]) {
        // The follower's own clear comes back each attempt.
        let Command::Clear { token, .. } = out[0] else {
            unreachable!()
        };
        let f = follow_token(&nav.recovered(token, true, 30.1));
        nav.followed(f, Err((105, "no progress".into())), 31.0)
    } else {
        out
    };
    // The second outer recovery: wait 5 s (no back up: forward only).
    assert_eq!(out, vec![Command::StopFollowing]);
    assert!(nav.tick(33.0, None).is_empty());
    let (t, _) = plan_token(&nav.tick(36.1, None));
    let f = follow_token(&nav.planned(t, Ok(straight(&GOAL)), 36.2));
    let out = nav.followed(f, Err((105, "no progress".into())), 40.0);
    let Command::Clear { token, .. } = out[0] else {
        panic!("{out:?}")
    };
    let f = follow_token(&nav.recovered(token, true, 40.1));
    // Out of retries: aborted with the follower's code.
    let out = nav.followed(f, Err((105, "no progress".into())), 41.0);
    match finished(&out) {
        Some((7, Outcome::Aborted { code: 105, .. })) => {}
        other => panic!("{other:?}"),
    }
}

#[test]
fn back_up_is_a_recovery_only_where_the_car_may_reverse() {
    let settings = Settings {
        backup: Some(BackUp {
            distance: 1.0,
            speed: 0.25,
        }),
        ..Settings::default()
    };
    let mut nav = Navigator::new(settings);
    nav.start(1, Mission::ToPose(GOAL), 0.0);
    let mut kinds = Vec::new();
    let mut now = 0.0;
    // An outer recovery that answers plans again at once; a wait, at the next tick.
    let mut pending: Vec<Command> = Vec::new();
    for _ in 0..3 {
        let asked = if pending.is_empty() {
            nav.tick(now, None)
        } else {
            std::mem::take(&mut pending)
        };
        let (t, _) = plan_token(&asked);
        // A goal the planner can't reach, and clearing doesn't help.
        let out = nav.planned(t, Err((208, "no path".into())), now);
        let Command::Clear { token, .. } = out[0] else {
            panic!("{out:?}")
        };
        let out = nav.recovered(token, true, now);
        let (t, _) = plan_token(&out);
        let out = nav.planned(t, Err((208, "no path".into())), now);
        kinds.push(match out.get(1) {
            Some(Command::Clear { .. }) => "clear",
            Some(Command::BackUp { .. }) => "backup",
            None => "wait",
            other => panic!("{other:?}"),
        });
        match out.get(1) {
            Some(Command::Clear { token, .. }) | Some(Command::BackUp { token, .. }) => {
                pending = nav.recovered(*token, true, now);
            }
            _ => now += 5.0,
        }
        now += 0.1;
    }
    assert_eq!(kinds, vec!["clear", "wait", "backup"]);
}

#[test]
fn errors_no_recovery_can_fix_end_the_goal_at_once() {
    let mut nav = Navigator::new(Settings::default());
    nav.start(3, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, None));
    let out = nav.planned(t, Err((204, "the goal is off the costmap".into())), 0.0);
    match finished(&out) {
        Some((
            3,
            Outcome::Aborted {
                code: 204, message, ..
            },
        )) => {
            assert!(message.contains("off the costmap"), "{message}")
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn a_new_goal_replaces_the_old_and_cancel_stops() {
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, None));
    let out = nav.start(2, Mission::ToPose(Pose::new(5.0, 5.0, 0.0)), 0.5);
    assert!(matches!(
        finished(&out),
        Some((1, Outcome::Aborted { code: 0, .. }))
    ));
    // The old goal's plan comes back late: ignored.
    assert!(nav.planned(t, Ok(straight(&GOAL)), 0.6).is_empty());
    let out = nav.cancel(2);
    assert_eq!(out[0], Command::StopFollowing);
    assert_eq!(finished(&out), Some((2, Outcome::Cancelled)));
    assert!(nav.cancel(2).is_empty());
}

#[test]
fn through_poses_plans_through_all_and_drops_the_passed() {
    let poses = vec![Pose::new(10.0, 1.5, 0.0), Pose::new(20.0, 0.0, 0.0), GOAL];
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::ThroughPoses(poses.clone()), 0.0);
    let (t, goals) = plan_token(&nav.tick(0.0, Some(&Pose::default())));
    assert_eq!(goals, poses);
    nav.planned(t, Ok(straight(&GOAL)), 0.0);
    // Every 3 s; the first pose (1.5 m off the path) is passed along it at x = 11.
    assert!(nav.tick(2.0, Some(&Pose::new(11.0, 0.0, 0.0))).is_empty());
    let (_, goals) = plan_token(&nav.tick(3.0, Some(&Pose::new(11.0, 0.0, 0.0))));
    assert_eq!(goals, poses[1..].to_vec());
    let p = nav.progress(Some(&Pose::new(11.0, 0.0, 0.0))).unwrap();
    assert_eq!((p.waypoint, p.poses_remaining), (1, 2));
    assert!((p.distance_remaining - 19.0).abs() < 1e-6);
}

#[test]
fn waypoints_pass_through_by_default_or_stop_at_each() {
    let wps = vec![Pose::new(10.0, 0.0, 0.0), GOAL];
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::Waypoints(wps.clone()), 0.0);
    let (_, goals) = plan_token(&nav.tick(0.0, None));
    assert_eq!(goals, wps, "one plan through both");

    let mut nav = Navigator::new(Settings {
        waypoints: WaypointMode::StopAtEach,
        ..Settings::default()
    });
    nav.start(1, Mission::Waypoints(wps.clone()), 0.0);
    let (t, goals) = plan_token(&nav.tick(0.0, None));
    assert_eq!(goals, vec![wps[0]]);
    let f = follow_token(&nav.planned(t, Ok(straight(&wps[0])), 0.0));
    assert!(nav.followed(f, Ok(()), 10.0).is_empty());
    let (t, goals) = plan_token(&nav.tick(10.0, None));
    assert_eq!(goals, vec![wps[1]]);
    // The second can't be planned at all: missed, and the goal ends (it was the last).
    let out = nav.planned(t, Err((206, "goal occupied".into())), 10.0);
    match finished(&out) {
        Some((1, Outcome::Aborted { missed, .. })) => assert_eq!(missed, vec![1]),
        other => panic!("{other:?}"),
    }
}

#[test]
fn a_start_marked_occupied_clears_the_global_costmap_first() {
    let mut nav = Navigator::new(Settings::default());
    nav.start(1, Mission::ToPose(GOAL), 0.0);
    let (t, _) = plan_token(&nav.tick(0.0, None));
    let out = nav.planned(t, Err((205, "start occupied".into())), 0.0);
    assert!(matches!(
        out[..],
        [Command::Clear {
            local: false,
            global: true,
            ..
        }]
    ));
}

#[test]
fn empty_goals_are_refused() {
    let mut nav = Navigator::new(Settings::default());
    let out = nav.start(4, Mission::ThroughPoses(vec![]), 0.0);
    assert!(matches!(
        finished(&out),
        Some((4, Outcome::Aborted { code: 0, .. }))
    ));
    let out = nav.start(5, Mission::ToPose(Pose::new(f64::NAN, 0.0, 0.0)), 0.0);
    assert!(finished(&out).is_some());
    assert_eq!(nav.goal(), None);
}
