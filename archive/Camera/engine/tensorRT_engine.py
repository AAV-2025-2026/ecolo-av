from ultralytics import YOLO
model = YOLO('/home/aavjetson/Desktop/aav/Camera/model/best.pt')
model.export(format='onnx', imgsz=640, simplify=True)