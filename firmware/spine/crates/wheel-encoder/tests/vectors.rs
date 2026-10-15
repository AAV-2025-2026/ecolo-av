//! The UDP packet against the examples the Motor Pi's Python checks too
//! (`firmware/udp/wheel_encoder_vectors.txt`).

use wheel_encoder::SpokeDelta;

const VECTORS: &str = include_str!("../../../../udp/wheel_encoder_vectors.txt");

fn vectors() -> impl Iterator<Item = (i32, Vec<u8>)> {
    VECTORS
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(|line| {
            let mut fields = line.split_whitespace();
            let spokes = fields.next().expect("a count").parse().expect("an i32");
            let hex = fields.next().expect("the bytes");
            let bytes = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).expect("hex"))
                .collect();
            (spokes, bytes)
        })
}

#[test]
fn packets_match_the_shared_examples() {
    let mut checked = 0;
    for (spokes, bytes) in vectors() {
        assert_eq!(SpokeDelta(spokes).to_bytes().as_slice(), bytes, "{spokes}");
        assert_eq!(SpokeDelta::from_bytes(&bytes), Ok(SpokeDelta(spokes)));
        checked += 1;
    }
    assert!(checked >= 10, "only {checked} examples");
}
