from aav_battery_victron.BatteryStatePublisher import BatteryStatePublisher

# The class is named TimePublisher.
from aav_battery_victron.HeartbeatPublisher import TimePublisher as HeartbeatPublisher
from aav_battery_victron.VEDirect import VEDirect
import rclpy
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import BatteryState
import serial

BSP_NODE_NAME = 'battery_state_publisher'
BSP_TOPIC_NAME = '/vehicle/battery'
HP_NODE_NAME = 'heartbeat_publisher'
HP_TOPIC_NAME = '/vehicle/battery/heartbeat'
READINGS = ('V', 'I', 'SOC', 'VS')


class BatteryMonitor:
    def __init__(self, sr, vd, bsp, hp):
        self.sr = sr
        self.vd = vd
        self.bsp = bsp
        self.hp = hp

    # When the data is changed we should do stuff
    def dataChanged(self):
        # Check both blocks are present
        if not (
            'V' in self.vd.data.keys()
            and 'I' in self.vd.data.keys()
            and 'SOC' in self.vd.data.keys()
            and 'VS' in self.vd.data.keys()
        ):
            return
        # Publish only when this block brought a reading. A monitor also sends blocks of
        # history (H1, H2...): publishing on those re-sent old readings as new ones.
        if not any(key in self.vd.last_block for key in READINGS):
            return
        print('Sending Data')
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
        msg.voltage = float(int(data['V']) / 1000)  # V (mV) -> voltage (V)
        msg.temperature = float('nan')
        msg.current = float(int(data['I']) / 1000)  # I (mA) -> current (A)
        msg.charge = float('nan')
        msg.capacity = float('nan')
        msg.design_capacity = float('nan')
        msg.percentage = float(int(data['SOC']) / 1000)  # %0 (100.0) -> % (1.000)
        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_UNKNOWN
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_UNKNOWN
        msg.present = True
        msg.cell_voltage = [
            float(int(data['V']) / 1000),
            float(int(data['VS']) / 1000),
        ]  # [0] pack voltage, [1] 12V regulator voltage
        msg.cell_temperature = [float('nan'), float('nan')]
        msg.location = 'Battery Pack'
        msg.serial_number = 'BW12500'

        return msg


def main():
    # Initialize the rclpy library
    rclpy.init()
    # Startup
    bsp = BatteryStatePublisher(BSP_NODE_NAME, BSP_TOPIC_NAME)
    print('Created Battery State ROS2 Publisher')
    # The udev name from tools/udev/99-aav.rules
    port = bsp.declare_parameter('port', '/dev/aav/battery').value
    baud = bsp.declare_parameter('baud', 19200).value
    sr = serial.Serial(port, baud)
    print('Created Serial Interface on port: ' + port)
    vd = VEDirect()
    print('Created VEDirect Interface')
    hp = HeartbeatPublisher(HP_NODE_NAME, HP_TOPIC_NAME)
    print('Created Battery Monitor Heartbeat Publisher')
    bm = BatteryMonitor(sr, vd, bsp, hp)
    print('Initialized Battery Monitor')

    # Loop and read serial + initiate dataChanged callback when new data arrives
    try:
        while rclpy.ok():
            data = sr.read()
            for byte in data:
                vd.process_byte(byte, bm.dataChanged)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # Cleanup
        sr.close()
        hp.destroy_node()
        bsp.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    # Main
    main()
