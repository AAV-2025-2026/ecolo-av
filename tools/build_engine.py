#!/usr/bin/env python3
"""
Build the Orin's TensorRT model, models/yolo11n.engine, on the Orin itself.

usage, on the Orin, with JetPack's python3 (not Pixi's):
    cd ~/aav && python3 tools/build_engine.py [models/yolo11n.pt]

A TensorRT engine runs only on the GPU and the TensorRT version that built it, so it
can't be made on a laptop and copied over. This needs, in JetPack's python3:
  - TensorRT's Python module: JetPack has it (python3-libnvinfer);
  - PyTorch with CUDA: NVIDIA's build for Jetson, not PyPI's;
  - Ultralytics and ONNX: pip install ultralytics onnx. In a venv, make it with
    --system-site-packages, or it can't see TensorRT and PyTorch.
It exports at 640 px, as the detector runs, in half precision (FP16), the usual choice on
a Jetson. car.launch.py machine:=orin then loads models/yolo11n.engine. Steps:
docs/perception.md, "Models". Untested: it needs the Orin.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
# What the export needs, and where each comes from.
NEEDS = {
    'tensorrt': "TensorRT's Python module, from JetPack (sudo apt install python3-libnvinfer)",
    'torch': "PyTorch with CUDA: NVIDIA's build for Jetson (docs/perception.md)",
    'ultralytics': 'pip install ultralytics',
    'onnx': 'pip install onnx',
}


def problems():
    """List what stops this python3 building an engine: nothing, on a ready Orin."""
    found = []
    if (Path(sys.prefix) / 'conda-meta').is_dir():
        found.append(f'{sys.executable} is a Pixi or conda Python: run this with '
                     "JetPack's python3, outside Pixi")
    found += [f'no {module}: {how}' for module, how in NEEDS.items()
              if importlib.util.find_spec(module) is None]
    return found


def main():
    pt = Path(sys.argv[1] if len(sys.argv) > 1 else 'models/yolo11n.pt')
    pt = pt if pt.is_absolute() else ROOT / pt
    jetson = Path('/etc/nv_tegra_release')
    if jetson.exists():
        print(jetson.read_text().splitlines()[0])
    else:
        print("Not a Jetson: this engine will run only on this computer's own GPU.")
    found = problems()
    if found:
        sys.exit('Cannot build the engine with this python3:\n  - ' + '\n  - '.join(found))

    import tensorrt
    import torch
    print(f'TensorRT {tensorrt.__version__}, PyTorch {torch.__version__}, '
          f'CUDA {torch.version.cuda}')
    if not torch.cuda.is_available():
        sys.exit("PyTorch can't see the GPU: it needs NVIDIA's build for Jetson")
    if not pt.exists() and pt.name == 'yolo11n.pt':
        subprocess.run([str(ROOT / 'tools' / 'get_models.sh')], check=True)
    if not pt.exists():
        sys.exit(f'{pt} is missing')

    # Ultralytics must never pip-install anything: say what's missing instead.
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    from ultralytics.utils import DEFAULT_CFG_DICT
    # FP16 is quantize=16 since Ultralytics 8.4, half=True before.
    fp16 = {'quantize': 16} if 'quantize' in DEFAULT_CFG_DICT else {'half': True}
    start = time.monotonic()
    # simplify=False: TensorRT optimises the graph itself, and simplifying would also need
    # onnxslim and onnxruntime, which has no CUDA build for Jetson on PyPI.
    engine = YOLO(str(pt)).export(format='engine', imgsz=640, device=0, simplify=False, **fp16)
    print(f'{engine}: built in {time.monotonic() - start:.0f} s')


if __name__ == '__main__':
    main()
