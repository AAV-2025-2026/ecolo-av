# send_cmd.py
import socket
import struct
import time

# Wire format:
#   16 bytes  ackermann payload (opaque)
#    4 bytes  freshness_ms (uint32 big-endian)
#    1 byte   priority (uint8)

VM_IP        = "192.168.56.104"  # change to your VM's actual IP
VM_PORT      = 5000
PACKET_SIZE  = 21

def send_command(ackermann_bytes, freshness_ms, priority):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = ackermann_bytes + struct.pack(">IB", freshness_ms, priority)
    sock.sendto(payload, (VM_IP, VM_PORT))
    sock.close()
    print(f"Sent priority={priority} freshness={freshness_ms}ms data={ackermann_bytes.hex()}")

# --- Test 1: single command, generous freshness ---
ackermann_1 = bytes([0x01] * 16)
send_command(ackermann_1, freshness_ms=2000, priority=5)
time.sleep(0.5)

# --- Test 2: two commands back to back, higher priority should win ---
ackermann_low  = bytes([0x02] * 16)
ackermann_high = bytes([0x03] * 16)
send_command(ackermann_low,  freshness_ms=2000, priority=3)
send_command(ackermann_high, freshness_ms=2000, priority=9)
time.sleep(0.5)

# --- Test 3: expired command (1ms freshness, sleep before it arrives) ---
ackermann_stale = bytes([0x04] * 16)
send_command(ackermann_stale, freshness_ms=1, priority=10)