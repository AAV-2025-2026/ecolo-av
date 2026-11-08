//! Nav2's Savitzky-Golay smoothing of the control sequence (utils::savitskyGolayFilter).
//!
//! A 9-point quadratic filter, (-21, 14, 39, 54, 59, 54, 39, 14, -21) / 231, run along
//! each control (speed, steering), with the last four commands sent standing in for the
//! points before the sequence's start. Sequences shorter than 21 steps are left alone.

use crate::model::Command;

const FILTER: [f64; 9] = [-21.0, 14.0, 39.0, 54.0, 59.0, 54.0, 39.0, 14.0, -21.0];

/// The last four commands sent, oldest first.
pub type History = [Command; 4];

fn smooth_axis(sequence: &mut [f64], history: [f64; 4]) {
    let n = sequence.len() - 1;
    let initial = sequence.to_vec();
    let at = |i: usize| initial[i.min(n)];
    let mut window = [
        history[0],
        history[1],
        history[2],
        history[3],
        at(0),
        at(1),
        at(2),
        at(3),
        at(4),
    ];
    for (idx, out) in sequence.iter_mut().take(n).enumerate() {
        *out = window.iter().zip(FILTER).map(|(v, f)| v * f).sum::<f64>() / 231.0;
        window.rotate_left(1);
        window[8] = at(idx + 5);
    }
}

/// Smooth `sequence` in place, then record its first command (the one sent) in `history`.
pub fn savitzky_golay(sequence: &mut [Command], history: &mut History) {
    if sequence.len() < 21 {
        return;
    }
    let mut speeds: Vec<f64> = sequence.iter().map(|c| c.speed).collect();
    let mut steers: Vec<f64> = sequence.iter().map(|c| c.steer).collect();
    smooth_axis(&mut speeds, history.map(|c| c.speed));
    smooth_axis(&mut steers, history.map(|c| c.steer));
    for ((c, v), s) in sequence.iter_mut().zip(speeds).zip(steers) {
        *c = Command::new(v, s);
    }
    history.rotate_left(1);
    history[3] = sequence[0];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filter_sums_to_one() {
        assert!((FILTER.iter().sum::<f64>() - 231.0).abs() < 1e-12);
    }

    #[test]
    fn keeps_a_constant_and_a_straight_line() {
        // A quadratic filter passes lines through untouched (away from the ends).
        let mut seq: Vec<Command> = (0..56)
            .map(|i| Command::new(1.0, 0.01 * f64::from(i)))
            .collect();
        let mut history = [-4.0, -3.0, -2.0, -1.0].map(|i| Command::new(1.0, 0.01 * i));
        savitzky_golay(&mut seq, &mut history);
        for (i, c) in seq.iter().enumerate().take(50) {
            assert!((c.speed - 1.0).abs() < 1e-12);
            assert!(
                (c.steer - 0.01 * i as f64).abs() < 1e-12,
                "{i}: {}",
                c.steer
            );
        }
        assert_eq!(history[3], seq[0]);
    }

    #[test]
    fn smooths_noise() {
        let mut seq: Vec<Command> = (0..56)
            .map(|i| Command::new(0.0, if i % 2 == 0 { 0.1 } else { -0.1 }))
            .collect();
        let before: f64 = seq.iter().map(|c| c.steer.abs()).sum();
        let mut history = [Command::default(); 4];
        savitzky_golay(&mut seq, &mut history);
        let after: f64 = seq.iter().map(|c| c.steer.abs()).sum();
        assert!(after < 0.2 * before, "{after} vs {before}");
    }

    #[test]
    fn short_sequences_are_left_alone() {
        let mut seq = vec![Command::new(1.0, 0.3); 10];
        let mut history = [Command::default(); 4];
        savitzky_golay(&mut seq, &mut history);
        assert!(seq.iter().all(|c| *c == Command::new(1.0, 0.3)));
    }
}
