//! A [`SimWorld`] as Bevy entities: meshes, materials, the sky, the sun.

use std::f32::consts::FRAC_PI_2;

use bevy::image::{ImageAddressMode, ImageSampler, ImageSamplerDescriptor};
use bevy::{
    asset::RenderAssetUsages,
    camera::{visibility::RenderLayers, Exposure},
    light::CascadeShadowConfigBuilder,
    mesh::{Indices, PrimitiveTopology},
    prelude::*,
    render::render_resource::{Extent3d, TextureDimension, TextureFormat},
};
use camera_core::{Geometry, Look, Shape, SimWorld, TriMesh};
use std::path::Path;

use crate::{transform, CarRoot, RenderError};

/// The exposure every camera uses (Bevy's default, Blender's), as a multiplier.
fn exposure() -> f32 {
    Exposure::BLENDER.exposure()
}

/// Spawns the world; returns every entity, to remove them when the world changes.
pub(crate) fn spawn(
    ecs: &mut World,
    world: &SimWorld,
    car_layer: usize,
) -> Result<Vec<Entity>, RenderError> {
    let sky = Color::linear_rgb(world.sky.r, world.sky.g, world.sky.b);
    ecs.insert_resource(ClearColor(sky));
    // Ambient: a white surface comes out `ambient` grey (Bevy's ambient is in nits,
    // scaled by the camera's exposure).
    ecs.insert_resource(GlobalAmbientLight {
        color: Color::WHITE,
        brightness: world.ambient / exposure(),
        ..default()
    });
    let mut out = Vec::new();
    if let Some(sun) = world.sun {
        // Lambert's diffuse is albedo / pi times the light: so lux = strength * pi / exposure.
        let lux = sun.strength * std::f32::consts::PI / exposure();
        let d = sun.direction;
        let dir = Vec3::new(d.x as f32, d.y as f32, d.z as f32).normalize_or(Vec3::NEG_Z);
        let id = ecs
            .spawn((
                DirectionalLight {
                    illuminance: lux,
                    shadow_maps_enabled: true,
                    ..default()
                },
                // Two cascades out to 60 m: shadows cost the GPU about half its time
                // with Bevy's four out to 150 m (measured on an M4 Max).
                CascadeShadowConfigBuilder {
                    num_cascades: 2,
                    first_cascade_far_bound: 15.0,
                    maximum_distance: 60.0,
                    ..default()
                }
                .build(),
                // A directional light shines along its -z.
                Transform::default().looking_to(dir, Vec3::Z),
                RenderLayers::from_layers(&[0, car_layer]),
            ))
            .id();
        out.push(id);
    }
    for shape in &world.shapes {
        out.push(spawn_shape(ecs, shape, RenderLayers::layer(0), None)?);
    }
    if !world.car.is_empty() {
        let root = ecs
            .spawn((CarRoot, Transform::default(), Visibility::default()))
            .id();
        out.push(root);
        for shape in &world.car {
            spawn_shape(ecs, shape, RenderLayers::layer(car_layer), Some(root))?;
        }
    }
    Ok(out)
}

fn spawn_shape(
    ecs: &mut World,
    shape: &Shape,
    layers: RenderLayers,
    parent: Option<Entity>,
) -> Result<Entity, RenderError> {
    let mesh = mesh(&shape.geometry)?;
    let mesh = ecs.resource_mut::<Assets<Mesh>>().add(mesh);
    let material = material(ecs, &shape.look)?;
    let mut e = ecs.spawn((
        Mesh3d(mesh),
        MeshMaterial3d(material),
        transform(&shape.pose),
        layers,
        Name::new(shape.name.clone()),
    ));
    if let Some(parent) = parent {
        e.insert(ChildOf(parent));
    }
    Ok(e.id())
}

/// SDF's shapes in SDF's own axes (a cylinder along z, a plane facing z).
fn mesh(geometry: &Geometry) -> Result<Mesh, RenderError> {
    Ok(match *geometry {
        Geometry::Plane { x, y } => {
            Plane3d::new(Vec3::Z, Vec2::new(x as f32 / 2.0, y as f32 / 2.0))
                .mesh()
                .build()
        }
        Geometry::Cuboid { x, y, z } => Cuboid::new(x as f32, y as f32, z as f32).mesh().build(),
        Geometry::Cylinder { radius, length } => Cylinder::new(radius as f32, length as f32)
            .mesh()
            .resolution(24)
            .build()
            .rotated_by(Quat::from_rotation_x(FRAC_PI_2)),
        Geometry::Octagon { across, thickness } => octagon(across as f32, thickness as f32),
        Geometry::Mesh { ref file, scale } => obj_mesh(file, scale)?,
    })
}

/// An OBJ file, as triangles with the file's normals and picture coordinates.
fn obj_mesh(file: &Path, scale: [f64; 3]) -> Result<Mesh, RenderError> {
    let text = std::fs::read_to_string(file)
        .map_err(|e| RenderError::Mesh(format!("{}: {e}", file.display())))?;
    let soup = TriMesh::from_obj(&text)
        .map_err(|e| RenderError::Mesh(format!("{}: {e}", file.display())))?
        .scaled(scale.map(|s| s as f32));
    // OBJ's v grows upwards; a picture's rows go down.
    let uvs: Vec<[f32; 2]> = soup.uvs.iter().map(|[u, v]| [*u, 1.0 - v]).collect();
    Ok(Mesh::new(
        PrimitiveTopology::TriangleList,
        RenderAssetUsages::RENDER_WORLD,
    )
    .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, soup.positions)
    .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, soup.normals)
    .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uvs))
}

/// A picture, tiled (the campus's road and grass repeat every few metres), with its
/// smaller copies (mipmaps), so a far-off road is its average colour, not a flicker.
fn tiled_image(picture: image::RgbaImage) -> Image {
    let (w, h) = picture.dimensions();
    let levels = 32 - w.max(h).max(1).leading_zeros();
    let mut data = picture.as_raw().clone();
    let mut level = picture;
    for _ in 1..levels {
        let (lw, lh) = ((level.width() / 2).max(1), (level.height() / 2).max(1));
        level = image::imageops::resize(&level, lw, lh, image::imageops::FilterType::Triangle);
        data.extend_from_slice(level.as_raw());
    }
    let mut img = Image::new_uninit(
        Extent3d {
            width: w,
            height: h,
            depth_or_array_layers: 1,
        },
        TextureDimension::D2,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::RENDER_WORLD,
    );
    img.data = Some(data);
    img.texture_descriptor.mip_level_count = levels;
    let mut sampler = ImageSamplerDescriptor::linear();
    sampler.set_address_mode(ImageAddressMode::Repeat);
    sampler.set_anisotropic_filter(16);
    img.sampler = ImageSampler::Descriptor(sampler);
    img
}

/// A flat octagon facing +x, its flats up, down and to the sides. The picture's square
/// fills the square around it: its right edge at +y (seen from in front, +x).
fn octagon(across: f32, thickness: f32) -> Mesh {
    let r = across / 2.0 / (std::f32::consts::PI / 8.0).cos();
    let corners: Vec<Vec2> = (0..8)
        .map(|k| {
            let a = std::f32::consts::PI / 8.0 + k as f32 * std::f32::consts::PI / 4.0;
            Vec2::new(r * a.cos(), r * a.sin()) // (y, z)
        })
        .collect();
    let mut positions = Vec::new();
    let mut normals = Vec::new();
    let mut uvs = Vec::new();
    let mut indices = Vec::new();
    for (x, normal) in [(thickness / 2.0, 1.0f32), (-thickness / 2.0, -1.0)] {
        let base = positions.len() as u32;
        for p in std::iter::once(Vec2::ZERO).chain(corners.iter().copied()) {
            positions.push([x, p.x, p.y]);
            normals.push([normal, 0.0, 0.0]);
            uvs.push([0.5 + p.x / across, 0.5 - p.y / across]);
        }
        for k in 0..8u32 {
            let (a, b) = (base + 1 + k, base + 1 + (k + 1) % 8);
            // Counter-clockwise seen from the side the normal points to.
            if normal > 0.0 {
                indices.extend([base, a, b]);
            } else {
                indices.extend([base, b, a]);
            }
        }
    }
    Mesh::new(
        PrimitiveTopology::TriangleList,
        RenderAssetUsages::RENDER_WORLD,
    )
    .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, positions)
    .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, normals)
    .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uvs)
    .with_inserted_indices(Indices::U32(indices))
}

fn material(ecs: &mut World, look: &Look) -> Result<Handle<StandardMaterial>, RenderError> {
    let texture = match &look.texture {
        Some(path) => {
            let picture = image::open(path)
                .map_err(|e| RenderError::Texture(format!("{}: {e}", path.display())))?
                .to_rgba8();
            Some(
                ecs.resource_mut::<Assets<Image>>()
                    .add(tiled_image(picture)),
            )
        }
        None => None,
    };
    let c = look.colour;
    Ok(ecs
        .resource_mut::<Assets<StandardMaterial>>()
        .add(StandardMaterial {
            base_color: Color::linear_rgb(c.r, c.g, c.b),
            base_color_texture: texture,
            // Matte, as Gazebo's plain materials: almost no shine.
            perceptual_roughness: 0.95,
            reflectance: 0.05,
            ..default()
        }))
}
