# DriveIndia Dataset - Manual Download Required

The direct download link for the DriveIndia dataset is no longer active. You must download it manually.

## Steps to Download:
1. Create an account on Kaggle (https://www.kaggle.com) or Roboflow (https://universe.roboflow.com).
2. Search for **"Indian vehicle detection dataset"** or **"DriveIndia dataset YOLO"**.
3. Download the dataset in **YOLOv8** format.
4. Extract the contents into this folder (`C:\Pilli\trafficsense\data\raw\driveindia\`).
5. Ensure the structure looks like this:
   ```
   data/raw/driveindia/
   ├── train/
   │   ├── images/
   │   └── labels/
   ├── valid/
   │   ├── images/
   │   └── labels/
   └── test/
       ├── images/
       └── labels/
   ```
   If the downloaded zip has a different structure (e.g., `export/images` and `export/labels`), reorganize the folders to match the train/valid/test structure.

Once this is complete, re-run `python tests/verify_datasets.py`.
