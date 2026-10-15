//! The place search from a terminal, to try queries and time them:
//!
//! `cargo run --release -p map-core --example search -- carleton university`
//!
//! Reads `maps/places/ottawa.db` (or the file in `$PLACES`); distances are from the
//! sim's datum, by Carleton.

use std::path::Path;

use map_core::{earth::LatLon, places::Places};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let file = std::env::var("PLACES").unwrap_or_else(|_| "maps/places/ottawa.db".into());
    let places = Places::open(Path::new(&file))?;
    let query = std::env::args().skip(1).collect::<Vec<_>>().join(" ");
    let near = LatLon::new(45.3860, -75.6960);
    let start = std::time::Instant::now();
    let found = places.search(&query, Some(near))?;
    println!("{query:?}: {} in {:?}", found.len(), start.elapsed());
    for p in found {
        let d = p.distance.map_or(0.0, |d| d.0);
        println!(
            "  {:<9} {:>7.0} m  {}  ({})",
            format!("{:?}", p.matched),
            d,
            p.title,
            p.detail()
        );
    }
    Ok(())
}
