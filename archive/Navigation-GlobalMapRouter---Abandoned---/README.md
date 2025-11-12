# 🛰️ Global Map Router (ROS 2 Node)

`global_map_router` is a ROS 2 node that performs **global route planning** using the **Google Maps Directions API**.
It subscribes to a destination topic (`/target_address`), retrieves the current GPS position (from `.env`), and computes one or more route alternatives.
Each route’s polyline coordinates are decoded and printed to the console.

---

## 📁 Project Structure

```
global_map_router/
├── global_map_router/
│   ├── app/
│   ├── .env                👈 Environment configuration file
│   └── __init__.py
├── package.xml
├── setup.py
└── README.md
```

---

## ⚙️ Dependencies

Requires a working ROS 2 installation (Humble, Iron, or Jazzy).
Python dependencies (installed automatically during ROS build):

```
rclpy
std_msgs
requests
python-dotenv
colorlog
```

---

## 🔑 API Key Setup

Before running the node, you **must** edit `.env` file inside:

```
/global_map_router/global_map_router/.env
```

Example:

```bash
GOOGLE_MAP_API_KEY=AIzaSyD**************
CUR_POS_LAT_TEST=45.4231
CUR_POS_LON_TEST=-75.6831
```

| Variable                                | Description                                                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `GOOGLE_MAP_API_KEY`                    | Your valid Google Maps API key. Enable **Geocoding API** and **Directions API**, and ensure **Billing** is active. |
| `CUR_POS_LAT_TEST` / `CUR_POS_LON_TEST` | Default GPS location. Currently set to Carleton University (Ottawa).                                               |

---

## 🧭 Node Information

| Field                | Value                                                                                |
| -------------------- | ------------------------------------------------------------------------------------ |
| **Node name**        | `global_map_router`                                                                  |
| **Subscribed topic** | `/target_address`                                                                    |
| **Message type**     | `std_msgs/String`                                                                    |
| **Purpose**          | Receives destination text and computes a route plan using Google Maps Directions API |

---

## 🚀 Usage

### 1️⃣ Load ROS 2 environment

```bash
source /opt/ros/jazzy/setup.bash     # or humble/iron depending on your version
source ~/ros2_ws/install/setup.bash
```

### 2️⃣ Run the node

```bash
ros2 run global_map_router global_map_router
```

Expected output:

```
2025-11-12 10:10:18 [INFO] Starting Global Navigation Node
2025-11-12 10:10:18 [INFO] Waiting for /target_address...
```

### 3️⃣ Publish a destination

```bash
ros2 topic pub /target_address std_msgs/String "data: Ottawa Airport"
```

Example output:

```
2025-11-12 10:08:59 [INFO] Received destination: Ottawa Airport
2025-11-12 10:08:59 [INFO] Current GPS: lat=45.4231, lon=-75.6831
2025-11-12 10:08:59 [INFO] Destination: lat=45.3201686, lon=-75.66562239999999
2025-11-12 10:08:59 [INFO] Route 1 decoded (268 points)
2025-11-12 10:08:59 [INFO] Route 2 decoded (369 points)
2025-11-12 10:08:59 [INFO] Received 2 alternative routes
2025-11-12 10:08:59 [INFO] Route #1 - 268 points
2025-11-12 10:08:59 [INFO]    [1] lat=45.423300, lon=-75.682450
2025-11-12 10:08:59 [INFO]    [2] lat=45.423690, lon=-75.681520
2025-11-12 10:08:59 [INFO]    [3] lat=45.423450, lon=-75.681320
```

---

## 🗺️ Changing the Default Start Location

By default, the node starts at **Carleton University (Ottawa)**.
To use another origin, edit the `.env` file:

```
/global_map_router/global_map_router/.env
```

Example:

```bash
CUR_POS_LAT_TEST=43.65107
CUR_POS_LON_TEST=-79.347015
```

Then rebuild or restart the node.

---

## 🤩 Example Topic Tests

You can test other destinations:

```bash
ros2 topic pub /target_address std_msgs/String "data: Ottawa University"
ros2 topic pub /target_address std_msgs/String "data: Montreal Airport"
```

---

## ⚠️ Common Issues

| Error            | Cause                          | Fix                                                               |
| ---------------- | ------------------------------ | ----------------------------------------------------------------- |
| `REQUEST_DENIED` | Invalid or restricted API key  | Enable Geocoding/Directions APIs and Billing                      |
| `ZERO_RESULTS`   | Address unreachable or invalid | Try another location                                              |
| `NoneType` error | `.env` not loaded properly     | Make sure `.env` is inside `global_map_router/global_map_router/` |

---

## 🧠 Author

**Ruangfafa**
ROS 2 Global Map Router Node — Autonomous Route Planner powered by Google Maps API
