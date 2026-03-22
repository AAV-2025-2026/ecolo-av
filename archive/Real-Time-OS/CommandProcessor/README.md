# Command Processor — Iteration 2

Part of the AAV Real-Time OS stack. Sits between the navigation team's path planner and the motor control team, receiving Ackermann commands over UDP, managing them in a priority pool, and forwarding the highest-priority valid command to the motor control unit.

---

## Architecture

The command processor is made up of three components:

**Command Interface** (`src/command_interface.c`)
Owns a UDP socket that listens for inbound packets from the navigation team. For each packet it records the receive timestamp, parses the freshness and priority metadata, computes `valid_until = recv_time + freshness_ms`, and pushes a `PoolEntry` into the shared command pool.

**Command Pool** (`src/command_pool.c`)
A thread-safe, priority-ordered pool shared between the interface and MCU logic. Entries are kept sorted by priority (descending). Expired entries are discarded automatically when the MCU thread pops from the pool. The pool blocks the MCU thread on a condition variable when empty.

**MCU Logic** (`src/mcu_logic.c`)
Runs a scheduling loop: pop the highest-priority valid command from the pool, verify it hasn't expired in the gap since it was popped, then forward the raw Ackermann bytes to the motor control team over UDP. Runs at a higher real-time priority (SCHED_FIFO) than the interface thread on QNX so scheduling decisions are never delayed by incoming packet processing.

```
Navigation Team                Command Processor                 Motor Control Team
(external, non-RTOS)                                             (external)

                   UDP :5000       ┌─────────────────┐
  [Ackermann pkt] ──────────────► │ CommandInterface │
  [freshness_ms ]                 │                  │
  [priority     ]                 │   CommandPool    │
                                  │                  │
                                  │    MCULogic      │ ──────────────► [Ackermann bytes]
                                  └─────────────────┘      UDP :5001
```

---

## Wire Format

Inbound UDP packets from the navigation team must follow this layout (big-endian):

| Offset | Size | Field            | Description                              |
|--------|------|------------------|------------------------------------------|
| 0      | 16   | ackermann_payload | Opaque blob, forwarded as-is            |
| 16     | 4    | freshness_ms      | uint32, how long the command is valid for (milliseconds) |
| 20     | 1    | priority          | uint8, higher value = higher priority    |

Total packet size: **21 bytes**. The Ackermann payload is never deserialised — it is forwarded raw to the motor control team.

---

## Configuration

All values that need to change between deployments are defined as `#define` constants at the top of `src/main.c` and `include/command_pool.h`. **These are the first things to check if something isn't working.**

### `src/main.c`

```c
#define INTERFACE_LISTEN_PORT   5000u
```
UDP port the command processor binds to and listens on for inbound Ackermann packets from the navigation team. Must match the port the navigation team is sending to.

```c
#define MCU_TARGET_HOST         "192.168.56.1"
```
IP address of the motor control team's UDP listener. When testing locally with a listener on a Windows host connected via VirtualBox host-only networking, this is typically `192.168.56.1`. On the real vehicle this will be the motor control unit's network address.

```c
#define MCU_TARGET_PORT         5001u
```
UDP port the motor control team is listening on for forwarded Ackermann commands.

### `include/command_pool.h`

```c
#define ACKERMANN_PAYLOAD_SIZE  16u
```
Size in bytes of the opaque Ackermann payload. Must match the exact byte size of the struct the navigation team is sending. If the navigation team changes their Ackermann struct, update this value — it affects both the inbound packet size check and the number of bytes forwarded to motor control.

```c
#define POOL_CAPACITY           64u
```
Maximum number of commands that can sit in the pool simultaneously. If the pool fills up, incoming commands are dropped with a warning. Increase if high-frequency command bursts are expected.

### `src/mcu_logic.c` and `src/command_interface.c` — Thread Priorities (QNX only)

Inside `mcu_start()` and `interface_start()`, the SCHED_FIFO real-time priorities are set under `#ifdef __QNXNTO__`:

- Interface thread: priority **20**
- MCU logic thread: priority **30**

The MCU thread is intentionally higher than the interface thread so scheduling decisions are never delayed by packet processing. If these need to be adjusted to fit within the broader RTOS priority scheme, change the `sp.sched_priority` values in the respective `_start()` functions.

---

## Building

The project uses the QNX-generated Makefile. Build through the QNX Toolkit in VS Code, or from the command line:

```sh
make BUILD_PROFILE=debug PLATFORM=x86_64 all       # debug build, x86_64 VM target
make BUILD_PROFILE=release PLATFORM=x86_64 all     # release build, x86_64 VM target
make BUILD_PROFILE=release PLATFORM=aarch64le all  # release build, ARM target (real hardware)
```

Clean:
```sh
make clean
```

The binary is output to `build/<PLATFORM>-<BUILD_PROFILE>/command_processor`.

---

## Testing

### Requirements
- Python 3 on the test machine
- The command processor running on the target (VM or hardware)
- The test machine able to reach the target's IP on the listen port

### Running the tests

Start the listener first (simulates the motor control team):
```sh
python listen.py
```

Then send test commands (simulates the navigation team):
```sh
python send_cmd.py
```

`send_cmd.py` sends four packets: a single normal command, two back-to-back commands with different priorities to verify ordering, and one command with a 1ms freshness to verify expiry handling.

### Troubleshooting

**Nothing arrives at the listener:**
1. Confirm `MCU_TARGET_HOST` in `main.c` is set to the listener machine's IP — not the target's own IP, and not `127.0.0.1`
2. Confirm the listener machine's firewall allows inbound UDP on `MCU_TARGET_PORT`. On Windows, the rule must use `-Profile Any` — rules scoped to Domain or Private will not apply to VirtualBox host-only adapters which Windows classifies as Public
3. SSH into the target and check `netstat -an` to confirm the process is bound on the listen port
4. If debug logging is needed, temporary log-to-file instrumentation can be added to `interface_thread()` and `mcu_thread()` writing to `/tmp/iface_debug.log` and `/tmp/mcu_debug.log` respectively — this is the only reliable way to see output from processes launched by the QNX Toolkit

**Packets received but forwarded to wrong destination:**
Check `MCU_TARGET_HOST`. A common mistake when testing with a VirtualBox VM is setting this to the VM's own IP (`192.168.56.104`) instead of the Windows host IP (`192.168.56.1`).

**Build fails with undefined reference to `recv`, `socket`, `bind`, etc.:**
Add `-lsocket` to the `LIBS` line in the Makefile. On QNX, socket functions are not in libc.

## Not Yet Implemented

- Watchdog pulse for the interface, pool, and mcu logic thread

## Command Processor and Database Communication (VM)

### Prerequisites
- **QNX Software Development Platform (SDP)** installed on Windows (provides `qcc` compiler and `make`).
- **QNX VM** running (e.g., Oracle VirtualBox with QNX Neutrino, IP: 192.168.56.104).
- **SSH access** to the VM (username: `root`, password as configured).
- **Python** on Windows for testing (send_cmd.py).

### Step-by-Step Setup and Run Guide

#### 1. Build the Database App (DBapp)
- Open the `qnx-terminal` in VS Code (this provides the QNX build environment).
- Navigate to the Database folder (Example path, replace with real path):
  ```
  cd 'C:\Users\randr\Real-Time-OS\Database'
  ```
- Compile DBapp:
  ```
  qcc sqlite3.c database.c -o DBapp
  ```
- Verify: Check for `DBapp` in the current directory (no errors in output).

#### 2. Build the Command Processor (command_processor)
- In the same `qnx-terminal`:
- Navigate to the CommandProcessor folder:
  ```
  cd 'C:\Users\randr\Real-Time-OS\CommandProcessor'
  ```
- Build using the Makefile:
  ```
  make
  ```
- Verify: Check for `build/x86_64-debug/command_processor` (no errors in output).

#### 3. Transfer Executables to QNX VM
- In the `qnx-terminal`:
- Transfer DBapp: (Your VM IP may be different)
  ```
  scp -o MACs=hmac-sha2-256 C:\Users\randr\Real-Time-OS\Database\DBapp root@192.168.56.104:
  ```
- Transfer command_processor:
  ```
  scp -o MACs=hmac-sha2-256 C:\Users\randr\Real-Time-OS\CommandProcessor\build\x86_64-debug\command_processor root@192.168.56.104:
  ```
- Enter the VM's root password when prompted. Files will be in `/root/` on the VM.

#### 4. Run on QNX VM
- Open the SSH terminal in VS Code (`qnx-ssh-vbox-qnx800-x86_64`).
- Make executables runnable:
  ```
  chmod +x DBapp
  chmod +x command_processor
  ```
- Start DBapp in the background:
  ```
  ./DBapp &
  ```
- Start command_processor:
  ```
  ./command_processor
  ```
- Both should run indefinitely, listening for messages.

#### 5. Test the Integration
- On Windows, in a PowerShell terminal:
- Navigate to the test folder:
  ```
  cd 'C:\Users\randr\Real-Time-OS\CommandProcessor\command_processor_test'
  ```
- Run the test script:
  ```
  python send_cmd.py
  ```
- Check the SSH terminal: You should see DBapp receiving and inserting messages (e.g., "Received from queue: ..." and "Inserted log: ...").

#### Troubleshooting
- If builds fail, ensure QNX SDP is properly installed and `qnx-terminal` is used.
- If SCP fails, verify VM IP and SSH access.
- If no messages in DBapp, check for errors in the SSH terminal (e.g., queue issues).

