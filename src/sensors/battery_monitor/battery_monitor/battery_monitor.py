import serial
import rclpy
from VEDirect import VEDirect
from BatteryStatePublisher import BatteryStatePublisher
from HeartbeatPublisher import TimePublisher as HeartbeatPublisher  # the class is named TimePublisher
from sensor_msgs.msg import BatteryState

SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD = 19200
BSP_NODE_NAME = "battery_state_publisher"
BSP_TOPIC_NAME = "/battery_status"
HP_NODE_NAME = "heartbeat_publisher"
HP_TOPIC_NAME = "/battery_monitor_heartbeat"

class BatteryMonitor:
  def __init__(self, sr, vd, bsp, hp):
    self.sr = sr
    self.vd = vd
    self.bsp = bsp
    self.hp = hp

  # When the data is changed we should do stuff
  def dataChanged(self):
    # Check both blocks are present
    if not ("V" in self.vd.data.keys() and "I" in self.vd.data.keys() and "SOC" in self.vd.data.keys() and "VS" in self.vd.data.keys()): return
    print("Sending Data")
    # Convert from dict to ros msg
    msg = self.createBatteryState(self.vd.data)
    # Send over ROS2
    self.bsp.publish_message(msg)
    # Heartbeat (built together so we know that the fullstack [hw to ros] is active)
    self.hp.publish_time()

  def createBatteryState(self, data):
    # Convert dict into ROS BatteryState msg
    msg = BatteryState()
    msg.header.stamp = self.bsp.get_clock().now().to_msg()
    msg.header.frame_id = 'base_link'
    msg.voltage = float(int(data["V"]) / 1000)                                     # V (mV) -> voltage (V)
    msg.temperature = float('nan')
    msg.current = float(int(data["I"]) / 1000)                                     # I (mA) -> current (A)
    msg.charge = float('nan')
    msg.capacity = float('nan')
    msg.design_capacity = float('nan')
    msg.percentage = float(int(data["SOC"]) / 1000)                                # %0 (100.0) -> % (1.000)
    msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
    msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_UNKNOWN
    msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_UNKNOWN
    msg.present = True
    msg.cell_voltage = [float(int(data["V"]) / 1000), float(int(data["VS"]) / 1000)]    # [0] pack voltage, [1] 12V regulator voltage
    msg.cell_temperature = [float('nan'), float('nan')]
    msg.location ="Battery Pack"
    msg.serial_number = "BW12500"

    return msg

def main():
  # Initialize the rclpy library
  rclpy.init()
  # Startup
  print("Created Batery Monitor")
  sr = serial.Serial(SERIAL_PORT, SERIAL_BAUD)
  print("Created Serial Interface on port: " + SERIAL_PORT)
  vd = VEDirect()
  print("Created VEDirect Interface")
  bsp = BatteryStatePublisher(BSP_NODE_NAME, BSP_TOPIC_NAME)
  print("Created Battery State ROS2 Publisher")
  hp = HeartbeatPublisher(HP_NODE_NAME, HP_TOPIC_NAME)
  print("Created Battery Monitor Heartbeat Publisher")
  bm = BatteryMonitor(sr, vd, bsp, hp)
  print("Initialized Battery Monitor")

  # Loop and read serial + initiate dataChanged callback when new data arrives
  while True:
    data = sr.read()
    for byte in data:
      vd.process_byte(byte, bm.dataChanged)
  
  # Cleanup
  bsp.destroy_node()
  rclpy.shutdown()

if __name__ == "__main__":
  # Main
  main()