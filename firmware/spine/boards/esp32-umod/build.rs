//! What the status lines' heartbeat says about this build, and the WiFi's credentials.
//!
//! | Sets | From |
//! |---|---|
//! | `AAV_BUILD` | `git rev-parse --short=7 HEAD`; `unknown` without git |
//! | `AAV_FEATURES` | the features this build has, comma-separated |
//! | `cfg(wifi_secrets)`, `$OUT_DIR/wifi_secrets.rs` | with `wifi-status`: a copy of `src/wifi_secrets.rs` (git ignores it), or of the file `AAV_WIFI_SECRETS` names |
//!
//! The credentials never go in git. Without the file, `main.rs`'s `compile_error!` says how to
//! make it.

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo::rustc-check-cfg=cfg(wifi_secrets)");
    println!("cargo::rerun-if-changed=build.rs");
    println!("cargo::rerun-if-changed=src/wifi_secrets.rs");
    println!("cargo::rerun-if-env-changed=AAV_WIFI_SECRETS");
    // A commit changes the branch's ref, not a file here.
    for path in git_paths() {
        println!("cargo::rerun-if-changed={path}");
    }

    println!("cargo::rustc-env=AAV_BUILD={}", build_id());
    println!("cargo::rustc-env=AAV_FEATURES={}", features());

    if env::var_os("CARGO_FEATURE_WIFI_STATUS").is_some() {
        let source = env::var_os("AAV_WIFI_SECRETS")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("src/wifi_secrets.rs"));
        if let Ok(text) = fs::read_to_string(&source) {
            let out = PathBuf::from(env::var_os("OUT_DIR").expect("cargo sets OUT_DIR"));
            fs::write(out.join("wifi_secrets.rs"), text).expect("OUT_DIR is writable");
            println!("cargo::rustc-cfg=wifi_secrets");
        }
    }
}

fn git(args: &[&str]) -> Option<String> {
    Command::new("git")
        .args(args)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
}

/// HEAD and the branch it points at, wherever this checkout keeps them (a worktree too).
fn git_paths() -> Vec<String> {
    let mut paths: Vec<String> = git(&["rev-parse", "--git-path", "HEAD"])
        .into_iter()
        .collect();
    if let Some(branch) = git(&["symbolic-ref", "-q", "HEAD"]) {
        paths.extend(git(&["rev-parse", "--git-path", &branch]));
    }
    paths
}

/// The short commit; `unknown` without git. (Not "-dirty": this script reruns on a
/// commit, not on every edit, so that mark would go stale.)
fn build_id() -> String {
    git(&["rev-parse", "--short=7", "HEAD"])
        .filter(|commit| !commit.is_empty())
        .unwrap_or_else(|| "unknown".to_owned())
}

/// `legacy-uart,wifi-status`: the build's features, as Cargo names them, sorted.
fn features() -> String {
    let mut names: Vec<String> = env::vars()
        .filter_map(|(key, _)| {
            key.strip_prefix("CARGO_FEATURE_")
                .map(|name| name.to_lowercase().replace('_', "-"))
        })
        .filter(|name| name != "default")
        .collect();
    names.sort();
    names.join(",")
}
