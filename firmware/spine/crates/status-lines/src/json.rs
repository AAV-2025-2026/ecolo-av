//! The few JSON forms the lines need: a quoted string, a number that may be absent, a float.

use core::fmt::{self, Display, Formatter, Write};

/// A string, quoted, with `"`, `\` and control characters escaped.
pub(crate) struct Text<'a>(pub &'a str);

impl Display for Text<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_char('"')?;
        for c in self.0.chars() {
            match c {
                '"' => f.write_str("\\\"")?,
                '\\' => f.write_str("\\\\")?,
                '\n' => f.write_str("\\n")?,
                '\r' => f.write_str("\\r")?,
                '\t' => f.write_str("\\t")?,
                c if u32::from(c) < 0x20 => write!(f, "\\u{:04x}", u32::from(c))?,
                c => f.write_char(c)?,
            }
        }
        f.write_char('"')
    }
}

/// An `f32` as JSON: the shortest form that reads back as the same `f32` (`0.0`, `-0.1`,
/// `1e-7`), or `null` when it is not finite. JSON has no NaN or infinity.
pub(crate) struct Float(pub f32);

impl Display for Float {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        if self.0.is_finite() {
            // Debug, not Display: Display writes 0.0 as "0", and the contract has "0.0".
            write!(f, "{:?}", self.0)
        } else {
            f.write_str("null")
        }
    }
}

/// A number, or `null`.
pub(crate) fn option<T: Display>(f: &mut Formatter<'_>, value: Option<T>) -> fmt::Result {
    match value {
        Some(v) => write!(f, "{v}"),
        None => f.write_str("null"),
    }
}
