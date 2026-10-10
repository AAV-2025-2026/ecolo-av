# VEDirect Class
# Serial line format [KEY \t VALUE \r \n]
# State equivalent   [KEY -> VALUE -> NL] use \t and \r to transition
from enum import Enum


class VEDirect:
  
  # Enum for serial state
  class SerialState(Enum):
    KEY = 0,      # Next bytes are key
    VALUE = 1,    # Next bytes are value
    NL = 2        # Next bytes are line feed
  
  # Constructor
  def __init__(self):
    self.state = VEDirect.SerialState.NL
    self.data = {}
    self.currentdict = {}
    self.currentkey = ""
    self.currentvalue = ""

  # Read byte from serial
  def process_byte(self, byte, block_callback):
    match self.state:
      case VEDirect.SerialState.KEY:
        # Check for tab to move to value
        if byte == ord("\t"):
          self.state = VEDirect.SerialState.VALUE
        else:
          # Add to currentKey
          self.currentkey += chr(byte)
      
      case VEDirect.SerialState.VALUE:
        # Check for carriage return to move to nl
        if byte == ord("\r"):
          self.state = VEDirect.SerialState.NL
          # Add current key/value as element in dict
          self.currentdict[self.currentkey] = self.currentvalue
          # If the key was a checksum then we have reached the end of the block
          if(self.currentkey == "Checksum"):
            if self.set_block(self.currentdict):
              block_callback()
            self.currentdict = {}
          # Wipe
          self.currentkey = ""
          self.currentvalue = ""
        else:
          # Add to currentValue
          self.currentvalue += chr(byte)
      
      case VEDirect.SerialState.NL:
        # Wait on line feed
        if byte == ord("\n"):
          self.state = VEDirect.SerialState.KEY
          # Move the current 

  def check_checksum(self, block):
    calc_checksum = 0

    # Calculate the checksum
    for key, value in block.items():
      # Account for /t and /r/n
      calc_checksum = (calc_checksum + ord("\t") + ord("\r") + ord("\n")) % 256
      # Add the key and value
      for chr in key:
        calc_checksum = (calc_checksum + ord(chr)) % 256
      for chr in value:
        calc_checksum = (calc_checksum + ord(chr)) % 256
    
    return calc_checksum == 0

  # Attempt to set a block of incoming data, fails if invalid checksum
  def set_block(self, block):
    # Check checksum
    if not self.check_checksum(block):
      print("WARN: bad checksum, discarding block")
      return False
    # Remove checksum
    block.pop("Checksum")
    # Update data
    self.data.update(block)
    return True