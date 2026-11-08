//! The node `sim_cameras`: the pictures out on Gazebo's camera topics, the car's pose in.
//!
//! Subscribes: `/vehicle/sim/truth` (nav_msgs/Odometry, map frame: where the simulated car
//! is; only with `--pose truth`).
//! Publishes, for each camera in `config/cameras.yaml`: `<topic>/image_raw`
//! (sensor_msgs/Image, rgb8, the camera's link as frame_id) and, except the chase camera,
//! `<topic>/camera_info` (sensor_msgs/CameraInfo). Reliable, keep last 10: as
//! ros_gz_bridge publishes Gazebo's.
//! Serves and calls nothing.

use std::{sync::mpsc, thread, time::Duration};

use camera_core::{CameraSpec, Frame, Pose, Rig, Rotation, Vec3};
use rclrs::*;
use ros_env::builtin_interfaces::msg::Time;
use ros_env::nav_msgs::msg::Odometry;
use ros_env::sensor_msgs::msg::{CameraInfo, Image};
use ros_env::std_msgs::msg::Header;

const NODE_NAME: &str = "sim_cameras";
/// Where the simulated car is: the simulator's truth.
pub const TRUTH: &str = "/vehicle/sim/truth";

struct Outputs {
    image: Publisher<Image>,
    info: Option<Publisher<CameraInfo>>,
}

/// The node's publishers, and the car's poses as they arrive.
pub struct RosOut {
    outputs: Vec<Outputs>,
    infos: Vec<CameraInfo>,
    frame_ids: Vec<String>,
}

/// A pose of the car at a sim time.
pub type Stamped = (Duration, Pose);

impl RosOut {
    /// Starts the node on its own thread. With `truth`, the car's poses arrive on the
    /// returned receiver, newest last.
    pub fn start(rig: &Rig, truth: bool) -> Result<(Self, mpsc::Receiver<Stamped>), String> {
        let (tx, rx) = mpsc::sync_channel::<Stamped>(256);
        let (ready_tx, ready_rx) = mpsc::channel();
        let specs = rig.cameras.clone();
        thread::Builder::new()
            .name("ros".into())
            .spawn(move || {
                let run = || -> Result<(), RclrsError> {
                    let context = Context::new(
                        std::iter::once(NODE_NAME.to_owned()),
                        InitOptions::default(),
                    )?;
                    let mut executor = context.create_basic_executor();
                    let node = executor.create_node(NODE_NAME)?;
                    let outputs = specs
                        .iter()
                        .map(|c| {
                            Ok(Outputs {
                                image: node.create_publisher(c.image_topic().as_str())?,
                                info: if c.camera_info {
                                    Some(node.create_publisher(c.info_topic().as_str())?)
                                } else {
                                    None
                                },
                            })
                        })
                        .collect::<Result<Vec<_>, RclrsError>>()?;
                    let _truth = if truth {
                        let tx = tx.clone();
                        Some(
                            node.create_subscription(TRUTH.reliable(), move |m: Odometry| {
                                let _ = tx.try_send((stamp_of(&m.header.stamp), pose_of(&m)));
                            })?,
                        )
                    } else {
                        None
                    };
                    let _ = ready_tx.send(Ok(outputs));
                    executor.spin(SpinOptions::default()).first_error()
                };
                if let Err(e) = run() {
                    let _ = ready_tx.send(Err(format!("{e:#}")));
                    eprintln!("sim_cameras: the ROS node stopped: {e:#}");
                }
            })
            .map_err(|e| e.to_string())?;
        let outputs = ready_rx
            .recv()
            .map_err(|_| "the ROS thread ended before the node was up".to_owned())?
            .map_err(|e| format!("starting the ROS node (is ROS sourced?): {e}"))?;
        let infos = rig.cameras.iter().map(camera_info).collect();
        let frame_ids = rig.cameras.iter().map(|c| c.frame_id.clone()).collect();
        Ok((
            Self {
                outputs,
                infos,
                frame_ids,
            },
            rx,
        ))
    }

    /// Publishes one picture and its camera_info, with the same stamp.
    pub fn publish(&self, frame: Frame) -> Result<(), String> {
        let i = frame.camera;
        let header = Header {
            stamp: time_of(frame.stamp),
            frame_id: self.frame_ids[i].clone(),
        };
        let out = &self.outputs[i];
        if let Some(info) = &out.info {
            let mut msg = self.infos[i].clone();
            msg.header = header.clone();
            info.publish(msg).map_err(|e| e.to_string())?;
        }
        let step = frame.step();
        let image = Image {
            header,
            height: frame.height,
            width: frame.width,
            encoding: Frame::ENCODING.to_owned(),
            is_bigendian: 0,
            step,
            data: frame.rgb,
        };
        out.image.publish(image).map_err(|e| e.to_string())
    }
}

/// camera_info as Gazebo's bridge sends it (no header yet).
fn camera_info(spec: &CameraSpec) -> CameraInfo {
    let lens = &spec.lens;
    CameraInfo {
        height: lens.height(),
        width: lens.width(),
        distortion_model: lens.distortion_model().to_owned(),
        d: lens.d().to_vec(),
        k: lens.k(),
        r: lens.r(),
        p: lens.p(),
        ..Default::default()
    }
}

fn stamp_of(t: &Time) -> Duration {
    Duration::new(u64::try_from(t.sec).unwrap_or(0), t.nanosec)
}

fn time_of(d: Duration) -> Time {
    Time {
        sec: i32::try_from(d.as_secs()).unwrap_or(i32::MAX),
        nanosec: d.subsec_nanos(),
    }
}

fn pose_of(m: &Odometry) -> Pose {
    let p = &m.pose.pose;
    let q = &p.orientation;
    Pose::new(
        Vec3::new(p.position.x, p.position.y, p.position.z),
        Rotation::from_quaternion(q.x, q.y, q.z, q.w),
    )
}
