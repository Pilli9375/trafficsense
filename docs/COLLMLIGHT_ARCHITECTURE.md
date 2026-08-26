# CoLLMLight Architecture Map

## Repository Structure
```text
CoLLMLight/
├── config/             # Configuration files
├── data/               # Datasets and intersection roadnets (Synthetic, HangZhou, etc.)
├── framework/          # Engine and agent frameworks
├── models/             # Implementations of various agents (CoLLMLightAgent, chatgpt, etc.)
├── utils/              # Core utilities (cityflow_env.py, prompts.py, LLMs.py, pipeline.py)
├── run_CoLLMlight.py   # Main entry point for evaluation
├── run_fts.py          # Stage 1: fine-tuning data sampling
├── reasoning_refinement.py # Stage 2: reasoning refinement
└── ppo_ft.py           # Stage 3: policy refinement
```

## Core Modules

### `run_CoLLMlight.py`
**Purpose**: Main entry point that sets up the CityFlow environment and orchestrates the multi-agent execution loop.
**Key Functions**: `main()`, which initializes `pipeline.py`.
**Relation to Paper**: Triggers the evaluation phase of the trained CoLLMLight models on the specified traffic network.

### `utils/cityflow_env.py`
**Purpose**: Wraps the CityFlow simulator to provide states and step the simulation.
**Key Functions**: `get_state()`, `_inner_step()`.
**Relation to Paper**: Serves as the simulated traffic environment from which perfect spatiotemporal states are extracted.

### `utils/LLMs.py` & `models/chatgpt.py`
**Purpose**: Handles the API calls to Large Language Models.
**Key Functions**: Functions calling `openai.chat.completions.create` or `generate`.
**Relation to Paper**: Executes the reasoning and decision-making logic of the agents by querying the LLM API.

### `models/CoLLMLightAgent.py` & `framework/CoLLMlight.py`
**Purpose**: Implements the CoLLMLight cooperative agent logic.
**Key Functions**: Methods building prompts and processing neighbor communication.
**Relation to Paper**: Implements the Spatiotemporal Reasoning (SR) and Real-time Decision (RD) modules.

## Data Flow
CityFlow Simulator → `utils.cityflow_env.get_state()` → CoLLMLight Agent (SR + RD) → `utils.LLMs` (OpenAI API) → Agent Decision → CityFlow Simulator `_inner_step()`

## Integration Points for TrafficSense

### Point 1: Observation Source
- **Current**: `cityflow_env.py` gets perfect state variables directly from the CityFlow engine via `get_state()`.
- **Change**: Read states directly from the TrafficSense perception JSON file (`perception_states.json`) using the `PerceptionToCoLLMLight` bridge.
- **Strategy**: In our orchestration layer adapter, we will replace `env.get_state()` with a call to `state_exporter.convert_batch()` which parses YOLOv8 outputs.

### Point 2: Vehicle Mix Extension
- **Current**: CoLLMLight states are strictly numeric (`n_queue`, `n_move`, `occupancy`, `tau`, `rho`).
- **Change**: We inject `vehicle_mix` and `congestion_level` fields into the state dictionaries.
- **Strategy**: The `state_exporter.py` bridge already performs this. We must ensure the `prompts.py` or agent prompt builder includes this extension text in its messages to the LLM.

### Point 3: Indian Traffic Context
- **Current**: Prompts in `utils/prompts.py` are generic for standard structured intersections.
- **Change**: Prepend Indian urban traffic context (e.g., highly heterogeneous traffic, lack of strict lane discipline, significant autorickshaw/bike presence) to the system prompts.
- **Strategy**: Modify the prompt generation in the agent/orchestrator to include a specialized context block.

## Files to Modify (Step 3.2)
1. `src/orchestration/perception_adapter.py` (New file to create)
2. `utils/prompts.py` (To inject Indian traffic context and `vehicle_mix`)
3. `models/chatgpt.py` or `utils/LLMs.py` (To route requests to a local LLM instead of OpenAI)
