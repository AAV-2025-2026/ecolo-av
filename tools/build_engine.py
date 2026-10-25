#!/usr/bin/env python3
"""
Build the Orin's TensorRT model, models/rf-detr-nano.engine, on the Orin itself.

usage, on the Orin, with JetPack's python3 (not Pixi's):
    cd ~/aav && python3 tools/build_engine.py                       # RF-DETR Nano: the car's
    python3 tools/build_engine.py models/rf-detr-nano.onnx          # from an ONNX copied over
    python3 tools/build_engine.py models/yolo11n.pt                 # YOLO, through Ultralytics

A TensorRT engine runs only on the GPU and the TensorRT version that built it, so it
can't be made on a laptop and copied over. RF-DETR goes in two steps:
  1. .pth -> .onnx, with rfdetr's own export (tools/export_model.py). Any computer can do
     this step, with pip install onnx; ONNX files are portable.
  2. .onnx -> .engine, with TensorRT's own Python builder, in half precision (FP16), the
     usual choice on a Jetson. `trtexec --onnx=models/rf-detr-nano.onnx --fp16
     --saveEngine=models/rf-detr-nano.engine` does the same by hand.
Then it runs the engine once on the test stop sign, and prints the score and the time.

This needs, in JetPack's python3:
  - TensorRT's Python module: JetPack has it (python3-libnvinfer);
  - PyTorch and torchvision with CUDA: NVIDIA's builds for Jetson, not PyPI's;
  - for RF-DETR from a .pth: pip install rfdetr onnx (not rfdetr[tensorrt]: that brings
    PyPI's TensorRT, not JetPack's); for YOLO: pip install ultralytics onnx.
In a venv, make it with --system-site-packages, or it can't see TensorRT and PyTorch.
car.launch.py machine:=orin then loads models/rf-detr-nano.engine (orin.yaml says how).
Steps: docs/perception.md, "Models". Untested: it needs the Orin.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros' / 'perception' / 'aav_detector'))
sys.path.insert(0, str(ROOT / 'tools'))
TEST_PICTURE = ROOT / 'ros' / 'perception' / 'aav_detector' / 'test' / 'stop_sign.jpg'
# What each kind of model needs, and where each comes from.
TENSORRT = {
    'tensorrt': "TensorRT's Python module, from JetPack (sudo apt install python3-libnvinfer)",
    'torch': "PyTorch with CUDA: NVIDIA's build for Jetson (docs/perception.md)",
    'cv2': "OpenCV's Python module: JetPack's (sudo apt install python3-opencv)",
}
NEEDS = {
    '.pth': {**TENSORRT, 'rfdetr': 'pip install rfdetr', 'onnx': 'pip install onnx'},
    '.onnx': TENSORRT,
    '.pt': {**TENSORRT, 'ultralytics': 'pip install ultralytics', 'onnx': 'pip install onnx'},
}


def problems(kind):
    """List what stops this python3 building an engine from a `kind` model: nothing, ready."""
    found = []
    if (Path(sys.prefix) / 'conda-meta').is_dir():
        found.append(f'{sys.executable} is a Pixi or conda Python: run this with '
                     "JetPack's python3, outside Pixi")
    found += [f'no {module}: {how}' for module, how in NEEDS[kind].items()
              if importlib.util.find_spec(module) is None]
    return found


def onnx_to_engine(onnx, engine):
    """Build a TensorRT engine from an ONNX file, in FP16 where the GPU has it."""
    import tensorrt as trt
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    # TensorRT 10 always has explicit batch sizes; 8.x needs the flag.
    explicit = getattr(trt.NetworkDefinitionCreationFlag, 'EXPLICIT_BATCH', None)
    network = builder.create_network(0 if explicit is None else 1 << int(explicit))
    parser = trt.OnnxParser(network, logger)
    if not parser.parse(onnx.read_bytes()):
        errors = [str(parser.get_error(i)) for i in range(parser.num_errors)]
        sys.exit(f'{onnx}: TensorRT could not read it:\n  ' + '\n  '.join(errors))
    config = builder.create_builder_config()
    if builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
    else:
        print('This GPU has no fast FP16: the engine stays in full precision (FP32)')
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        sys.exit(f'{onnx}: TensorRT could not build an engine (its messages are above)')
    engine.write_bytes(bytes(serialized))
    return engine


def build_yolo(pt):
    """Build YOLO's engine with Ultralytics, at 640 px, as the detector runs."""
    # Ultralytics must never pip-install anything: say what's missing instead.
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    from ultralytics.utils import DEFAULT_CFG_DICT
    # FP16 is quantize=16 since Ultralytics 8.4, half=True before.
    fp16 = {'quantize': 16} if 'quantize' in DEFAULT_CFG_DICT else {'half': True}
    # simplify=False: TensorRT optimises the graph itself, and simplifying would also need
    # onnxslim and onnxruntime, which has no CUDA build for Jetson on PyPI.
    return Path(YOLO(str(pt)).export(format='engine', imgsz=640, device=0, simplify=False,
                                     **fp16))


def check(engine):
    """Run a new RF-DETR engine on the test stop sign: print the score and the time."""
    import cv2

    from aav_detector.detectors import load_detector
    model = load_detector('rfdetr', str(engine), root='/')
    picture = cv2.imread(str(TEST_PICTURE))
    boxes = model.detect(picture, 0.5)
    start = time.monotonic()
    for _ in range(20):
        model.detect(picture, 0.5)
    ms = (time.monotonic() - start) * 1000.0 / 20
    found = ', '.join(f'{b.label} {b.score:.2f}' for b in boxes) or 'nothing'
    print(f'The test stop sign: {found} (PyTorch on a Mac: stop sign 0.96); '
          f'{ms:.1f} ms a picture, its pre- and post-processing included')


def main():
    model = Path(sys.argv[1] if len(sys.argv) > 1 else 'models/rf-detr-nano.pth')
    model = model if model.is_absolute() else ROOT / model
    if model.suffix not in NEEDS:
        sys.exit(f'{model}: give a .pth or .onnx (RF-DETR), or a .pt (YOLO)')
    jetson = Path('/etc/nv_tegra_release')
    if jetson.exists():
        print(jetson.read_text().splitlines()[0])
    else:
        print("Not a Jetson: this engine will run only on this computer's own GPU.")
    found = problems(model.suffix)
    if found:
        sys.exit('Cannot build the engine with this python3:\n  - ' + '\n  - '.join(found))

    import tensorrt
    import torch
    print(f'TensorRT {tensorrt.__version__}, PyTorch {torch.__version__}, '
          f'CUDA {torch.version.cuda}')
    if not torch.cuda.is_available():
        sys.exit("PyTorch can't see the GPU: it needs NVIDIA's build for Jetson")
    if not model.exists() and model.name in ('rf-detr-nano.pth', 'yolo11n.pt'):
        subprocess.run([str(ROOT / 'tools' / 'get_models.sh')], check=True)
    if not model.exists():
        sys.exit(f'{model} is missing')

    start = time.monotonic()
    if model.suffix == '.pt':
        print(f'{build_yolo(model)}: built in {time.monotonic() - start:.0f} s')
        return
    onnx = model
    if model.suffix == '.pth':
        from export_model import export_rfdetr
        onnx = export_rfdetr(model, 'onnx', model.with_suffix('.onnx'))
        print(f'{onnx}: exported in {time.monotonic() - start:.0f} s')
    engine = onnx_to_engine(onnx, onnx.with_suffix('.engine'))
    print(f'{engine}: built in {time.monotonic() - start:.0f} s')
    check(engine)


if __name__ == '__main__':
    main()
