# DATS_2022 Dataset - Manual Download Required

The Dense Annotation Traffic Surveillance (DATS 2022) dataset requires manual download.

## Steps to Download:
1. Search for **"DATS 2022 dataset Indian traffic"** or check Kaggle for **"DATS vehicle detection"**.
2. Download the dataset (should contain Pascal VOC XML annotations).
3. Extract the contents into this folder (`C:\Pilli\trafficsense\data\raw\dats_2022\`).
4. Ensure the structure looks like this:
   ```
   data/raw/dats_2022/
   ├── images/
   └── annotations/
   ```

Once this is complete, re-run `python tests/verify_datasets.py`.
