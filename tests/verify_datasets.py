import os
import glob
import sys

print("=== TrafficSense Dataset Verification ===")

def count_files(directory, extensions):
    count = 0
    if os.path.exists(directory):
        for ext in extensions:
            count += len(glob.glob(os.path.join(directory, f"*{ext}")))
    return count

base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
driveindia_dir = os.path.join(base_dir, "driveindia")
dats_dir = os.path.join(base_dir, "dats_2022")

checks_passed = 0
total_checks = 2

# DriveIndia Checks
driveindia_images = 0
driveindia_labels = 0
driveindia_status = "PENDING"
if os.path.exists(driveindia_dir) and not os.path.exists(os.path.join(driveindia_dir, "README.md")):
    for split in ["train", "valid", "test"]:
        driveindia_images += count_files(os.path.join(driveindia_dir, split, "images"), [".jpg", ".png", ".jpeg"])
        driveindia_labels += count_files(os.path.join(driveindia_dir, split, "labels"), [".txt"])
    
    if driveindia_images > 0:
        driveindia_status = "OK"
        checks_passed += 1
    else:
        driveindia_status = "PARTIAL"
        
    data_yaml = os.path.join(driveindia_dir, "data.yaml")
    if os.path.exists(data_yaml):
        print("DriveIndia Classes:")
        with open(data_yaml, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if "names:" in line:
                    print(line.strip())
else:
    # Meaning the README is there, so it's not downloaded yet.
    if os.path.exists(driveindia_dir):
        # We might have the README
        pass
    else:
        print("[FAIL] data/raw/driveindia/ directory missing.")

# DATS_2022 Checks
dats_images = 0
dats_labels = 0
dats_status = "PENDING"
if os.path.exists(dats_dir) and not os.path.exists(os.path.join(dats_dir, "README.md")):
    dats_images += count_files(os.path.join(dats_dir, "images"), [".jpg", ".png", ".jpeg"])
    dats_labels += count_files(os.path.join(dats_dir, "annotations"), [".xml"])
    if dats_images > 0:
        dats_status = "OK"
        checks_passed += 1
    else:
        dats_status = "PARTIAL"
else:
    if not os.path.exists(dats_dir):
        print("[FAIL] data/raw/dats_2022/ directory missing.")

print("")
print(f"{'Dataset':<15} | {'Images':<10} | {'Labels':<10} | {'Status'}")
print("-" * 50)
print(f"{'DriveIndia':<15} | {driveindia_images:<10} | {driveindia_labels:<10} | {driveindia_status}")
print(f"{'DATS_2022':<15} | {dats_images:<10} | {dats_labels:<10} | {dats_status}")
print("")
print(f"Dataset verification: {checks_passed}/{total_checks} checks passed.")
