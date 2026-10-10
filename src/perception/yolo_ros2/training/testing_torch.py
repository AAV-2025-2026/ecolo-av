from ultralytics import YOLO

if __name__ ==  '__main__':
    
    model = YOLO("yolo11n.yaml")

    results = model.train(data="data.yaml", epochs=50)
