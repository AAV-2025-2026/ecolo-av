import carla

client = carla.Client("localhost", 2000)
client.set_timeout(20.0)

xodr_path = "/media/aav/DataDrive1/DigitalTwins/CarletonMap/carleton.xodr"

with open(xodr_path, 'r') as f:
    xodr_data = f.read()

params = carla.OpendriveGenerationParameters(
    vertex_distance=2.0,
    max_road_length=50.0,
    wall_height=1.0,
    additional_width=0.6,
    smooth_junctions=True,
    enable_mesh_visibility=True,
    enable_pedestrian_navigation=True
)

world = client.generate_opendrive_world(xodr_data, params)

print("Carleton.xodr loaded successfully.")
