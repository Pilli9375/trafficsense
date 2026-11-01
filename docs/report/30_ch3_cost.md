# Cost Analysis {#sec:cost}

This chapter lists every tool, dataset, model and piece of equipment the project used, with its
licence and its cost to the project. Nothing was bought. All the software is free and open
source, or free of charge. The dataset and the model weights are free for research use under
their own terms. The laptops were the team members' own and are not costed. No price in this
chapter is estimated.

## List of Components and Their Cost {#sec:cost-list}

::: {#tbl:cost short="List of components and their cost"}
| Component | Used for | Licence or terms | Cost to the project |
|:---------------------------|:------------------------------|:--------------------------------|:--------------------|
| CityFlow | traffic simulation | Apache-2.0 | free (open source) |
| Python | all project code | PSF License | free (open source) |
| NumPy | metrics, statistics | BSD-3-Clause | free (open source) |
| PyYAML | configuration files | MIT | free (open source) |
| requests | calls to Ollama and the NVIDIA API | Apache-2.0 | free (open source) |
| OpenCV, Pillow | images and video | Apache-2.0; MIT-CMU | free (open source) |
| Matplotlib, Plotly | report figures, dashboard charts | Matplotlib License (PSF-based); MIT | free (open source) |
| PyTorch, torchvision | detector training and inference | BSD-3-Clause with bundled Apache-2.0, BSD-2-Clause, BSL-1.0 and MIT parts; BSD | free (open source) |
| Ultralytics YOLOv8 | the detector | AGPL-3.0 | free (open source) |
| Ollama | local LLM server | MIT | free (open source) |
| Streamlit | dashboard | Apache-2.0 | free (open source) |
| pytest, Playwright | tests, dashboard layout tests and screenshots | MIT; Apache-2.0 | free (open source) |
| pandoc, LibreOffice, pypdfium2 | this report (Word file and PDF) | GPL-2.0-or-later; MPL-2.0; Apache-2.0 or BSD-3-Clause | free (open source) |
| Ubuntu in WSL2 | operating system for all the work | open-source licences of the distribution | free |
| NVIDIA driver and CUDA | GPU computing | NVIDIA's licence | free of charge |
| `llama3.2:3b`, `llama3.1:8b` | LLM agents | Llama Community License | free download, not redistributed |
| `gemma4:e4b`, `gemma3:4b` | LLM agents | Gemma terms of use | free download, not redistributed |
| `qwen2.5:3b` | LLM agent (benchmark) | Qwen licence | free download, not redistributed |
| `nvidia/nemotron-3-ultra-550b-a55b` | exploratory model-size study only | NVIDIA's API terms | not recorded by the project |
| India Driving Dataset (IDD) | detector training and testing | IDD terms of use, after registration | free for research, not redistributed |
| CoLLMLight code and data | validation of the simulator | no licence file (checked at commit `ce204a9`) | free download; run unmodified, not copied |
| Geist and Geist Mono fonts | dashboard | SIL Open Font License 1.1 | free (open source) |
| Times New Roman, Consolas | fonts of this report | licensed with Windows | not costed (came with the laptops) |
| Project laptop, second laptop | all computing (@tbl:hardware) | the team's own | not costed |
| TrafficSense code | the system itself (own work) | no licence file in the repository | not applicable |

: Every tool, dataset, model and piece of equipment used, its licence and its cost to the project.
Licences of the Python packages are those their installed package metadata state.
:::

Two of these licences carry obligations worth knowing before any deployment. Ultralytics YOLOv8 is
under AGPL-3.0, which requires the source of a networked application that uses it to be made
available to its users. The model weights and IDD may be used only under their own terms, which
is why neither is redistributed with the project.

## What a Real Deployment Would Additionally Need (Not Costed) {#sec:cost-deploy}

The project is a simulation study, so a deployment at real junctions would need components the
project never had. **None of them was priced**: their cost depends on vendors, on the number of
junctions and on the city's existing equipment, and an estimate made here would be invented.

* **Cameras at every junction approach**, with poles, mounting and power. The detector was
  trained and tested on dash-camera images, so it would also need images from these cameras to
  be retrained and its errors measured again (@sec:error-model).
* **Computing at the junction or in a control centre**, with a GPU for the detector and the LLM
  agents.
* **An interface to the existing signal controllers**, approved by the traffic authority, with a
  safe fallback to the controller's own fixed plan on any fault.
* **Network links** between neighbouring junctions (the agents share their neighbours' states)
  and to a control centre.
* **Ambulance positions from GPS or V2X**, which the simulation assumes (@sec:ambulance-design).
* **Field trials and calibration** against counted traffic, maintenance, power backup, and
  protection of the camera footage.
