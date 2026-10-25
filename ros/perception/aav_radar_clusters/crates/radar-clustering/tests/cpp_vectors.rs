//! The C++ node's answers, kept after it was removed.
//!
//! `cpp_vectors.txt` holds radar clouds and what the 2025-26 C++ node (`dbscan` in
//! `aav_object_detection`) published for each: its clusters and its boxes. They were
//! recorded by `test/capture_cpp_vectors.py`, through ROS, from the node itself. The same
//! points through [`cluster`] must give the same clusters, with the same ids, and the same
//! boxes, bit for bit.
//!
//! The C++ compared eps with the squared distance, so its neighbours were within
//! sqrt(eps) m. Here the radius is a distance: these tests give `cluster` sqrt(eps). No
//! pair of points sits within rounding of that radius, so both tests agree on every pair.

use radar_clustering::{cluster, Metres, Point, Settings, BOX_MARGIN};

/// One cloud, and what the C++ node published for it.
struct Case {
    /// Where the cloud starts in `cpp_vectors.txt`, for a failure message.
    line: usize,
    what: String,
    points: Vec<Point>,
    /// (id, the indices of its points, in order), in the order of their ids.
    clusters: Vec<(usize, Vec<usize>)>,
    /// (id, centre, size).
    boxes: Vec<(usize, [f64; 3], [f64; 3])>,
    /// The C++ cloud's extra points at (0, 0, 0), one per noise point.
    padding: usize,
}

/// The C++ node's settings, and the clouds it clustered with them.
struct Group {
    name: String,
    eps: f32,
    min_points: usize,
    cases: Vec<Case>,
}

fn numbers<T: std::str::FromStr>(text: &str) -> Vec<T>
where
    T::Err: std::fmt::Debug,
{
    text.split_whitespace()
        .map(|v| v.parse().expect("a number"))
        .collect()
}

fn three(values: &[f64]) -> [f64; 3] {
    values.try_into().expect("three numbers")
}

fn groups() -> Vec<Group> {
    let mut groups: Vec<Group> = Vec::new();
    for (index, line) in include_str!("cpp_vectors.txt").lines().enumerate() {
        let Some((word, rest)) = line.split_once(' ') else {
            continue;
        };
        if word == "#" {
            continue;
        }
        if word == "settings" {
            // settings 'the car' eps 0.8 minimum_points 15
            let (name, values) = rest.rsplit_once('\'').expect("a quoted name");
            let values: Vec<&str> = values.split_whitespace().collect();
            groups.push(Group {
                name: name.trim_start_matches('\'').to_string(),
                eps: values[1].parse().expect("eps"),
                min_points: values[3].parse().expect("minimum_points"),
                cases: Vec::new(),
            });
            continue;
        }
        let group = groups.last_mut().expect("settings come first");
        if word == "cloud" {
            group.cases.push(Case {
                line: index + 1,
                what: rest.to_string(),
                points: Vec::new(),
                clusters: Vec::new(),
                boxes: Vec::new(),
                padding: 0,
            });
            continue;
        }
        let case = group.cases.last_mut().expect("a cloud comes first");
        match word {
            "point" => {
                let v: Vec<f32> = numbers(rest);
                case.points.push(Point {
                    position: [v[0], v[1], v[2]],
                    intensity: v[3],
                    velocity: v[4],
                });
            }
            "cluster" => {
                let v: Vec<usize> = numbers(rest);
                case.clusters.push((v[0], v[1..].to_vec()));
            }
            "box" => {
                let (id, values) = rest.split_once(' ').expect("an id");
                let v: Vec<f64> = numbers(values);
                let id = id.parse().expect("a box id");
                case.boxes.push((id, three(&v[..3]), three(&v[3..])));
            }
            "padding" => case.padding = rest.parse().expect("a count"),
            _ => {}
        }
    }
    groups
}

#[test]
fn the_vectors_cover_both_settings_and_real_clusters() {
    let groups = groups();
    let names: Vec<_> = groups.iter().map(|g| g.name.as_str()).collect();
    assert_eq!(names, ["the car", "the bench"]);
    for group in &groups {
        assert!(group.cases.len() >= 40, "{}: too few clouds", group.name);
        let clusters: usize = group.cases.iter().map(|c| c.clusters.len()).sum();
        let noise: usize = group.cases.iter().map(|c| c.padding).sum();
        assert!(clusters >= 40, "{}: too few clusters", group.name);
        assert!(noise > 0, "{}: no noise", group.name);
    }
}

#[test]
fn the_clusters_and_boxes_are_the_cpp_nodes() {
    for group in groups() {
        let radius = f64::from(group.eps).sqrt();
        let settings = Settings::new(Metres(radius), group.min_points).expect("valid settings");
        for case in &group.cases {
            let at = format!("{} ({}), line {}", case.what, group.name, case.line);
            let found = cluster(&case.points, &settings);

            let clusters: Vec<_> = found
                .iter()
                .enumerate()
                .map(|(index, c)| (index + 1, c.members.clone()))
                .collect();
            assert_eq!(clusters, case.clusters, "clusters: {at}");

            let boxes: Vec<_> = found
                .iter()
                .enumerate()
                .map(|(index, c)| {
                    let cube = c.bounds.padded(BOX_MARGIN);
                    (index + 1, cube.centre, cube.size)
                })
                .collect();
            let bits = |b: &[(usize, [f64; 3], [f64; 3])]| -> Vec<_> {
                b.iter()
                    .map(|(id, c, s)| (*id, c.map(f64::to_bits), s.map(f64::to_bits)))
                    .collect()
            };
            assert_eq!(bits(&boxes), bits(&case.boxes), "boxes: {at}");

            // The C++ cloud had a point at (0, 0, 0) for each noise point; ours leaves
            // them out. The numbers must still add up.
            let clustered: usize = found.iter().map(|c| c.members.len()).sum();
            assert_eq!(clustered + case.padding, case.points.len(), "noise: {at}");
        }
    }
}
