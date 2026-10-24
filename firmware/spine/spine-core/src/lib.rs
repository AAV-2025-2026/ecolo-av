//! Hardware-independent spine logic. Placeholder until T3.6.
#![cfg_attr(not(test), no_std)]

/// Commands older than this are stale and the spine brakes (proposal section 3.1, layer 8).
pub const COMMAND_TIMEOUT_MS: u32 = 100;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_timeout_matches_proposal() {
        assert_eq!(COMMAND_TIMEOUT_MS, 100);
    }
}
