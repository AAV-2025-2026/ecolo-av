# Command Processor

Part of the AAV Real-Time OS stack. Sits between the navigation team's path planner and the motor control team, receiving Ackermann commands over UDP, managing them in a priority pool, and forwarding the highest-priority command to the motor control unit.

---

## Architecture

The command processor is made up of three components:

**Command Interface** (`src/command_interface.c`)
Owns a UDP socket that listens for inbound packets from the navigation team. For each packet it records the receive timestamp, parses the priority metadata, and pushes a `PoolEntry` into the shared command pool. Each received command is also logged to the RTOS database via the `/db_queue` POSIX message queue.

**Command Pool** (`src/command_pool.c`)
A thread-safe, priority-ordered pool shared between the interface and MCU logic. Entries are kept sorted by priority (descending). The pool blocks the MCU thread on a condition variable when empty.

**MCU Logic** (`src/mcu_logic.c`)
Pops the highest-priority command from the pool and forwards the raw Ackermann bytes to the motor control team over UDP. Each forwarded command is logged to the RTOS database. Runs at a higher real-time priority (SCHED_FIFO) than the interface thread so scheduling decisions are never delayed by incoming packet processing.
```
Navigation Team                Command Processor                 Motor Control Team
(external, non-RTOS)                                             (external)

                   UDP :5000       ┌─────────────────┐
  [Ackermann pkt] ──────────────► │ CommandInterface │
  [priority     ]                 │                  │
                                  │   CommandPool    │
                                  │                  │
                                  │    MCULogic      │ ──────────────► [Ackermann bytes]
                                  └─────────────────┘      UDP :5001
                                          │
                                    /db_queue (POSIX mq)
                                          │
                                   Database component
```

---

## Wire Format

Inbound UDP packets must follow this layout:

| Offset | Size | Field             | Description                           |
|--------|------|-------------------|---------------------------------------|
| 0      | 16   | ackermann_payload | Opaque blob, forwarded as-is to MCU   |
| 16     | 1    | priority          | uint8, higher value = higher priority |

Total packet size: **17 bytes**. The Ackermann payload is never deserialised — it is forwarded raw to the motor control team. Command validation is the responsibility of the sending subsystem.

---

## Configuration

All deployment-specific values are defined as `#define` constants. These are the first things to check if something isn't working.

### `src/main.c`

| Constant               | Default         | Description                                      |
|------------------------|-----------------|--------------------------------------------------|
| `INTERFACE_LISTEN_PORT`| `5000`          | UDP port to listen on for inbound commands       |
| `MCU_TARGET_HOST`      | `"192.168.56.1"`| IP address of the motor control team's listener  |
| `MCU_TARGET_PORT`      | `5001`          | UDP port the motor control team listens on       |

### `include/command_pool.h`

| Constant               | Default | Description                                                        |
|------------------------|---------|--------------------------------------------------------------------|
| `ACKERMANN_PAYLOAD_SIZE`| `16`   | Payload size in bytes — must match the navigation team's struct    |
| `POOL_CAPACITY`        | `64`    | Max commands in the pool; incoming commands are dropped if full    |

### Thread priorities (QNX only)

Set inside `mcu_start()` and `interface_start()` under `#ifdef __QNXNTO__`:

| Thread            | Priority | Notes                                                        |
|-------------------|----------|--------------------------------------------------------------|
| Interface thread  | 20       | Receive and pool insertion                                   |
| MCU logic thread  | 30       | Higher than interface — forwarding is never delayed by recv  |

To adjust, change `sp.sched_priority` in the respective `_start()` functions.

---

## Building

Requires the QNX Software Development Platform (SDP) installed on Windows, which provides `qcc` and `make`. Build via the QNX Toolkit in VS Code or from the `qnx-terminal`:
```sh
make BUILD_PROFILE=debug PLATFORM=x86_64 all       # debug, x86_64 VM target
make BUILD_PROFILE=release PLATFORM=x86_64 all     # release, x86_64 VM target
make BUILD_PROFILE=release PLATFORM=aarch64le all  # release, ARM (real hardware)
make clean
```

Output: `build/<PLATFORM>-<BUILD_PROFILE>/command_processor`

> **Note:** If the build fails with undefined references to `recv`, `socket`, `bind`, etc., ensure `-lsocket` is present in the `LIBS` line of the Makefile. On QNX, socket functions are not in libc.

---

## Deploying to the QNX VM

### Prerequisites
- QNX SDP installed (provides `qcc`, `make`, and `scp` via `qnx-terminal`)
- QNX VM running in VirtualBox (default IP: `192.168.56.104`)
- SSH access to the VM (`root`, password as configured)

### Steps

**1. Build the Database app and Command Processor** (see [Building](#building) above)

**2. Transfer binaries to the VM** — run from `qnx-terminal`:
```sh
scp -o MACs=hmac-sha2-256 <path>\Database\DBapp root@192.168.56.104:
scp -o MACs=hmac-sha2-256 <path>\CommandProcessor\build\x86_64-debug\command_processor root@192.168.56.104:
```

**3. Run on the VM** — from the SSH terminal (`qnx-ssh-vbox-qnx800-x86_64`):
```sh
chmod +x DBapp command_processor
./DBapp &
./command_processor
```

Both processes run indefinitely. The Database app listens on `/db_queue` and persists all log entries written by the command processor.

---

## Testing

Requires Python 3 on the test machine, with the command processor running on the target and the test machine able to reach the target's IP on the listen port.

**Start the listener** (simulates the motor control team):
```sh
python listen.py
```

**Send test commands** (simulates the navigation team):
```sh
python send_cmd.py
```

`send_cmd.py` sends three test cases: a single command, two back-to-back commands with different priorities to verify pool ordering, and a high-priority command. Check the SSH terminal to confirm the Database app is receiving and inserting log entries from the command processor.

---

## Troubleshooting

**Nothing arrives at the listener:**
1. Confirm `MCU_TARGET_HOST` is set to the listener machine's IP — not the target's own IP or `127.0.0.1`
2. On Windows, confirm the firewall rule for `MCU_TARGET_PORT` uses `-Profile Any` — VirtualBox host-only adapters are classified as Public, so Domain/Private rules do not apply
3. SSH into the target and run `netstat -an` to confirm the process is bound on the listen port

**Packets received but forwarded to wrong destination:**
Check `MCU_TARGET_HOST`. A common mistake is setting this to the VM's own IP (`192.168.56.104`) instead of the Windows host IP (`192.168.56.1`).

**No log entries appearing in the Database app:**
Confirm `DBapp` is running before `command_processor` is started — the `/db_queue` message queue must exist before the command processor attempts to open it.

**Debug logging:**
Temporary log-to-file instrumentation can be added to `interface_thread()` and `mcu_thread()` writing to `/tmp/iface_debug.log` and `/tmp/mcu_debug.log` respectively. This is the most reliable way to see output from processes launched by the QNX Toolkit.

---

## Not Yet Implemented

- Watchdog heartbeat pulses from the interface and MCU logic threads
- Emergency stop blocking mechanism
- Transport layer replacement (UDP → CAN bus or Automotive Ethernet)
