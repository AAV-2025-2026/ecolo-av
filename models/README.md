# Models

Trained model files for the perception nodes. They stay out of git: only this file is
tracked (see `.gitignore`).

| File | What it is | How to get it |
|---|---|---|
| `rf-detr-nano.pth` | the stock RF-DETR Nano model (Roboflow, Apache-2.0): the detector's default since 20 Oct (`detector:=rfdetr`). It knows the same 80 everyday things | `pixi run get-models` (366 MB) |
| `yolo11n.pt` | the stock YOLO11 nano model (`detector:=yolo`). It knows 80 everyday things, "stop sign" among them | `pixi run get-models` |
| `best.pt` | the 2024-25 team's own stop-sign model: its trained weights, one label (`Stop_Sign`). Training saves two files, `best.pt` (the round that scored best) and `last.pt`. Their code loaded it from `~/Yolo/Capstone/runs/detect/train7/weights/best.pt`, on one student's computer | ask the team. Then `pixi run detect model:=models/best.pt labels:="stop sign"` |

One YOLO model, three formats. Make the other two from the `.pt` file:

| Format | Runs on | Make it with |
|---|---|---|
| `.pt` | anything, with PyTorch | the training |
| `.mlpackage` | Macs, with Core ML | `pixi run -e ml export-coreml [models/<name>.pt]`, on a Mac |
| `.engine` | the Orin, with TensorRT | `python3 tools/build_engine.py [models/<name>.pt]`, on the Orin itself, with JetPack's Python |

The Ultralytics models and code are licensed AGPL-3.0; RF-DETR's Nano to Large, Apache-2.0.
