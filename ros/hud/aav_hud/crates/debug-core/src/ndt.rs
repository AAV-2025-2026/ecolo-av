//! NDT (aav_ndt) on the debug screen: its status in plain words, and its map's occupied
//! cells for the faint wireframes (key M).
//!
//! `/localization/ndt/status` is a diagnostic_msgs/DiagnosticStatus: level OK, WARN or
//! ERROR (LOST); message `TRACKING`, `WAITING` or `LOST`, then `: why` for a poor fit;
//! values `score_per_point`, `overlap`, `iterations`, `match_ms`, `points`,
//! `poor_in_row`, `restarts`, `clouds_dropped`, `x`, `y`, `yaw` (aav_ndt's README).
//!
//! The map is the PCD `pixi run ndt-map drive` writes (map frame, ground removed), read
//! with ndt-core's own reader and snapped to cells (1 m by default).

use std::{collections::HashMap, fmt, fs::File, path::Path};

use map_core::geom::Point;

use crate::cubes;

/// What NDT is doing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NdtState {
    /// No start pose yet.
    Waiting,
    /// Matching: the last fit was good, or a few poor ones in a row.
    Tracking,
    /// Too many poor fits in a row: it starts again from ekf_global.
    Lost,
}

impl NdtState {
    /// From the message's first word.
    pub fn from_word(word: &str) -> Option<Self> {
        match word {
            "WAITING" => Some(Self::Waiting),
            "TRACKING" => Some(Self::Tracking),
            "LOST" => Some(Self::Lost),
            _ => None,
        }
    }

    pub fn word(self) -> &'static str {
        match self {
            Self::Waiting => "WAITING",
            Self::Tracking => "TRACKING",
            Self::Lost => "LOST",
        }
    }
}

/// How the last cloud went (the message's level).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fit {
    /// Level OK: a good fit, a pose published.
    Good,
    /// Level WARN: a poor fit, or no start yet.
    Poor,
    /// Level ERROR: LOST.
    Lost,
}

impl Fit {
    /// diagnostic_msgs' levels: 0 OK, 1 WARN, 2 ERROR (3 STALE counts as lost).
    pub fn from_level(level: u8) -> Self {
        match level {
            0 => Self::Good,
            1 => Self::Poor,
            _ => Self::Lost,
        }
    }
}

/// What the panel shows of NDT.
#[derive(Debug, Clone, PartialEq)]
pub struct NdtStatus {
    pub fit: Fit,
    /// `None` if the message's first word is none of NDT's.
    pub state: Option<NdtState>,
    /// The message after its first word: why a fit was poor, or empty.
    pub why: String,
    /// The fit's score per point (good fits score about 3; below 2 is poor).
    pub score_per_point: Option<f64>,
    /// The match alone, wall clock, milliseconds.
    pub match_ms: Option<f64>,
    /// The share of the scan's points that landed in map cubes.
    pub overlap: Option<f64>,
    pub iterations: Option<u64>,
    /// Points matched, after the filters.
    pub points: Option<u64>,
    pub poor_in_row: Option<u64>,
    /// Restarts from ekf_global after LOST.
    pub restarts: Option<u64>,
    /// Clouds that arrived while one was being matched.
    pub clouds_dropped: Option<u64>,
}

impl NdtStatus {
    /// From the message's level, its `message` and its key-value pairs. Unreadable
    /// values are left out.
    pub fn from_message<'a>(
        level: u8,
        message: &str,
        values: impl IntoIterator<Item = (&'a str, &'a str)>,
    ) -> Self {
        let (word, rest) = message
            .split_once(':')
            .map_or((message, ""), |(w, r)| (w, r));
        let mut s = Self {
            fit: Fit::from_level(level),
            state: NdtState::from_word(word.trim()),
            why: rest.trim().to_owned(),
            score_per_point: None,
            match_ms: None,
            overlap: None,
            iterations: None,
            points: None,
            poor_in_row: None,
            restarts: None,
            clouds_dropped: None,
        };
        let number = |v: &str| v.trim().parse::<f64>().ok().filter(|x| x.is_finite());
        let count = |v: &str| v.trim().parse::<u64>().ok();
        for (key, value) in values {
            match key {
                "score_per_point" => s.score_per_point = number(value),
                "match_ms" => s.match_ms = number(value),
                "overlap" => s.overlap = number(value),
                "iterations" => s.iterations = count(value),
                "points" => s.points = count(value),
                "poor_in_row" => s.poor_in_row = count(value),
                "restarts" => s.restarts = count(value),
                "clouds_dropped" => s.clouds_dropped = count(value),
                _ => {}
            }
        }
        s
    }

    /// The panel's big word: TRACKING, WAITING, LOST, or the message itself.
    pub fn headline(&self) -> &'static str {
        match (self.fit, self.state) {
            (Fit::Lost, _) | (_, Some(NdtState::Lost)) => "LOST",
            (_, Some(s)) => s.word(),
            (_, None) => "?",
        }
    }

    /// The numbers, in one short line: "3.41 per point   12.3 ms".
    pub fn numbers(&self) -> String {
        let mut parts = Vec::new();
        if let Some(s) = self.score_per_point {
            parts.push(format!("{s:.2} per point"));
        }
        if let Some(ms) = self.match_ms {
            parts.push(format!("{ms:.1} ms"));
        }
        parts.join("   ")
    }

    /// The smaller numbers: overlap, iterations, restarts, dropped clouds.
    pub fn details(&self) -> String {
        let mut parts = Vec::new();
        if let Some(o) = self.overlap {
            parts.push(format!("overlap {:.0}%", o * 100.0));
        }
        if let Some(i) = self.iterations {
            parts.push(format!("{i} steps"));
        }
        if let Some(r) = self.restarts {
            parts.push(format!("{r} restarts"));
        }
        if let Some(d) = self.clouds_dropped.filter(|&d| d > 0) {
            parts.push(format!("{d} clouds dropped"));
        }
        parts.join(" · ")
    }
}

/// NDT's map, as the screen has it.
#[derive(Debug, Clone, PartialEq)]
pub enum MapFile {
    /// No file at the path: say how to make one.
    Missing {
        path: String,
    },
    /// The file is there but can't be read.
    Unreadable {
        path: String,
        why: String,
    },
    Loaded {
        path: String,
        cells: MapCells,
    },
}

impl MapFile {
    /// What `pixi run ndt-map drive` makes, said once for the panel and the README.
    pub const HOW_TO_MAKE: &'static str =
        "make it with pixi run ndt-map drive (about 6 min), then pixi run debugdemo";

    /// Reads `path` (a PCD) into cells of `size` metres. An empty path is missing.
    pub fn read(path: &str, size: f64) -> Self {
        let owned = path.to_owned();
        if path.trim().is_empty() || !Path::new(path).is_file() {
            return Self::Missing { path: owned };
        }
        let read = File::open(path)
            .map_err(|e| e.to_string())
            .and_then(|f| ndt_core::pcd::read(f).map_err(|e| e.to_string()));
        match read {
            Ok(points) => Self::Loaded {
                path: owned,
                cells: MapCells::from_points(points.iter().map(|p| [p.x, p.y, p.z]), size),
            },
            Err(why) => Self::Unreadable { path: owned, why },
        }
    }

    pub fn cells(&self) -> Option<&MapCells> {
        match self {
            Self::Loaded { cells, .. } => Some(cells),
            _ => None,
        }
    }
}

impl fmt::Display for MapFile {
    /// One line for the panel.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Missing { path } => write!(f, "no NDT map at {path}: {}", Self::HOW_TO_MAKE),
            Self::Unreadable { path, why } => write!(f, "NDT map {path}: {why}"),
            Self::Loaded { path, cells } => {
                write!(f, "map {path}: {} cubes of {} m", cells.len(), cells.size)
            }
        }
    }
}

/// The map's occupied cells: their centres in the map frame.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct MapCells {
    /// One cell's edge, metres.
    pub size: f32,
    pub centres: Vec<[f32; 3]>,
}

/// A cell needs this many of the map's points to count: a stray point isn't a wall.
pub const MIN_POINTS: u32 = 3;

impl MapCells {
    /// The cells of `size` metres holding at least [`MIN_POINTS`] of `points` (map frame).
    /// Points that aren't finite are skipped.
    pub fn from_points(points: impl IntoIterator<Item = [f64; 3]>, size: f64) -> Self {
        let mut counts: HashMap<[i32; 3], u32> = HashMap::new();
        for p in points
            .into_iter()
            .filter(|p| p.iter().all(|v| v.is_finite()))
        {
            *counts.entry(cubes::cell_of(p, size)).or_default() += 1;
        }
        let mut centres: Vec<[f32; 3]> = counts
            .into_iter()
            .filter(|&(_, n)| n >= MIN_POINTS)
            .map(|(c, _)| c.map(|i| ((f64::from(i) + 0.5) * size) as f32))
            .collect();
        // A steady order, so a redraw never flickers between equal cells.
        centres.sort_by(|a, b| {
            a.iter()
                .zip(b)
                .fold(std::cmp::Ordering::Equal, |o, (x, y)| {
                    o.then(x.total_cmp(y))
                })
        });
        Self {
            size: size as f32,
            centres,
        }
    }

    pub fn len(&self) -> usize {
        self.centres.len()
    }

    pub fn is_empty(&self) -> bool {
        self.centres.is_empty()
    }

    /// At most `max` cells, the nearest `to` (map frame, seen from above).
    pub fn nearest(&self, to: Point, max: usize) -> Vec<[f32; 3]> {
        let mut v = self.centres.clone();
        cubes::keep_nearest_by(&mut v, |c| *c, to, max);
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tracking() -> NdtStatus {
        NdtStatus::from_message(
            0,
            "TRACKING",
            [
                ("points", "812"),
                ("poor_in_row", "0"),
                ("restarts", "1"),
                ("clouds_dropped", "0"),
                ("match_ms", "12.34"),
                ("score_per_point", "3.412"),
                ("overlap", "0.870"),
                ("iterations", "7"),
                ("x", "1.0"),
            ],
        )
    }

    #[test]
    fn reads_a_good_fit() {
        let s = tracking();
        assert_eq!((s.fit, s.state), (Fit::Good, Some(NdtState::Tracking)));
        assert_eq!(s.headline(), "TRACKING");
        assert_eq!(s.numbers(), "3.41 per point   12.3 ms");
        assert_eq!(s.details(), "overlap 87% · 7 steps · 1 restarts");
        assert_eq!(s.points, Some(812));
    }

    #[test]
    fn reads_a_poor_fit_and_lost() {
        let poor = NdtStatus::from_message(
            1,
            "TRACKING: a poor fit (score per point too low)",
            [("score_per_point", "1.2")],
        );
        assert_eq!(poor.fit, Fit::Poor);
        assert_eq!(poor.why, "a poor fit (score per point too low)");
        let lost = NdtStatus::from_message(2, "LOST: a poor fit (out of iterations)", []);
        assert_eq!(lost.headline(), "LOST");
        let waiting = NdtStatus::from_message(1, "WAITING: no start pose yet", []);
        assert_eq!(waiting.headline(), "WAITING");
        assert_eq!(waiting.numbers(), "");
        let odd = NdtStatus::from_message(0, "hello", [("match_ms", "nan")]);
        assert_eq!((odd.headline(), odd.match_ms), ("?", None));
    }

    #[test]
    fn a_map_keeps_cells_with_enough_points() {
        let wall = (0..30).map(|i| [0.5, f64::from(i) * 0.1, 1.2]);
        let stray = [[10.2, 10.2, 1.0], [f64::NAN, 0.0, 0.0]];
        let cells = MapCells::from_points(wall.chain(stray), 1.0);
        // 3 m of wall: cells y = 0, 1, 2; the stray point isn't one.
        assert_eq!(
            cells.centres,
            vec![[0.5, 0.5, 1.5], [0.5, 1.5, 1.5], [0.5, 2.5, 1.5]]
        );
        assert_eq!(
            cells.nearest(Point::new(0.0, 3.0), 1),
            vec![[0.5, 2.5, 1.5]]
        );
    }

    #[test]
    fn a_missing_map_says_how_to_make_one() {
        let m = MapFile::read("/no/such/map.pcd", 1.0);
        assert!(matches!(m, MapFile::Missing { .. }));
        assert!(m.to_string().contains("pixi run ndt-map drive"));
        assert!(matches!(MapFile::read("", 1.0), MapFile::Missing { .. }));
    }

    #[test]
    fn a_pcd_file_becomes_cells() {
        let dir = std::env::temp_dir().join(format!("debug-core-ndt-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("a temp folder");
        let path = dir.join("lot.pcd");
        let points: Vec<ndt_core::Point> = (0..10)
            .map(|i| ndt_core::Point::new(2.1, 0.05 * f64::from(i), 0.8))
            .collect();
        let mut file = File::create(&path).expect("a temp file");
        ndt_core::pcd::write(&mut file, &points).expect("written");
        drop(file);
        let m = MapFile::read(path.to_str().expect("utf-8"), 1.0);
        let cells = m.cells().expect("loaded");
        assert_eq!(cells.centres, vec![[2.5, 0.5, 0.5]]);
        std::fs::write(&path, "not a pcd").expect("written");
        assert!(matches!(
            MapFile::read(path.to_str().expect("utf-8"), 1.0),
            MapFile::Unreadable { .. }
        ));
        let _ = std::fs::remove_dir_all(dir);
    }
}
