#!/usr/bin/env python3
"""
Compare object detectors on the same pictures: YOLO11 (ours today), YOLO26 and RF-DETR.

    python3 tools/compare_detectors.py --fetch            download the photos (once)
    python3 tools/compare_detectors.py                    every model, every device
    python3 tools/compare_detectors.py --models yolo11n rfdetr-nano --devices cpu

Only two classes matter to the car: person and stop sign (COCO 0 and 11 in Ultralytics'
numbering, 1 and 13 in RF-DETR's). Prints two markdown tables: per model and device, how
many pictures each class was found in (at the detector node's confidence, 0.5), the mean
best confidence, false finds, and ms per picture; then per picture, each model's best score.

Downloads go to --store (default ~/aav-models), never into the repo:
  weights/   the models (fetched by hand or by each library; see MODELS for where from)
  images/    Wikimedia Commons photos, 640 px wide (--fetch; licences in PHOTOS)
  frames/    Gazebo's road world, from tools/sim_frames.py

The runners need ultralytics (YOLO) and rfdetr (RF-DETR): `pixi run -e ml python3
tools/compare_detectors.py`. docs/model-comparison.md has the results.
Everything above the runners is plain Python, tested in tools/tests/test_compare_detectors.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Dict, Iterable, List, Optional, Sequence
import urllib.parse
import urllib.request

# As the ml environment sets: torchvision has no Metal NMS, so YOLO's runs on the CPU.
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
os.environ.setdefault('YOLO_AUTOINSTALL', 'false')   # Ultralytics must never pip-install

CLASSES = ('person', 'stop sign')
CONFIDENCE = 0.5            # the detector node's (aav_yolo detector.py)
LOW = 0.1                   # what the models are asked for: best scores below 0.5 still show
USER_AGENT = 'aav-capstone-model-comparison/0.1 (Carleton University school project)'

# Each model: its library, its file in weights/, where that came from, its checksum and
# licence. The weights are never committed.
MODELS: Dict[str, Dict] = {
    'yolo11n': {'family': 'ultralytics', 'file': 'yolo11n.pt',
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt',
                'sha256': '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1',
                'licence': 'AGPL-3.0 (Ultralytics)'},
    'yolo11s': {'family': 'ultralytics', 'file': 'yolo11s.pt',
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt',
                'sha256': '85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5',
                'licence': 'AGPL-3.0 (Ultralytics)'},
    'yolo26n': {'family': 'ultralytics', 'file': 'yolo26n.pt',
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt',
                'sha256': '9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef',
                'licence': 'AGPL-3.0 (Ultralytics)'},
    'yolo26s': {'family': 'ultralytics', 'file': 'yolo26s.pt',
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt',
                'sha256': '646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b',
                'licence': 'AGPL-3.0 (Ultralytics)'},
    # rfdetr's own table (rfdetr/assets/model_weights.py) pins these by MD5.
    'rfdetr-nano': {'family': 'rfdetr', 'file': 'rfdetr/rf-detr-nano.pth', 'variant': 'RFDETRNano',
                    'url': 'https://storage.googleapis.com/rfdetr/nano_coco/'
                           'checkpoint_best_regular.pth',
                    'md5': 'fb6504cce7fbdc783f7a46991f07639f',
                    'licence': 'Apache-2.0 (Roboflow)'},
    'rfdetr-small': {'family': 'rfdetr', 'file': 'rfdetr/rf-detr-small.pth',
                     'variant': 'RFDETRSmall',
                     'url': 'https://storage.googleapis.com/rfdetr/small_coco/'
                            'checkpoint_best_regular.pth',
                     'md5': 'fb37061c1af7bace359c91b723a8d5c1',
                     'licence': 'Apache-2.0 (Roboflow)'},
}

# Freely licensed photos from Wikimedia Commons: what's in each (checked by eye), and
# credit as each licence asks. --fetch downloads a 640 px copy of each into images/.
PHOTOS: List[Dict] = [
    {'name': 'dashcam-stop', 'expect': ['stop sign'],
     'title': 'File:Jackson Rd wb Wallace Rd intersection solar stop sign dashcam.jpg',
     'author': 'Michael Rivera (Mjrmtg)', 'licence': 'CC0'},
    {'name': 'gatineau-arret', 'expect': ['stop sign'],      # French: ARRÊT, not STOP
     'title': 'File:Tiled intersection with stop sign in Gatineau.jpg',
     'author': '137a', 'licence': 'CC BY 4.0'},
    {'name': 'sf-all-way-stop', 'expect': ['stop sign', 'person'],   # people, small, right
     'title': 'File:All-way stop intersection in San Francisco.jpg',
     'author': 'Hiya111', 'licence': 'CC BY-SA 4.0'},
    {'name': 'sf-market-from-above', 'expect': ['person'],  # tiny, from a roof: a hard one
     'title': 'File:Crosswalk of Market at Third, San Francisco.jpg',
     'author': 'Dllu', 'licence': 'CC BY-SA 4.0'},
    {'name': 'petersfield-walkers', 'expect': ['person'],
     'title': 'File:Pedestrians and a cyclist in the Petersfield Road - geograph.org.uk'
              ' - 3005700.jpg',
     'author': 'Basher Eyre (geograph.org.uk)', 'licence': 'CC BY-SA 2.0'},
    {'name': 'barcelona-crossing', 'expect': ['person'],
     'title': 'File:Pedestrians crossing the street in Barcelona DSF0993.jpg',
     'author': 'Levi Meir Clancy', 'licence': 'CC0'},
    {'name': 'dyott-street-crossing', 'expect': ['person'],
     'title': 'File:Pedestrians crossing in Dyott Street - geograph.org.uk - 1105273.jpg',
     'author': 'Basher Eyre (geograph.org.uk)', 'licence': 'CC BY-SA 2.0'},
    {'name': 'mississauga-empty', 'expect': [],             # nobody, no sign: false finds
     'title': 'File:Crosswalk (6984572731).jpg',
     'author': '^ Missi ^ (Flickr)', 'licence': 'CC BY 2.0'},
]


# --- The plain parts: no models, no network -------------------------------------------

def canonical(label) -> Optional[str]:
    """Return 'person' or 'stop sign' for a class name from any of the models, else None."""
    text = str(label).strip().lower().replace('_', ' ').replace('-', ' ')
    text = ' '.join(text.split())
    return text if text in CLASSES else None


def best_scores(detections: Iterable[Sequence], floor: float = 0.0) -> Dict[str, float]:
    """From (label, score) pairs, the best score of each class we care about (0 if none)."""
    best = dict.fromkeys(CLASSES, 0.0)
    for label, score in detections:
        name = canonical(label)
        if name and score >= floor and score > best[name]:
            best[name] = float(score)
    return best


def counts(detections: Iterable[Sequence], threshold: float = CONFIDENCE) -> Dict[str, int]:
    """How many boxes of each class we care about scored the threshold or more."""
    n = dict.fromkeys(CLASSES, 0)
    for label, score in detections:
        name = canonical(label)
        if name and score >= threshold:
            n[name] += 1
    return n


def detr_detections(logits, labels: Dict[int, str], threshold: float = LOW) -> List[tuple]:
    """
    (label, score) pairs from a DETR's raw class logits (queries x classes), as RF-DETR does.

    RF-DETR scores each query and class with a sigmoid and needs no NMS; this keeps every
    query-class pair at the threshold or more whose class index is in labels.
    """
    found = []
    for row in logits:
        for index, logit in enumerate(row):
            if index not in labels:
                continue
            score = 1.0 / (1.0 + math.exp(-float(logit)))
            if score >= threshold:
                found.append((labels[index], score))
    return found


def summarise(model: str, device: str, per_image: List[Dict], expect: Dict[str, List[str]],
              threshold: float = CONFIDENCE) -> Dict:
    """
    One model on one device, over every picture: its row of the main table.

    per_image: {'image', 'best': {class: score}, 'n': {class: count}, 'ms': [times]}.
    expect: each picture's classes (pictures not in it are left out of hits and misses).
    """
    row = {'model': model, 'device': device}
    for c in CLASSES:
        with_c = [p for p in per_image if c in expect.get(p['image'], [])]
        without = [p for p in per_image if p['image'] in expect and c not in expect[p['image']]]
        hits = [p for p in with_c if p['best'][c] >= threshold]
        row[c] = {'found': len(hits), 'of': len(with_c),
                  'mean_best': (round(statistics.mean(p['best'][c] for p in with_c), 2)
                                if with_c else None),
                  'false': sum(1 for p in without if p['best'][c] >= threshold)}
    times = [statistics.median(p['ms']) for p in per_image if p['ms']]
    row['ms'] = round(statistics.mean(times), 1) if times else None
    return row


def frames_reach(per_image: List[Dict], distances: Dict[str, float],
                 threshold: float = CONFIDENCE) -> Optional[float]:
    """Return the farthest Gazebo frame (m to the sign) where the stop sign scored enough."""
    seen = [distances[p['image']] for p in per_image
            if p['image'] in distances and p['best']['stop sign'] >= threshold]
    return max(seen) if seen else None


def frame_distance(name: str) -> Optional[float]:
    """road_sign_15.0m.png -> 15.0: metres from the camera to the sign (sim_frames.py)."""
    stem = Path(name).name
    for ext in ('.png', '.jpg'):
        stem = stem[:-len(ext)] if stem.endswith(ext) else stem
    if not (stem.startswith('road_sign_') and stem.endswith('m')):
        return None
    try:
        return float(stem[len('road_sign_'):-1])
    except ValueError:
        return None


def cell(found: Dict) -> str:
    """'3/3 (0.91)': pictures found in, of those with one, and the mean best score."""
    if not found['of']:
        return '-'
    text = f'{found["found"]}/{found["of"]}'
    if found['mean_best'] is not None:
        text += f' ({found["mean_best"]:.2f})'
    return text


def main_table(rows: List[Dict], sizes: Dict[str, str], licences: Dict[str, str],
               reach: Dict[str, Optional[float]]) -> str:
    """Return the markdown table: one row per model and device."""
    lines = ['| Model | Device | Person | Stop sign | False finds | Gazebo sign from '
             '| ms / picture | Size | Licence |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        false = sum(r[c]['false'] for c in CLASSES)
        far = reach.get((r['model'], r['device']))
        lines.append(f'| {r["model"]} | {r["device"]} | {cell(r["person"])} | '
                     f'{cell(r["stop sign"])} | {false} | '
                     f'{"-" if far is None else f"{far:g} m"} | '
                     f'{"-" if r["ms"] is None else r["ms"]} | {sizes.get(r["model"], "?")} | '
                     f'{licences.get(r["model"], "?")} |')
    return '\n'.join(lines)


def image_table(results: Dict[tuple, List[Dict]], expect: Dict[str, List[str]]) -> str:
    """Per picture: each model's best person and stop-sign score (its first device)."""
    models, seen = [], set()
    for model, _ in results:
        if model not in seen:
            seen.add(model)
            models.append(model)
    first = {m: next(v for (mm, _), v in results.items() if mm == m) for m in models}
    images = [p['image'] for p in first[models[0]]] if models else []
    lines = ['| Picture | Has | ' + ' | '.join(models) + ' |',
             '|---|---|' + '---|' * len(models)]
    for name in images:
        cells = []
        for m in models:
            p = next(p for p in first[m] if p['image'] == name)
            cells.append(f'{p["best"]["person"]:.2f} / {p["best"]["stop sign"]:.2f}')
        has = ', '.join(expect.get(name, [])) or 'nothing'
        lines.append(f'| {name} | {has} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def commons_query_url(titles: Sequence[str], width: int = 640) -> str:
    """Return the Commons API call for each file's thumbnail URL and licence."""
    query = {'action': 'query', 'titles': '|'.join(titles), 'prop': 'imageinfo',
             'iiprop': 'url|extmetadata', 'iiurlwidth': str(width), 'format': 'json'}
    return 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(query)


def looks_like_jpeg(data: bytes) -> bool:
    """Check the bytes look like a JPEG: FF D8 FF at the start, FF D9 at the end."""
    return data[:3] == b'\xff\xd8\xff' and data.rstrip(b'\x00')[-2:] == b'\xff\xd9'


def file_hash(path: Path, kind: str = 'sha256') -> str:
    h = hashlib.new(kind)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def checked_weights(store: Path, name: str) -> Path:
    """Return the model's file once its checksum matches: never load an unexpected file."""
    spec = MODELS[name]
    path = store / 'weights' / spec['file']
    if not path.is_file():
        raise SystemExit(f'{path} is missing: download it from {spec["url"]}')
    kind = 'sha256' if 'sha256' in spec else 'md5'
    if file_hash(path, kind) != spec[kind]:
        raise SystemExit(f'{path} is not the expected download ({kind} differs): delete it')
    return path


# --- The network: photos only ------------------------------------------------------------

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(5 << 20)


def fetch_photos(images: Path) -> None:
    """Download a 640 px copy of each photo in PHOTOS, checking its licence on Commons."""
    images.mkdir(parents=True, exist_ok=True)
    pages = json.loads(_get(commons_query_url([p['title'] for p in PHOTOS])))['query']['pages']
    by_title = {p['title']: p for p in pages.values()}
    for photo in PHOTOS:
        page = by_title.get(photo['title'].replace('_', ' '))
        if not page or 'imageinfo' not in page:
            print(f'  {photo["name"]}: not on Commons any more, skipped')
            continue
        info = page['imageinfo'][0]
        licence = info['extmetadata'].get('LicenseShortName', {}).get('value', '?')
        if licence != photo['licence']:
            print(f'  {photo["name"]}: licence now {licence!r}, not {photo["licence"]!r}: skipped')
            continue
        data = _get(info['thumburl'])
        if not looks_like_jpeg(data):
            print(f'  {photo["name"]}: not a JPEG, skipped')
            continue
        (images / f'{photo["name"]}.jpg').write_bytes(data)
        artist = info['extmetadata'].get('Artist', {}).get('value', '?')
        print(f'  {photo["name"]}.jpg  {len(data) // 1024} KB  {licence}  '
              f'{info["descriptionurl"]}\n      artist (HTML): {artist[:200]}')


# --- The runners: these need the models' libraries --------------------------------------

class UltralyticsRunner:
    """A YOLO model (.pt on cpu or mps, or its Core ML export)."""

    def __init__(self, weights: Path, device: str):
        from ultralytics import YOLO
        self.device = device
        if device == 'coreml':
            package = weights.with_suffix('.mlpackage')
            if not package.exists():
                YOLO(str(weights)).export(format='coreml', imgsz=640)
            self.model, self.kwargs = YOLO(str(package), task='detect'), {}
        else:
            self.model, self.kwargs = YOLO(str(weights)), {'device': device}

    def __call__(self, image) -> List[tuple]:
        result = self.model.predict(image, imgsz=640, conf=LOW, verbose=False, **self.kwargs)[0]
        names = result.names
        return [(names[int(c)], float(s))
                for c, s in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist())]


class RfdetrRunner:
    """An RF-DETR model (PyTorch on cpu or mps, or its Core ML export)."""

    def __init__(self, weights: Path, variant: str, device: str):
        import rfdetr
        from rfdetr.assets.coco_classes import COCO_CLASSES
        self.labels = dict(COCO_CLASSES)
        self.device = device
        torch_device = 'cpu' if device == 'coreml' else device
        self.model = getattr(rfdetr, variant)(pretrain_weights=str(weights), device=torch_device)
        self.coreml = None
        if device == 'coreml':
            out = weights.parent / (weights.stem + '-coreml')
            if not any(out.glob('*.mlpackage')):
                self.model.export(output_dir=str(out), format='coreml', verbose=False)
            import coremltools as ct
            self.coreml = ct.models.MLModel(str(next(out.glob('*.mlpackage'))))
            self.size = self.model.model_config.resolution
        else:
            # rfdetr 1.11 calls it inference(); older versions optimize_for_inference().
            optimise = getattr(self.model, 'inference', None) or self.model.optimize_for_inference
            try:
                optimise()                      # traced (TorchScript): the fast path
            except Exception:  # noqa: B902 (a device it can't trace: run it plain)
                optimise(compile=False)

    def __call__(self, image) -> List[tuple]:
        if self.coreml is None:
            det = self.model.predict(image, threshold=LOW)
            return [(self.labels.get(int(c), str(c)), float(s))
                    for c, s in zip(det.class_id.tolist(), det.confidence.tolist())]
        import numpy as np
        spec = self.coreml.get_spec().description
        name = spec.input[0].name
        picture = image.convert('RGB').resize((self.size, self.size))
        array = np.asarray(picture, dtype=np.float32) / 255.0
        mean, std = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
        array = ((array - mean) / std).astype(np.float32).transpose(2, 0, 1)[None]
        out = self.coreml.predict({name: array})
        logits = next(v for k, v in out.items() if 'logit' in k.lower()
                      or (hasattr(v, 'shape') and v.shape[-1] > 4))
        return detr_detections(logits.reshape(-1, logits.shape[-1]), self.labels)


def make_runner(store: Path, name: str, device: str):
    spec = MODELS[name]
    weights = checked_weights(store, name)
    if spec['family'] == 'ultralytics':
        return UltralyticsRunner(weights, device)
    return RfdetrRunner(weights, spec['variant'], device)


def size_text(store: Path, name: str, runner) -> str:
    """Describe the download's size, and the weights (millions) where the library tells."""
    mb = (store / 'weights' / MODELS[name]['file']).stat().st_size / 1e6
    params = None
    try:
        module = runner.model.model if hasattr(runner.model, 'model') else None
        if hasattr(module, 'parameters'):
            params = sum(p.numel() for p in module.parameters())
        elif hasattr(module, 'model') and hasattr(module.model, 'parameters'):
            params = sum(p.numel() for p in module.model.parameters())
    except Exception:  # noqa: B902 (a size is a nicety: never fail the run for it)
        params = None
    return size_words(mb, params)


def size_words(file_mb: float, params: Optional[int]) -> str:
    """'6 MB file; 2.6 M weights (10 MB at fp32)': a training checkpoint holds more."""
    text = f'{file_mb:.0f} MB file'
    if params:
        text += f'; {params / 1e6:.1f} M weights ({params * 4 / 1e6:.0f} MB at fp32)'
    return text


def load_pictures(store: Path, frames: Optional[Path]):
    """Every picture to test: the photos, then the Gazebo frames. Returns (images, expect)."""
    from PIL import Image
    pictures, expect = [], {}
    for photo in PHOTOS:
        path = store / 'images' / f'{photo["name"]}.jpg'
        if path.is_file():
            pictures.append((photo['name'], Image.open(path).convert('RGB')))
            expect[photo['name']] = list(photo['expect'])
    found = frames.glob('road_sign_*m.png') if frames and frames.is_dir() else []
    for path in sorted(found, key=lambda f: -(frame_distance(f.name) or 0.0)):
        pictures.append((path.stem, Image.open(path).convert('RGB')))
        expect[path.stem] = ['stop sign']
    return pictures, expect


def run(store: Path, frames: Optional[Path], models: List[str], devices: List[str],
        repeats: int) -> Dict:
    pictures, expect = load_pictures(store, frames)
    if not pictures:
        raise SystemExit('no pictures: run with --fetch, or tools/sim_frames.py, first')
    results, rows, sizes, reach, failed = {}, [], {}, {}, []
    distances = {n: d for n, _ in pictures if (d := frame_distance(n)) is not None}
    for name in models:
        for device in devices:
            try:
                runner = make_runner(store, name, device)
                runner(pictures[0][1])          # warm up: the first call compiles
            except Exception as e:  # noqa: B902 (record why, and go on with the next)
                failed.append((name, device, f'{type(e).__name__}: {str(e)[:160]}'))
                print(f'== {name} on {device}: FAILED {failed[-1][2]}', flush=True)
                continue
            sizes.setdefault(name, size_text(store, name, runner))
            per_image = []
            for picture, image in pictures:
                times, found = [], []
                for _ in range(repeats):
                    t0 = time.perf_counter()
                    found = runner(image)
                    times.append((time.perf_counter() - t0) * 1000.0)
                per_image.append({'image': picture, 'best': best_scores(found),
                                  'n': counts(found), 'ms': times})
            results[(name, device)] = per_image
            rows.append(summarise(name, device, per_image, expect))
            reach[(name, device)] = frames_reach(per_image, distances)
            print(f'== {name} on {device}: {rows[-1]["ms"]} ms', flush=True)
    licences = {m: MODELS[m]['licence'] for m in models}
    return {'rows': rows, 'results': results, 'expect': expect, 'sizes': sizes,
            'licences': licences, 'reach': reach, 'failed': failed}


def default_devices() -> List[str]:
    devices = ['cpu']
    try:
        import torch
        if torch.backends.mps.is_available():
            devices.append('mps')
    except ImportError:
        pass
    if sys.platform == 'darwin':
        devices.append('coreml')
    return devices


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('--store', type=Path, default=Path.home() / 'aav-models',
                   help='where the downloads are (default ~/aav-models)')
    p.add_argument('--frames', type=Path, help='Gazebo frames (default <store>/frames)')
    p.add_argument('--models', nargs='+', default=list(MODELS), choices=list(MODELS))
    p.add_argument('--devices', nargs='+', choices=['cpu', 'mps', 'coreml'])
    p.add_argument('--repeats', type=int, default=5, help='timed runs per picture')
    p.add_argument('--fetch', action='store_true', help='download the photos, then stop')
    p.add_argument('--out', type=Path, help='also write every score to this JSON file')
    args = p.parse_args(argv)
    store = args.store.expanduser()
    if args.fetch:
        fetch_photos(store / 'images')
        return 0
    out = run(store, args.frames or store / 'frames', args.models,
              args.devices or default_devices(), args.repeats)
    print()
    print(main_table(out['rows'], out['sizes'], out['licences'], out['reach']))
    print()
    if out['results']:
        print(image_table(out['results'], out['expect']))
    for name, device, why in out['failed']:
        print(f'\nNot run: {name} on {device}: {why}')
    if args.out:
        args.out.write_text(json.dumps(
            {**out, 'results': {f'{m} {d}': v for (m, d), v in out['results'].items()},
             'reach': {f'{m} {d}': v for (m, d), v in out['reach'].items()}}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
