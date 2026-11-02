//! What the `hud` and `map` programs share: the window's place on a computer with two
//! screens ([`window`]), and drawing with a theme ([`paint`]: frosted glass, the
//! background). The `hud` program itself is `main.rs`.

pub mod paint;
pub mod window;
