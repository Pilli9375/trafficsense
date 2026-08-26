import os
import sys
import subprocess
from pathlib import Path

def main():
    print("=== TrafficSense Setup Verification ===")
    
    # Detect project root (this script is in tests/, so go up one level)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    # Check folders
    folders_to_check = [
        "docs",
        "docs/base_papers",
        "docs/reports",
        "data",
        "data/raw",
        "data/processed",
        "data/synthetic",
        "src",
        "src/perception",
        "src/orchestration",
        "src/simulation",
        "src/dashboard",
        "models",
        "models/yolo",
        "models/llm",
        "models/checkpoints",
        "outputs",
        "outputs/detection_videos",
        "outputs/metrics",
        "outputs/plots",
        "tests",
        "scripts"
    ]
    
    checks_passed = 0
    total_checks = len(folders_to_check) + 5  # folders + 3 files + git dir + git status
    
    for folder in folders_to_check:
        folder_path = project_root / folder
        if folder_path.is_dir():
            print(f"[OK] {folder}")
            checks_passed += 1
        else:
            print(f"[MISSING] {folder}")
            
    # Check files
    files_to_check = ["README.md", ".gitignore", "requirements.txt"]
    for file_name in files_to_check:
        file_path = project_root / file_name
        if file_path.is_file():
            print(f"[OK] {file_name}")
            checks_passed += 1
        else:
            print(f"[MISSING] {file_name}")
            
    # Check git initialization
    git_dir = project_root / ".git"
    if git_dir.is_dir():
        print("[OK] .git/")
        checks_passed += 1
    else:
        print("[MISSING] .git/")
        
    # Check git status
    try:
        git_status = subprocess.check_output(["git", "status"], text=True)
        print("--- Git Status (First 3 Lines) ---")
        lines = git_status.strip().split('\n')
        for line in lines[:3]:
            print(line)
        print("----------------------------------")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] git status command failed: {e}")
        
    # Print Python version
    print(f"Python version: {sys.version.split(' ')[0]}")
    
    print(f"Setup verification complete. {checks_passed}/{total_checks} checks passed.")

if __name__ == "__main__":
    main()
