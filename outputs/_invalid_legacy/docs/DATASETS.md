# TrafficSense Datasets

## 1. DriveIndia
- **Source**: Pending manual download (e.g. from Kaggle/Roboflow)
- **Format**: YOLO (darknet)
- **Total Images**: ~67,000 (TBD based on actual download)
- **Train/Valid/Test Split**: TBD
- **Classes**: car, motorcycle, bus, truck, autorickshaw, bicycle, ambulance, police_vehicle, tractor, pedestrian, traffic_light, traffic_sign, etc. (up to 24 classes depending on source)
- **License**: CC BY 4.0 / Public Domain (Verify on source)
- **Usage**: Training YOLOv8n for Indian vehicle detection

## 2. DATS_2022
- **Source**: Pending manual download
- **Format**: Pascal VOC XML
- **Total Images**: TBD
- **Classes**: car, bus, truck, motorcycle, auto, bicycle, pedestrian
- **License**: Verify on source
- **Usage**: Augmentation/validation of Indian traffic scenarios

## 3. CoLLMLight Synthetic
- **Source**: Generated from CityFlow simulator
- **Location**: WSL ~/trafficsense/CoLLMLight/data/
- **Networks**: Hangzhou 4x4, Jinan 3x4, NewYork 28x7, Synthetic 4x4
- **Usage**: Training and evaluating the multi-agent orchestration layer

## 4. Data Pipeline
[Placeholder for Step 2.1 — will document the conversion/merging process]
