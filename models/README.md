# Models

Trained model files for the perception nodes. They stay out of git: only this file is
tracked (see `.gitignore`).

| File | What it is | How to get it |
|---|---|---|
| `yolo11n.pt` | the stock YOLO11 nano model. It knows 80 everyday things, "stop sign" among them | `pixi run get-models` |
| `best.pt` | the team's own stop-sign model, once someone finds it (the 2024-25 code loaded it from `~/Yolo/Capstone/runs/detect/train7/weights/best.pt`) | ask the team |

One model, three formats. Make the other two from the `.pt` file:

| Format | Runs on | Make it with |
|---|---|---|
| `.pt` | anything, with PyTorch | the training |
| `.mlpackage` | Macs, with Core ML | `pixi run -e ml yolo export model=models/yolo11n.pt format=coreml` |
| `.engine` | the Orin, with TensorRT | `yolo export model=models/yolo11n.pt format=engine`, on the Orin itself |

The Ultralytics models and code are licensed AGPL-3.0.
