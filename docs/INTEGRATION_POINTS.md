# TrafficSense → CoLLMLight Integration Plan

## Step 3.2: Perception Adapter
- **File**: `src/orchestration/perception_adapter.py` (to be created)
- **Injects**: `PerceptionToCoLLMLight` states into CoLLMLight agent loop
- **Replaces**: `Simulator.get_state()` calls

## Step 3.3: Local LLM Server
- **Tool**: llama.cpp server with Gemma 3 4B Q4
- **Endpoint**: `http://localhost:8000/v1`
- **Replaces**: GPT-4o API calls

## Step 3.4: Cooperative Reasoning Test
- **Dataset**: Synthetic 4x4 with perception-injected states
- **Goal**: Verify SR module works with real vehicle mix data

## Step 3.5: Network Simulation
- **Network**: 2×2 Indian intersection grid
- **Goal**: End-to-end multi-agent orchestration
