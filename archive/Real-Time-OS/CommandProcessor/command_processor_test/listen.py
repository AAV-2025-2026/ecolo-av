# listen.py
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5001))
print("Listening for forwarded Ackermann packets on :5001...")

while True:
    data, addr = sock.recvfrom(1024)
    print(f"Received {len(data)} bytes from {addr}: {data.hex()}")