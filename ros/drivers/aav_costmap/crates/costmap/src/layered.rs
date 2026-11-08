//! Nav2's `LayeredCostmap`: the static map, then each obstacle layer, then the inflation,
//! into one grid. Rolling (the local costmap: a window round the car, in odom) or fixed
//! to the map (the global costmap, in map).

use crate::cost::{FREE, NO_INFORMATION};
use crate::footprint;
use crate::grid::Grid;
use crate::inflation::Inflation;
use crate::obstacle::{Observation, ObstacleLayer};
use crate::static_layer::StaticMap;
use crate::transform::Pose2;

/// One costmap's settings: Nav2's, from nav2.yaml.
#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    /// A window that moves with the car (`rolling_window`).
    pub rolling: bool,
    /// m: the window's size (rolling only; a fixed costmap takes the map's).
    pub width: f64,
    /// m.
    pub height: f64,
    /// m per cell (rolling only; a fixed costmap takes the map's).
    pub resolution: f64,
    /// Unknown cells stay unknown (`track_unknown_space`); else they are free.
    pub track_unknown: bool,
    /// The car's outline in base_link, padded (footprint::padded).
    pub footprint: Vec<(f64, f64)>,
    /// m, and 1/m: the inflation (`inflation_layer`); None without one.
    pub inflation: Option<(f64, f64)>,
    /// A static layer reads the map.
    pub static_layer: bool,
}

/// A costmap: its layers and the grid they make.
#[derive(Debug, Clone)]
pub struct Costmap {
    settings: Settings,
    master: Grid,
    map: Option<StaticMap>,
    layers: Vec<ObstacleLayer>,
    inflation: Option<Inflation>,
}

impl Costmap {
    /// A costmap with these obstacle layers (their grids are resized to fit). A fixed one
    /// is empty until it has a map.
    pub fn new(settings: Settings, layers: Vec<ObstacleLayer>) -> Self {
        let (inscribed, _) = footprint::radii(&settings.footprint);
        let inflation = settings.inflation.map(|(radius, scaling)| Inflation {
            inflation_radius: radius,
            cost_scaling_factor: scaling,
            inscribed_radius: inscribed,
        });
        let master = if settings.rolling {
            let cells = |m: f64| (m / settings.resolution).round().max(1.0) as usize;
            Grid::new(
                (0.0, 0.0),
                settings.resolution,
                cells(settings.width),
                cells(settings.height),
                default(&settings),
            )
        } else {
            Grid::new((0.0, 0.0), settings.resolution, 0, 0, default(&settings))
        };
        let mut c = Self {
            settings,
            master,
            map: None,
            layers,
            inflation,
        };
        c.resize_layers();
        c
    }

    /// The settings.
    pub fn settings(&self) -> &Settings {
        &self.settings
    }

    /// The obstacle layers.
    pub fn layers(&self) -> &[ObstacleLayer] {
        &self.layers
    }

    /// The newest grid.
    pub fn grid(&self) -> &Grid {
        &self.master
    }

    /// The inscribed radius (m) and the inflation, if any.
    pub fn inflation(&self) -> Option<&Inflation> {
        self.inflation.as_ref()
    }

    /// A new map. A fixed costmap takes its size, cells and corner (Nav2's static layer
    /// resizes the master), and its obstacle layers start again.
    pub fn set_map(&mut self, map: StaticMap) {
        if !self.settings.rolling {
            let g = &map.grid;
            self.master = Grid::new(
                (g.origin_x, g.origin_y),
                g.resolution,
                g.width,
                g.height,
                default(&self.settings),
            );
            self.resize_layers();
        }
        self.map = Some(map);
    }

    /// Has it a map (or needs none)?
    pub fn ready(&self) -> bool {
        self.settings.rolling || self.map.is_some()
    }

    /// Forget every mark (Nav2's `ClearEntireCostmap`: each layer reset). The map comes
    /// back with the next update; the sensors' marks only as they see them again.
    pub fn clear(&mut self) {
        for layer in &mut self.layers {
            layer.grid.data.fill(layer.default);
        }
        self.master.data.fill(default(&self.settings));
    }

    fn resize_layers(&mut self) {
        for layer in &mut self.layers {
            layer.grid = self.master.like(layer.default);
        }
    }

    /// One update, as Nav2's `updateMap`: the window follows `robot` (the car's pose in
    /// this costmap's frame), then the master starts from nothing, the map is written in
    /// (`map_from_frame`: this frame's pose in the map frame; without it the map is left
    /// out), each obstacle layer takes `observations[layer][source]` (a list) and adds its grid,
    /// and the inflation goes last.
    pub fn update(
        &mut self,
        robot: &Pose2,
        map_from_frame: Option<&Pose2>,
        observations: &[Vec<Vec<&Observation>>],
    ) {
        if !self.ready() {
            return;
        }
        if self.settings.rolling {
            // Nav2's getSizeInMetersX: (cells - 1 + 0.5) x resolution, half a cell short.
            let (w, h) = (
                (self.master.width as f64 - 0.5) * self.master.resolution,
                (self.master.height as f64 - 0.5) * self.master.resolution,
            );
            let (x, y) = (robot.x - w / 2.0, robot.y - h / 2.0);
            self.master.move_origin(x, y, default(&self.settings));
            for layer in &mut self.layers {
                layer.grid.move_origin(x, y, layer.default);
            }
        }
        self.master.data.fill(default(&self.settings));
        if let Some(map) = self.map.as_ref().filter(|_| self.settings.static_layer) {
            if self.settings.rolling {
                if let Some(t) = map_from_frame {
                    map.stamp(&mut self.master, t);
                }
            } else {
                self.master.data.copy_from_slice(&map.grid.data);
            }
        }
        let outline = footprint::placed(&self.settings.footprint, robot);
        for (i, layer) in self.layers.iter_mut().enumerate() {
            let mut seen = observations.get(i).cloned().unwrap_or_default();
            seen.resize(layer.sources.len(), Vec::new());
            layer.update(&seen, &outline);
            layer.combine_into(&mut self.master);
        }
        if let Some(inflation) = &self.inflation {
            inflation.apply(&mut self.master);
        }
    }
}

fn default(s: &Settings) -> u8 {
    if s.track_unknown {
        NO_INFORMATION
    } else {
        FREE
    }
}
