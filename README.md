<p align="center">
  <img src="https://img.icons8.com/color/96/traffic-light.png" width="80" />
</p>
<h1 align="center">TrafficSense</h1>
<p align="center">
  <b>A Multi-Agent Smart City Traffic Management System</b><br>
  Integrating YOLOv8 Perception and LLM Orchestration for Indian Urban Roads
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" />
  <img src="https://img.shields.io/badge/PyTorch-2.5.1+cu121-ee4c2c?logo=pytorch" />
  <img src="https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?logo=yolo" />
  <img src="https://img.shields.io/badge/Streamlit-1.62-ff4b4b?logo=streamlit" />
  <img src="https://img.shields.io/badge/Base%20Paper-ICLR%202026-purple" />
  <img src="https://img.shields.io/badge/Status-Second%20Review%20Ready-success" />
</p>

---

## 🎯 Abstract

TrafficSense is a **multi-agent smart city traffic management system** designed specifically for **Indian urban road conditions**. It bridges the gap between computer vision perception and cooperative AI orchestration by:

- 🚗 **YOLOv8n Perception Layer** — Real-time detection of Indian vehicle classes (cars, auto-rickshaws, buses, tractors, pushcarts) with **mAP50 = 0.50**
- 🧠 **Cooperative LLM Orchestration** — Adapted from [CoLLMLight](https://arxiv.org/abs/2503.11739) (ICLR 2026), using spatiotemporal reasoning across multiple intersections
- 🚦 **Adaptive Signal Control** — Dynamic phase timing based on real-time congestion analysis
- 📊 **Real-time Dashboard** — Streamlit-based monitoring, network control, and performance analytics

**All components run on consumer hardware** (RTX 4050 6GB, 24GB RAM) with **zero API cost** using locally-deployed Gemma 3 4B via Ollama.

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│ TRAFFICSENSE ARCHITECTURE                                           │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 5: DASHBOARD & VISUALIZATION                                  │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐   │
│ │ Streamlit   │  │ Real-time   │  │ Signal Timing Override UI   │   │
│ │ Web UI      │  │ Heatmaps    │  │ (Emergency/Police)          │   │
│ └─────────────┘  └─────────────┘  └─────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 4: MULTI-AGENT LLM ORCHESTRATION (CoLLMLight-based)           │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│ │ Spatiotemporal  │  │ Async Decision  │  │ Cost-Aware Cooper.  │   │
│ │ Reasoning(SR)   │  │ Module (RD)     │  │ Optimization        │   │
│ └─────────────────┘  └─────────────────┘  └─────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3: ADAPTIVE SIGNAL CONTROL                                    │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐   │
│ │ Signal      │  │ Queue       │  │ Phase Duration Optimizer    │   │
│ │ Phase       │  │ Pressure    │  │ (Green time allocator)      │   │
│ │ Selector    │  │ Calculator  │  │                             │   │
│ └─────────────┘  └─────────────┘  └─────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2: PERCEPTION (YOLOv8 + Indian Adaptation)                    │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐   │
│ │ Vehicle     │  │ Vehicle     │  │ Density / Congestion        │   │
│ │ Detection   │  │ Classific.  │  │ Severity Estimator          │   │
│ │ (YOLOv8n)   │  │ (Car/Bus/..)│  │ (Vehicles/m + Wait time)    │   │
│ └─────────────┘  └─────────────┘  └─────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 1: SIMULATION & DATA (CityFlow + Indian Scenarios)            │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐   │
│ │ CityFlow    │  │ Indian Road │  │ Synthetic Traffic Flow      │   │
│ │ Simulator   │  │ Networks    │  │ Generator (rush hour etc)   │   │
│ └─────────────┘  └─────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📸 Screenshots

| Live Monitor | Network Control | Analytics |
|:------------:|:---------------:|:---------:|
| *Video upload + YOLO detection* | *2×2 grid + LLM reasoning* | *FixedTime vs TrafficSense* |
| ![Live](docs/screenshots/live_monitor.png) | ![Network](docs/screenshots/network_control.png) | ![Analytics](docs/screenshots/analytics.png) |

> 📷 Screenshots to be captured during final demo recording.

---

## 🚀 Quick Start

### Prerequisites
- **OS:** Windows 11 + WSL2 Ubuntu 22.04
- **GPU:** NVIDIA RTX 4050 6GB+ (CUDA 12.1)
- **RAM:** 24GB DDR5
- **Python:** 3.11 or 3.12 (3.13 will install CPU-only PyTorch)

### 1. Clone & Setup
```bash
git clone https://github.com/Pilli9375/trafficsense.git
cd trafficsense
```

### 2. Windows Environment (YOLO + Dashboard)
```powershell
# Create venv with Python 3.12 (NOT 3.13)
py -3.12 -m venv venv
venv\Scripts\activate

# Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install ultralytics streamlit plotly pandas opencv-python numpy pillow scipy tqdm transformers

# Verify GPU
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

### 3. WSL Environment (CityFlow + CoLLMLight)
```bash
# In WSL Ubuntu 22.04
sudo apt update && sudo apt install -y python3-pip python3-venv git build-essential
pip install cityflow torch==2.2.2 transformers==4.48.2 openai

# Clone base paper
git clone https://github.com/usail-hkust/CoLLMLight.git
```

### 4. Start Local LLM (Ollama)
```bash
# In WSL
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama serve
```

### 5. Run Dashboard
```powershell
# In Windows PowerShell (venv activated)
streamlit run src\dashboard\app.py
```
Open [http://localhost:8501](http://localhost:8501/) in your browser.

---

## 📁 Directory Structure
```text
TrafficSense/
├── docs/
│   ├── report/              # Full project report
│   ├── screenshots/         # Dashboard screenshots
│   └── COLLMLIGHT_ARCHITECTURE.md
├── data/
│   ├── raw/                 # DriveIndia, DATS_2022
│   └── processed/           # Unified dataset
├── src/
│   ├── perception/          # YOLOv8 + tracking + state exporter
│   ├── orchestration/       # CoLLMLight adapter + cooperative reasoning
│   ├── simulation/          # CityFlow wrapper + simulation loop
│   └── dashboard/           # Streamlit app (3 pages)
├── models/
│   └── yolo/best.pt         # Trained YOLOv8n (mAP50=0.50)
├── outputs/
│   ├── yolo_training/       # Training curves, confusion matrix
│   ├── perception_demo/     # Detection videos + states
│   └── simulation_results/  # Metrics + decisions
└── tests/                   # Verification scripts for every step
```

---

## 📊 Key Results

| Metric | Value |
|--------|-------|
| YOLOv8n mAP50 | 0.5001 |
| YOLOv8n mAP50-95 | 0.4847 |
| Training Time | 3.7 min (RTX 4050) |
| Model Size | 5.97 MB |
| Vehicle Classes | 11+ (Indian-specific) |
| LLM | Gemma 3 4B (local, zero API cost) |
| Decision Latency | ~12s per cooperative decision |
| Dashboard | 3-page Streamlit app |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Perception | YOLOv8n, ByteTrack, OpenCV |
| Orchestration | CoLLMLight (ICLR 2026), Gemma 3 4B |
| LLM Server | Ollama (OpenAI-compatible API) |
| Simulator | CityFlow |
| Dashboard | Streamlit, Plotly |
| OS | Windows 11 + WSL2 Ubuntu 22.04 |

---

## 📖 Base Paper

**CoLLMLight: Cooperative Large Language Model Agents for Network-Wide Traffic Signal Control**
Zirui Yuan, Siqi Lai, Hao Liu
*International Conference on Learning Representations (ICLR), 2026*

**Our Contribution:** While CoLLMLight achieves network-wide optimization via cooperative LLM agents, it assumes idealized simulator states. TrafficSense bridges the sim-to-real gap by integrating a YOLOv8-based perception layer trained on Indian road conditions to provide real-time vehicle counts, classifications, and density estimates as inputs to the cooperative orchestration layer.

---

## 📚 Citation

If you use this project, please cite:

```bibtex
@inproceedings{yuan2026collmlight,
  title={CoLLMLight: Cooperative Large Language Model Agents for Network-Wide Traffic Signal Control},
  author={Yuan, Zirui and Lai, Siqi and Liu, Hao},
  booktitle={ICLR},
  year={2026}
}
```

---

## 📅 Timeline

| Milestone | Date | Status |
|-----------|------|--------|
| Phase 1: Foundation | Aug 26 - Sep 1 | ✅ Complete |
| Phase 2: Perception | Sep 2 - Sep 8 | ✅ Complete |
| Phase 3: Orchestration | Sep 9 - Sep 15 | ✅ Complete |
| Phase 4: Dashboard | Sep 16 - Sep 22 | ✅ Complete |
| Phase 5: Polish | Sep 23 - Oct 3 | 🔄 In Progress |
| Second Review | Sep 29 - Oct 3 | 🎯 Target |
| Final Review | Nov 17 - Nov 21 | ⏳ Upcoming |

---

## 🤝 Acknowledgements
- CoLLMLight authors (Yuan et al., ICLR 2026) for the base paper and open-source code
- Ultralytics for YOLOv8
- Google for Gemma 3 model weights
- CityFlow project for the traffic simulator
- DriveIndia and DATS_2022 dataset creators

---

## 📄 License
This project is for academic purposes (B.Tech Capstone). Base paper code (CoLLMLight) retains its original license.

<p align="center">
  <b>TrafficSense</b> — Making Indian Roads Smarter, One Intersection at a Time 🚦
</p>
