//! A path's geometry: the nearest point, the distance left, passed poses.

use crate::Pose;

/// The index of the path's point nearest to `p`, and how far it is (m). None: no path.
pub fn nearest(path: &[Pose], p: &Pose) -> Option<(usize, f64)> {
    path.iter()
        .enumerate()
        .map(|(i, q)| (i, q.distance(p)))
        .min_by(|a, b| a.1.total_cmp(&b.1))
}

/// Metres along the path from its point nearest the car to its end; the straight line
/// with no path.
pub fn remaining(path: &[Pose], car: &Pose) -> f64 {
    match nearest(path, car) {
        None => 0.0,
        Some((i, gap)) => gap + length(&path[i..]),
    }
}

/// A path's length, m.
pub fn length(path: &[Pose]) -> f64 {
    path.windows(2).map(|w| w[0].distance(&w[1])).sum()
}

/// Has the car passed `pose` along `path`? True when the pose lies on the path (within
/// `on_path` m) and the car's nearest point is at or beyond the pose's.
pub fn passed_along(path: &[Pose], pose: &Pose, car: &Pose, on_path: f64) -> bool {
    match (nearest(path, pose), nearest(path, car)) {
        (Some((at, gap)), Some((here, _))) => gap <= on_path && here >= at,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(n: usize) -> Vec<Pose> {
        (0..n).map(|i| Pose::new(i as f64, 0.0, 0.0)).collect()
    }

    #[test]
    fn nearest_and_remaining() {
        let path = line(11);
        assert_eq!(nearest(&path, &Pose::new(3.2, 0.5, 0.0)).unwrap().0, 3);
        let left = remaining(&path, &Pose::new(3.0, 0.0, 0.0));
        assert!((left - 7.0).abs() < 1e-9);
        assert_eq!(remaining(&[], &Pose::default()), 0.0);
        assert!((length(&path) - 10.0).abs() < 1e-9);
    }

    #[test]
    fn passed_along_the_path_not_only_near_it() {
        let path = line(21);
        let pose = Pose::new(10.0, 1.5, 0.0); // the bend, cut by 1.5 m
        assert!(!passed_along(&path, &pose, &Pose::new(8.0, 0.0, 0.0), 2.0));
        assert!(passed_along(&path, &pose, &Pose::new(11.0, 0.0, 0.0), 2.0));
        // Off the path: never passed this way.
        let far = Pose::new(10.0, 5.0, 0.0);
        assert!(!passed_along(&path, &far, &Pose::new(15.0, 0.0, 0.0), 2.0));
    }
}
