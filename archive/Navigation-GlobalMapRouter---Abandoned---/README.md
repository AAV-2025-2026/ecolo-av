# 🛰️ Global Map Router`[Abandoned 2025/11/19]`

## Why abandoned?
Since this repo was originally planned to use the **Google Direction API** for navigation planning, but it lacked essential road surface information required for autonomous driving, we later switched to using the UI group’s **OSRM** for local deployment and generation of the global route.

## Introduction
`global_map_router` is a ROS 2 node that performs **global route planning** using the **Google Maps Directions API**.
It subscribes to a destination topic (`/target_address`), retrieves the current GPS position from /current_coordinate topic, and computes one or more route alternatives.
Each route’s polyline coordinates are decoded and printed to the console. Routes are also published in JSON format to topic: /global_map_router

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
json
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
```

| Variable                                | Description                                                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `GOOGLE_MAP_API_KEY`                    | Your valid Google Maps API key. Enable **Geocoding API** and **Directions API**, and ensure **Billing** is active. |

---

## 🧭 Node Information

| Field                | Value                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------- |
| **Node name**        | `global_map_router`                                                                           |
| **Subscribed topics**| `/target_address` (destination text), `/current_coordinate` (live GPS)                        |
| **Published topic**  | `/global_map_router` (JSON route output)                                                      |
| **Message type**     | `std_msgs/String`                                                                             |
| **Purpose**          | Computes one or more global navigation routes using Google Maps Directions API               |

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
ros2 topic pub /current_coordinate std_msgs/String "data: 45.4231,-75.6831"
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

### 📦 Route Output Format (JSON)

Each computed route is published as:

```json
{
  "routes": [
    {
      "route_index": 0,
      "points": [
        {"lat": 45.4233, "lon": -75.68245},
        ...
      ],
      "source": "GoogleDirections"
    }
  ]
}
```
---
## 🧠 Author

**Ruangfafa**
ROS 2 Global Map Router Node — Autonomous Route Planner powered by Google Maps API
