//! The hand-made maps, planned and timed: `cargo run --release -p lattice-planner --example scenes`.

use lattice_planner::{cusps, length, scenes, tightest_turn};

fn main() {
    println!(
        "| scene | reversing | result | length m | tightest turn m | cusps | iterations | search ms | total ms |"
    );
    println!("|---|---|---|---|---|---|---|---|---|");
    for reversing in [false, true] {
        let planner = scenes::planner(reversing);
        for scene in scenes::all() {
            // The best of 5, so a busy computer doesn't decide the number.
            let mut best = None;
            for _ in 0..5 {
                let r = planner.plan(&scene.grid, &scene.start, &scene.goal, &|| false);
                let keep = match (&best, &r) {
                    (Some(Ok(b)), Ok(p)) => {
                        let b: &lattice_planner::Plan = b;
                        p.total_time < b.total_time
                    }
                    _ => true,
                };
                if keep {
                    best = Some(r);
                }
            }
            match best.unwrap() {
                Ok(p) => println!(
                    "| {} | {reversing} | path | {:.1} | {:.2} | {} | {} | {:.1} | {:.1} |",
                    scene.name,
                    length(&p.poses),
                    tightest_turn(&p.poses, 1.0),
                    cusps(&p.poses),
                    p.iterations,
                    p.search_time * 1e3,
                    p.total_time * 1e3
                ),
                Err(e) => println!("| {} | {reversing} | {e} | | | | | | |", scene.name),
            }
        }
    }
}
