import os
import glob
import shutil
import xml.etree.ElementTree as ET

def count_files(directory, extensions):
    count = 0
    if os.path.exists(directory):
        for ext in extensions:
            count += len(glob.glob(os.path.join(directory, f"*{ext}")))
    return count

def analyze_dataset(path, is_yolo=True):
    print(f"Analyzing dataset at: {path}")
    if not os.path.exists(path):
        print(f"  [!] Path does not exist.")
        return 0, 0, []
    
    images = 0
    labels = 0
    classes = []
    
    if is_yolo:
        for split in ["train", "valid", "test"]:
            images += count_files(os.path.join(path, split, "images"), [".jpg", ".png", ".jpeg"])
            labels += count_files(os.path.join(path, split, "labels"), [".txt"])
        
        yaml_path = os.path.join(path, "data.yaml")
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r') as f:
                for line in f:
                    if "names:" in line:
                        classes_str = line.split("names:")[1].strip()
                        # Very basic parsing for demo
                        classes = [c.strip(" '\"[]") for c in classes_str.split(",")]
    else:
        images += count_files(os.path.join(path, "images"), [".jpg", ".png", ".jpeg"])
        labels += count_files(os.path.join(path, "annotations"), [".xml"])
        
        # Check a few XML files for classes
        xml_files = glob.glob(os.path.join(path, "annotations", "*.xml"))
        found_classes = set()
        for xml_file in xml_files[:10]:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                for obj in root.findall('object'):
                    name = obj.find('name').text
                    found_classes.add(name)
            except Exception:
                pass
        classes = list(found_classes)
        
    print(f"  Images: {images}")
    print(f"  Labels: {labels}")
    print(f"  Classes found: {len(classes)}")
    return images, labels, classes

def convert_voc_to_yolo(xml_path, img_width, img_height, class_map):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        yolo_lines = []
        for obj in root.findall('object'):
            name = obj.find('name').text
            if name not in class_map:
                continue
            cls_id = class_map[name]
            bndbox = obj.find('bndbox')
            xmin = float(bndbox.find('xmin').text)
            ymin = float(bndbox.find('ymin').text)
            xmax = float(bndbox.find('xmax').text)
            ymax = float(bndbox.find('ymax').text)
            
            x_center = ((xmin + xmax) / 2) / img_width
            y_center = ((ymin + ymax) / 2) / img_height
            width = (xmax - xmin) / img_width
            height = (ymax - ymin) / img_height
            
            yolo_lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
        return yolo_lines
    except Exception as e:
        print(f"Error parsing XML {xml_path}: {e}")
        return []

def merge_datasets(driveindia_path, dats_path, output_path):
    print("\n=== Merging Datasets ===")
    
    # Simple copy for DriveIndia
    for split in ["train", "valid", "test"]:
        for dtype in ["images", "labels"]:
            src_dir = os.path.join(driveindia_path, split, dtype)
            dst_dir = os.path.join(output_path, split, dtype)
            os.makedirs(dst_dir, exist_ok=True)
            if os.path.exists(src_dir):
                files = glob.glob(os.path.join(src_dir, "*.*"))
                for f in files:
                    shutil.copy2(f, dst_dir)
                    
    print("  DriveIndia merge complete.")
    
    # Process DATS if available
    dats_img_dir = os.path.join(dats_path, "images")
    dats_ann_dir = os.path.join(dats_path, "annotations")
    
    if os.path.exists(dats_img_dir) and os.path.exists(dats_ann_dir):
        print("  Processing DATS_2022...")
        # Add VOC to YOLO logic here (skipped in this stub since files are missing)
        pass
    else:
        print("  DATS_2022 not found. Skipping.")
        with open(os.path.join(dats_path, "PENDING_DOWNLOAD.md"), "w") as f:
            f.write("# DATS_2022 Pending Download\nInstructions to download...")
            
    print("Merge process finished.")

if __name__ == "__main__":
    print("=== Unified Indian Traffic Dataset Pipeline ===")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    di_path = os.path.join(base_dir, "data", "raw", "driveindia")
    dats_path = os.path.join(base_dir, "data", "raw", "dats_2022")
    out_path = os.path.join(base_dir, "data", "processed", "unified_indian")
    
    analyze_dataset(di_path, is_yolo=True)
    analyze_dataset(dats_path, is_yolo=False)
    
    merge_datasets(di_path, dats_path, out_path)
    
    print("\nPipeline execution complete.")
