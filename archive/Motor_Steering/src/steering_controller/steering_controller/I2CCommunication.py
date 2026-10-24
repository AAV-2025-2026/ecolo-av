import smbus
import time


class I2CCommunication:
    def __init__(self, device_address, bus_number=1):
        """
        Initialize the I2CCommunication class.

        :param device_address: The I2C address of the device.
        :param bus_number: The bus number (default is 1 for Raspberry Pi).
        """
        # Initialize the I2C bus (1 is typically the default for Raspberry Pi)
        self.bus = smbus.SMBus(bus_number)
        self.device_address = device_address

    def write_data(self, data):
        """
        Write raw data to the I2C device.

        :param data: List of byte data to send
        """
        try:
            # Write a block of data to the device
            self.bus.write_i2c_block_data(self.device_address, 0x00, data)
            print(f"Data written to I2C device: {data}")
        except Exception as e:
            print(f"Failed to write data to I2C: {e}")

    def close(self):
        """
        Close the I2C bus when done.
        """
        self.bus.close()