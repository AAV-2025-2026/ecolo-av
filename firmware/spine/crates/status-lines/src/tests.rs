//! Every line against `firmware/status/golden.jsonl`, byte for byte.

extern crate std;

use super::*;
use std::string::ToString;
use std::vec::Vec;

const GOLDEN: &str = include_str!("../../../../status/golden.jsonl");

fn golden() -> Vec<&'static str> {
    GOLDEN.lines().filter(|l| !l.trim().is_empty()).collect()
}

const CH: [u16; 6] = [1500, 1500, 1500, 1500, 1000, 1000];

fn heartbeat() -> Line<'static> {
    Line {
        seq: 812,
        up_ms: 40210,
        body: Body::Heartbeat(Heartbeat {
            boot_id: 0xa1b2_c3d4,
            build: "abc1234",
            features: "legacy-uart,wifi-status",
            last_reset: "PowerOn",
        }),
    }
}

fn driving() -> Line<'static> {
    Line {
        seq: 813,
        up_ms: 40300,
        body: Body::Status(Status {
            rx: Some(Rx {
                version: 2,
                counter: Some(41),
                check: 17,
                steer: -0.1,
                speed: 0.3,
                accel: 0.0,
                age_ms: 18,
            }),
            out: Out {
                steer_counts: 1755,
                brake_counts: 400,
                dac: 210,
                reverse: false,
            },
            low: Levels {
                steer_counts: 1750,
                brake_counts: 400,
                dac: 204,
            },
            high: Levels {
                steer_counts: 1760,
                brake_counts: 400,
                dac: 210,
            },
            pos: Positions {
                steer: Some(1762),
                brake: None,
            },
            link: LinkCounts {
                frames: 12040,
                bad: 0,
                skipped: 0,
                repeats: 3,
                verdict: Some(Verdict::Ok),
            },
            rc: Rc {
                switch: Switch::Computer,
                channels: &CH,
            },
            state: State {
                mode: Mode::Computer,
                armed: true,
                estop: false,
                faults: 0,
            },
            tick: Tick {
                worst_gap_us: 10840,
                overruns: 0,
            },
        }),
    }
}

fn stopped() -> Line<'static> {
    let out = Out {
        steer_counts: 1950,
        brake_counts: 3500,
        dac: 0,
        reverse: false,
    };
    Line {
        seq: 814,
        up_ms: 40400,
        body: Body::Status(Status {
            rx: None,
            out,
            low: Levels::from(&out),
            high: Levels::from(&out),
            pos: Positions::default(),
            link: LinkCounts {
                verdict: Some(Verdict::NoFrames),
                ..LinkCounts::default()
            },
            rc: Rc {
                switch: Switch::NoSignal,
                channels: &[],
            },
            state: State {
                mode: Mode::Stopped,
                armed: false,
                estop: false,
                faults: 256,
            },
            tick: Tick {
                worst_gap_us: 10840,
                overruns: 0,
            },
        }),
    }
}

fn event() -> Line<'static> {
    Line {
        seq: 815,
        up_ms: 40410,
        body: Body::Event(Event {
            what: "mode",
            from: Value::Text("rc"),
            to: Value::Text("computer"),
        }),
    }
}

fn config() -> Line<'static> {
    Line {
        seq: 816,
        up_ms: 40420,
        body: Body::Config(Config {
            build: "abc1234",
            features: "legacy-uart,wifi-status",
            version: "0.1.0",
            link: "uart",
            frame_version: Some(2),
            tick_ms: 10,
            watchdog_ms: 100,
            cmd_timeout_ms: 100,
            idle_brake: 1.0,
            full_throttle_speed: 3.0,
            i2c_khz: Some(100),
            addresses: Addresses {
                steering: 0x05,
                brake: 0x04,
                dac: 0x0C,
                expander: 0x20,
            },
            steering: SteeringLimits {
                min: 400,
                centre: 1950,
                max: 3500,
            },
            brake: BrakeLimits {
                released: 400,
                full: 3500,
            },
            throttle_full_code: 700,
            last_reset: "PowerOn",
        }),
    }
}

const TODAYS_DEVICES: [DeviceSeen<'static>; 4] = [
    DeviceSeen {
        name: "steering",
        address: 0x05,
        answered: true,
        feedback: Some("analog"),
    },
    DeviceSeen {
        name: "brake",
        address: 0x04,
        answered: true,
        feedback: Some("none"),
    },
    DeviceSeen {
        name: "dac",
        address: 0x0C,
        answered: true,
        feedback: None,
    },
    DeviceSeen {
        name: "expander",
        address: 0x20,
        answered: true,
        feedback: None,
    },
];

fn devices() -> Line<'static> {
    Line {
        seq: 817,
        up_ms: 40430,
        body: Body::Devices(DeviceList {
            devices: &TODAYS_DEVICES,
        }),
    }
}

fn health() -> Line<'static> {
    Line {
        seq: 818,
        up_ms: 40500,
        body: Body::Health(Health {
            link: Some(Verdict::Ok),
            age_ms: Some(18),
            counter_moving: Some(true),
            counts: LinkCounts {
                frames: 12040,
                bad: 0,
                skipped: 0,
                repeats: 3,
                verdict: Some(Verdict::Ok),
            },
            devices_answered: 4,
            devices_expected: 4,
            missing: &[],
            faults: 0,
            mode: Mode::Computer,
            last_reset: "PowerOn",
            build: "abc1234",
            boot_id: 0xa1b2_c3d4,
        }),
    }
}

#[test]
fn each_line_is_the_golden_one_byte_for_byte() {
    let lines = [
        heartbeat(),
        driving(),
        stopped(),
        event(),
        config(),
        devices(),
        health(),
    ];
    let golden = golden();
    assert_eq!(
        golden.len(),
        lines.len(),
        "golden.jsonl changed: add its lines here"
    );
    for (line, want) in lines.iter().zip(golden) {
        let mut buf = [0; MAX_LINE];
        assert_eq!(line.write_to(&mut buf).unwrap(), want);
        assert_eq!(line.to_string(), want);
        let mut lb = LineBuf::<MAX_LINE>::new();
        lb.set(line).unwrap();
        assert_eq!(lb.as_str(), want);
        assert_eq!(lb.as_bytes(), want.as_bytes());
    }
}

#[test]
fn every_golden_line_has_the_fields_every_reader_needs() {
    for line in golden() {
        for field in [r#"{"t":""#, r#""schema":1,"#, r#""seq":"#, r#""up_ms":"#] {
            assert!(line.contains(field), "{line}: {field}");
        }
    }
}

#[test]
fn a_buffer_too_small_says_so_and_holds_nothing() {
    let mut buf = [0; 40];
    assert_eq!(driving().write_to(&mut buf), Err(TooLong));
    let mut lb = LineBuf::<40>::new();
    lb.set(&event()).unwrap_err();
    assert!(lb.is_empty());
    assert_eq!(lb.as_str(), "");
}

#[test]
fn the_widest_status_line_fits_max_line() {
    let ch = [u16::MAX; MAX_CHANNELS + 4]; // more than are written
    let wide = Levels {
        steer_counts: u16::MAX,
        brake_counts: u16::MAX,
        dac: u16::MAX,
    };
    let line = Line {
        seq: u32::MAX,
        up_ms: u32::MAX,
        body: Body::Status(Status {
            rx: Some(Rx {
                version: u8::MAX,
                counter: Some(u8::MAX),
                check: u8::MAX,
                steer: -1.175_494_4e-38,
                speed: -3.402_823_5e38,
                accel: -1e-45,
                age_ms: u32::MAX,
            }),
            out: Out {
                steer_counts: u16::MAX,
                brake_counts: u16::MAX,
                dac: u16::MAX,
                reverse: false,
            },
            low: wide,
            high: wide,
            pos: Positions {
                steer: Some(u16::MAX),
                brake: Some(u16::MAX),
            },
            link: LinkCounts {
                frames: u32::MAX,
                bad: u32::MAX,
                skipped: u32::MAX,
                repeats: u32::MAX,
                verdict: Some(Verdict::CounterFrozen),
            },
            rc: Rc {
                switch: Switch::NoSignal,
                channels: &ch,
            },
            state: State {
                mode: Mode::Computer,
                armed: false,
                estop: false,
                faults: u16::MAX,
            },
            tick: Tick {
                worst_gap_us: u32::MAX,
                overruns: u32::MAX,
            },
        }),
    };
    let text = line.to_string();
    assert_eq!(
        text.len(),
        783,
        "the widest line: change MAX_LINE's note too"
    );
    let written = std::format!(r#""ch":[{}]"#, ["65535"; MAX_CHANNELS].join(","));
    assert!(
        text.contains(&written),
        "only {MAX_CHANNELS} channels: {text}"
    );
    let mut buf = [0; MAX_LINE];
    assert!(line.write_to(&mut buf).is_ok());
}

#[test]
fn values_json_cannot_hold_are_null() {
    let Body::Status(mut s) = driving().body else {
        unreachable!()
    };
    s.rx = Some(Rx {
        steer: f32::NAN,
        speed: f32::INFINITY,
        accel: -0.0,
        counter: None,
        ..s.rx.unwrap()
    });
    let text = Line {
        seq: 1,
        up_ms: 2,
        body: Body::Status(s),
    }
    .to_string();
    assert!(text.contains(r#""counter":null,"#), "{text}");
    assert!(
        text.contains(r#""steer":null,"speed":null,"accel":-0.0,"#),
        "{text}"
    );
}

#[test]
fn small_and_large_floats_stay_json() {
    let s = |v: f32| json::Float(v).to_string();
    assert_eq!(s(0.0), "0.0");
    assert_eq!(s(-0.1), "-0.1");
    assert_eq!(s(1.0), "1.0");
    assert_eq!(s(1e-7), "1e-7");
    assert_eq!(s(1e20), "1e20");
}

#[test]
fn text_is_escaped() {
    let line = Line {
        seq: 0,
        up_ms: 0,
        body: Body::Event(Event {
            what: "a\"b\\c\nd\u{1}",
            from: Value::Flag(false),
            to: Value::Number(256),
        }),
    };
    assert_eq!(
        line.to_string(),
        r#"{"t":"event","schema":1,"seq":0,"up_ms":0,"what":"a\"b\\c\nd\u0001","from":false,"to":256}"#
    );
}

#[test]
fn health_and_devices_say_what_is_missing_and_what_isnt_judged() {
    let Body::Health(mut h) = health().body else {
        unreachable!()
    };
    h.link = None;
    h.age_ms = None;
    h.counter_moving = None;
    h.devices_answered = 2;
    h.missing = &["steering", "dac"];
    let text = Line {
        seq: 1,
        up_ms: 2,
        body: Body::Health(h),
    }
    .to_string();
    assert!(
        text.contains(r#""link":null,"age_ms":null,"counter_moving":null,"#),
        "{text}"
    );
    assert!(
        text.contains(r#""answered":2,"expected":4,"missing":["steering","dac"]}"#),
        "{text}"
    );
    let mut list = TODAYS_DEVICES;
    list[0].answered = false;
    list[0].feedback = None;
    let text = Line {
        seq: 1,
        up_ms: 2,
        body: Body::Devices(DeviceList { devices: &list }),
    }
    .to_string();
    assert!(text.contains(r#""answered":3,"expected":4,"#), "{text}");
    assert!(
        text.contains(r#"{"name":"steering","address":5,"answered":false,"feedback":null}"#),
        "{text}"
    );
}

#[test]
fn a_config_on_can_in_qemu_writes_nulls_and_fits() {
    let Body::Config(mut c) = config().body else {
        unreachable!()
    };
    c.link = "can";
    c.frame_version = None;
    c.i2c_khz = None;
    let line = Line {
        seq: u32::MAX,
        up_ms: u32::MAX,
        body: Body::Config(c),
    };
    let text = line.to_string();
    assert!(
        text.contains(r#""link":"can","frame_version":null,"#),
        "{text}"
    );
    assert!(text.contains(r#""i2c_khz":null,"#), "{text}");
    let mut buf = [0; MAX_LINE];
    assert!(line.write_to(&mut buf).is_ok());
}

#[test]
fn names_are_the_contracts() {
    let names: Vec<_> = [
        Verdict::NoFrames,
        Verdict::Ok,
        Verdict::Stale,
        Verdict::CounterFrozen,
        Verdict::BadFrames,
    ]
    .iter()
    .map(|v| v.name())
    .collect();
    assert_eq!(
        names,
        ["no_frames", "ok", "stale", "counter_frozen", "bad_frames"]
    );
    let names: Vec<_> = [Mode::Stopped, Mode::Rc, Mode::Computer, Mode::Test]
        .iter()
        .map(|m| m.name())
        .collect();
    assert_eq!(names, ["stopped", "rc", "computer", "test"]);
    let names: Vec<_> = [
        Switch::Computer,
        Switch::ViaRos,
        Switch::Direct,
        Switch::NoSignal,
    ]
    .iter()
    .map(|s| s.name())
    .collect();
    assert_eq!(names, ["computer", "via_ros", "direct", "no_signal"]);
}
