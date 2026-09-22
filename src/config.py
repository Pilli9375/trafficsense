"""
TrafficSense Central Configuration
All paths are resolved dynamically from the project root.
"""

import os
from pathlib import Path

# Project root: two levels up from src/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Core directories
DATA_DIR = PROJECT_ROOT / 'data'
OUTPUTS_DIR = PROJECT_ROOT / 'outputs'
MODELS_DIR = PROJECT_ROOT / 'models'
SRC_DIR = PROJECT_ROOT / 'src'
TESTS_DIR = PROJECT_ROOT / 'tests'

# Data subdirectories
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
SYNTHETIC_DATA_DIR = DATA_DIR / 'synthetic'

# Model paths
YOLO_MODEL_PATH = MODELS_DIR / 'yolo' / 'best.pt'
YOLO_COCO_MODEL = 'yolov8n.pt'  # Auto-downloads from ultralytics hub

# Output subdirectories
SIMULATION_RESULTS_DIR = OUTPUTS_DIR / 'simulation_results'
DETECTION_VIDEOS_DIR = OUTPUTS_DIR / 'detection_videos'
PERCEPTION_DEMO_DIR = OUTPUTS_DIR / 'perception_demo'

# Dashboard
DASHBOARD_PORT = 8505

# Simulation
INDIAN_ROADNET = SYNTHETIC_DATA_DIR / 'indian_2x2_roadnet.json'
INDIAN_FLOW = SYNTHETIC_DATA_DIR / 'indian_2x2_flow.json'
INDIAN_CONFIG = SYNTHETIC_DATA_DIR / 'indian_2x2_config.json'

# LLM (Ollama)
OLLAMA_BASE_URL = 'http://localhost:11434/v1'
OLLAMA_MODEL = 'gemma3:4b'

# WSL path conversion helper
def to_wsl_path(windows_path):
    """Convert a Windows path to WSL /mnt/c/... path."""
    p = str(windows_path).replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        return f'/mnt/{drive}{p[2:]}'
    return p


def ensure_dirs():
    """Create all required output directories."""
    for d in [OUTPUTS_DIR, SIMULATION_RESULTS_DIR, DETECTION_VIDEOS_DIR, PERCEPTION_DEMO_DIR]:
        d.mkdir(parents=True, exist_ok=True)
