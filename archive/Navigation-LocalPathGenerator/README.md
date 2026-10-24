# 🚗 Local Path Generator (ROS2)

A lightweight local path generation utility for autonomous driving based on **OSRM route data**.  
It parses OSRM responses, converts coordinates into local XY, and efficiently determines the current step along the route using GPS.

---

## 📌 Features

- Parse OSRM global route, legs, and steps from JSON
- Cache geometry and coordinate transforms
- Efficiently detect current step based on GPS position
- Return closest segment & point on the step
- Provide maneuver metadata (turn type, modifier, etc.)

---

## 📎 Key Modules

| File | Description |
|------|-------------|
| `osrm_reader_service.py` | Parse OSRM response JSON into Python model objects |
| `osrm_step_model.py` | OSRM step model + indexed metadata (`step_index`, `maneuver info`) |
| `path_service.py` | Compute XY, search range, and nearest step using GPS |

---
## 🧠 Optimization Highlights
### 🔧 Step Determination Speed-up

- Limit step-search to current −3 to current +6

- Reduce unnecessary scanning of all steps

- Maintain cache of XY conversions keyed by GPS origin



### 📍 More Info Returned

- Exact segment within the step

- Closest projected point (local XY)

- Turn maneuver type + modifier added to each step