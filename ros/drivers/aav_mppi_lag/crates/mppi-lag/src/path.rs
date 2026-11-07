//! The planner's path, and the piece of it MPPI looks at each tick: Nav2's PathHandler.
//!
//! Each tick: find the closest pose within `max_search` m of path from where the car was
//! last, drop everything before it (Nav2 prunes the same), and hand the critics the poses
//! from there to `prune_distance` m along (Nav2's "transformed plan"). The goal is the
//! path's last pose. Forward only: no cusp handling (the trackers never reverse).

use crate::costmap::Costmap;
use crate::model::{wrap, Pose};

/// A path in the odom frame, and how far along it the car has got.
#[derive(Debug, Clone, PartialEq)]
pub struct GlobalPath {
    poses: Vec<Pose>,
    start: usize,
}

/// Where the car is beside the path.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Foot {
    /// m, + left of the path.
    pub cross_track: f64,
    /// rad: the car's heading minus the path's.
    pub heading_error: f64,
    /// m along the path to its end.
    pub left: f64,
}

/// The index of the first pose after `distance` m along `poses` from `from`; `poses.len()`
/// if the path ends first (Nav2's first_after_integrated_distance).
fn first_after(poses: &[Pose], from: usize, distance: f64) -> usize {
    let mut along = 0.0;
    for i in from + 1..poses.len() {
        along += poses[i].distance(&poses[i - 1]);
        if along > distance {
            return i;
        }
    }
    poses.len()
}

impl GlobalPath {
    /// A path of `poses` (odom frame). `None` if it is empty or not all numbers.
    pub fn new(poses: Vec<Pose>) -> Option<Self> {
        let finite = poses
            .iter()
            .all(|p| p.x.is_finite() && p.y.is_finite() && p.yaw.is_finite());
        (finite && !poses.is_empty()).then_some(Self { poses, start: 0 })
    }

    /// The last pose: the goal.
    pub fn goal(&self) -> Pose {
        self.poses[self.poses.len() - 1]
    }

    /// Every pose not yet pruned.
    pub fn remaining(&self) -> &[Pose] {
        &self.poses[self.start..]
    }

    /// Prune to the closest pose to `pose` (searching `max_search` m ahead), and return the
    /// next `prune_distance` m of path; with a costmap, only the part inside it.
    pub fn window(
        &mut self,
        pose: &Pose,
        max_search: f64,
        prune_distance: f64,
        costmap: Option<&Costmap>,
    ) -> &[Pose] {
        let bound = first_after(&self.poses, self.start, max_search);
        let closest = (self.start..bound.max(self.start + 1))
            .min_by(|&a, &b| {
                pose.distance(&self.poses[a])
                    .total_cmp(&pose.distance(&self.poses[b]))
            })
            .unwrap_or(self.start);
        self.start = closest;
        let end = first_after(&self.poses, closest, prune_distance);
        let mut window = &self.poses[closest..end];
        if let Some(map) = costmap {
            let inside = window
                .iter()
                .position(|p| map.cell(p.x, p.y).is_none())
                .unwrap_or(window.len());
            window = &window[..inside];
        }
        window
    }

    /// Where `pose` is beside the path, from the pruned start on.
    pub fn foot(&self, pose: &Pose) -> Foot {
        let poses = self.remaining();
        if poses.len() < 2 {
            let end = poses[0];
            return Foot {
                cross_track: 0.0,
                heading_error: wrap(pose.yaw - end.yaw),
                left: pose.distance(&end),
            };
        }
        let mut best = (f64::INFINITY, 0.0, 0.0, 0.0); // (distance², cross, heading, along)
        let mut along = 0.0;
        let mut total = 0.0;
        for pair in poses.windows(2) {
            let (a, b) = (pair[0], pair[1]);
            let (dx, dy) = (b.x - a.x, b.y - a.y);
            let length = dx.hypot(dy);
            if length > 1e-9 {
                let t = (((pose.x - a.x) * dx + (pose.y - a.y) * dy) / (length * length))
                    .clamp(0.0, 1.0);
                let (fx, fy) = (a.x + t * dx, a.y + t * dy);
                let d2 = (pose.x - fx).powi(2) + (pose.y - fy).powi(2);
                if d2 < best.0 {
                    let heading = dy.atan2(dx);
                    let cross = (dx * (pose.y - a.y) - dy * (pose.x - a.x)) / length;
                    best = (d2, cross, wrap(pose.yaw - heading), along + t * length);
                }
            }
            along += length;
            total = along;
        }
        Foot {
            cross_track: best.1,
            heading_error: best.2,
            left: (total - best.3).max(0.0),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(n: usize, step: f64) -> Vec<Pose> {
        (0..n)
            .map(|i| Pose::new(i as f64 * step, 0.0, 0.0))
            .collect()
    }

    #[test]
    fn empty_or_nan_paths_are_refused() {
        assert!(GlobalPath::new(vec![]).is_none());
        assert!(GlobalPath::new(vec![Pose::new(f64::NAN, 0.0, 0.0)]).is_none());
    }

    #[test]
    fn window_prunes_behind_and_stops_after_prune_distance() {
        let mut path = GlobalPath::new(line(201, 0.1)).expect("a path");
        let window = path
            .window(&Pose::new(5.02, 0.3, 0.0), 10.0, 3.0, None)
            .to_vec();
        assert!((window[0].x - 5.0).abs() < 1e-9);
        // First pose after 3 m along is excluded: 5.0 .. 8.0 inclusive.
        assert!((window[window.len() - 1].x - 8.0).abs() < 1e-9);
        assert_eq!(path.remaining()[0].x, window[0].x);
    }

    #[test]
    fn search_is_limited_ahead() {
        // The car is near the far end, but the search only looks 1 m ahead of the start.
        let mut path = GlobalPath::new(line(201, 0.1)).expect("a path");
        let window = path.window(&Pose::new(19.0, 0.0, 0.0), 1.0, 3.0, None);
        assert!((window[0].x - 1.0).abs() < 1e-9, "{:?}", window[0]);
    }

    #[test]
    fn foot_measures_cross_track_left_positive() {
        let path = GlobalPath::new(line(101, 0.1)).expect("a path");
        let foot = path.foot(&Pose::new(4.0, 0.5, 0.1));
        assert!((foot.cross_track - 0.5).abs() < 1e-9);
        assert!((foot.heading_error - 0.1).abs() < 1e-9);
        assert!((foot.left - 6.0).abs() < 1e-9);
        assert!((path.foot(&Pose::new(4.0, -0.2, 0.0)).cross_track + 0.2).abs() < 1e-9);
    }
}
