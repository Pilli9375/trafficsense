# TrafficSense

## Abstract
TrafficSense is a multi-agent smart city traffic management system designed for Indian urban road conditions. It integrates YOLOv8 for perception and large language models for intelligent traffic signal control orchestration. The project aims to improve traffic flow and reduce congestion through cooperative AI agents.

## Base Paper
CoLLMLight: Cooperative Large Language Model Agents for Network-Wide Traffic Signal Control, Yuan et al., ICLR 2026

## Tech Stack
- YOLOv8n
- CityFlow
- Gemma 3 4B
- Streamlit
- PyTorch

## Dual Environment Setup
The project utilizes a dual environment setup: Windows native is used for YOLO and the dashboard for optimal GPU utilization and UI development. WSL2 is used for CityFlow and CoLLMLight to support their Linux-centric dependencies and environment.

## Directory Structure
```
trafficSense/
├── docs/
│   ├── base_papers/
│   └── reports/
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
├── src/
│   ├── perception/
│   ├── orchestration/
│   ├── simulation/
│   └── dashboard/
├── models/
│   ├── yolo/
│   ├── llm/
│   └── checkpoints/
├── outputs/
│   ├── detection_videos/
│   ├── metrics/
│   └── plots/
├── tests/
└── scripts/
```

## Timeline
- Second Review: Sep 29-Oct 3, 2026
- Final Review: Nov 17-21, 2026
