//! Drawing with a theme, for `hud` and `map`: hud_core's colours as raylib's, the
//! window's soft background, and frosted-glass panels.
//!
//! The colours themselves are in `hud_core::theme`; nothing here picks one.

use hud_core::theme::{Rgba, Theme};
use raylib::prelude::*;

/// hud_core's colour as raylib's.
pub trait ToColor {
    fn rl(self) -> Color;
}

impl ToColor for Rgba {
    fn rl(self) -> Color {
        Color::new(self.r, self.g, self.b, self.a)
    }
}

/// How many segments each rounded corner gets: smooth at any size we draw.
const CORNER_SEGMENTS: i32 = 12;

/// raylib's roundness (0 to 1, of the shorter side) for corners `radius` pixels round.
pub fn roundness(r: Rectangle, radius: f32) -> f32 {
    let short = r.width.min(r.height);
    if short <= 0.0 {
        0.0
    } else {
        (2.0 * radius / short).clamp(0.0, 1.0)
    }
}

/// A rounded rectangle, filled: corners `radius` pixels round.
pub fn rounded(d: &mut impl RaylibDraw, r: Rectangle, radius: f32, fill: Rgba) {
    d.draw_rectangle_rounded(r, roundness(r, radius), CORNER_SEGMENTS, fill.rl());
}

/// A rounded rectangle's edge, `thick` pixels.
pub fn rounded_edge(d: &mut impl RaylibDraw, r: Rectangle, radius: f32, thick: f32, edge: Rgba) {
    d.draw_rectangle_rounded_lines_ex(r, roundness(r, radius), CORNER_SEGMENTS, thick, edge.rl());
}

/// A frosted-glass panel: a see-through fill, a soft edge, and a faint shine along its
/// top, as light catches glass. `px`: one line's width (the window's scale).
pub fn glass(
    d: &mut impl RaylibDraw,
    r: Rectangle,
    radius: f32,
    fill: Rgba,
    theme: &Theme,
    px: f32,
) {
    rounded(d, r, radius, fill);
    rounded_edge(d, r, radius, px, theme.glass_edge);
    let inset = radius.max(2.0 * px);
    if r.width > 2.0 * inset {
        let y = r.y + 1.5 * px;
        d.draw_line_ex(
            Vector2::new(r.x + inset, y),
            Vector2::new(r.x + r.width - inset, y),
            px,
            theme.glass_shine.rl(),
        );
    }
}

/// The window's background: a soft gradient, top to bottom, and two faint glows (top
/// left, bottom right) for the glass to show against.
pub fn backdrop(d: &mut impl RaylibDraw, width: i32, height: i32, theme: &Theme) {
    d.draw_rectangle_gradient_v(
        0,
        0,
        width,
        height,
        theme.background.rl(),
        theme.background_low.rl(),
    );
    let reach = width.max(height) as f32 * 0.55;
    for (glow, x, y) in [
        (theme.glow_a, width / 5, height / 6),
        (theme.glow_b, width * 4 / 5, height * 5 / 6),
    ] {
        d.draw_circle_gradient(x, y, reach, glow.rl(), glow.alpha(0).rl());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corners_are_a_radius_whatever_the_size() {
        let wide = Rectangle::new(0.0, 0.0, 400.0, 100.0);
        assert!((roundness(wide, 10.0) - 0.2).abs() < 1e-6);
        let tall = Rectangle::new(0.0, 0.0, 50.0, 300.0);
        assert!((roundness(tall, 10.0) - 0.4).abs() < 1e-6);
        // Never more than a pill, never less than square.
        assert_eq!(roundness(wide, 500.0), 1.0);
        assert_eq!(roundness(Rectangle::new(0.0, 0.0, 0.0, 10.0), 5.0), 0.0);
    }

    #[test]
    fn colours_carry_over() {
        let c = Rgba::hex(0x1e1e2e).alpha(10).rl();
        assert_eq!((c.r, c.g, c.b, c.a), (0x1e, 0x1e, 0x2e, 10));
    }
}
