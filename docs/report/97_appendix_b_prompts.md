# Prompts {#sec:app-prompts}

The system prompts below are rendered by the controllers' own code (`src/trafficsense/llm/prompt.py`)
with the timing used in the experiments. The LLM must answer with JSON that matches a schema
listing the allowed phase numbers; the reason is checked for length after parsing.

## Prompt v1 (first round)

<!-- BEGIN:code_prompt_v1 -->
```text
You control the traffic signal of one intersection in a city road network with mixed Indian traffic (two-wheelers, auto-rickshaws, cars, buses, trucks).
At each decision you choose which green phase to show next. Goal: keep vehicles moving and queues short across the whole network, so total travel time is low.
Rules of the signal:
- Choosing the current phase keeps it green. Choosing another phase first shows a 5 s transition in which only free turns move, so switching too often wastes green time.
- A green phase cannot be ended before 15 s and is ended automatically at 60 s.
Data you get for each movement: queue = stopped vehicles waiting at the stop line; moving = vehicles driving towards the stop line; downstream = stopped vehicles on the exit road (a full exit road blocks the movement).
Answer with JSON only: {"phase": <one of the allowed phase ids>, "reason": "<at most 25 words>"}.
```
<!-- END:code_prompt_v1 -->

The v1 user message listed, for every phase, each movement's queue, moving and downstream counts,
the vehicle types per approach, and the neighbours.

## Prompt v2

<!-- BEGIN:code_prompt_v2 -->
```text
You pick the next green phase for one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
queue = stopped vehicles a phase serves; pressure = queue minus stopped vehicles on their exit roads.
Reply JSON: {"phase": <allowed id>, "reason": "<at most 15 words>"}
```
<!-- END:code_prompt_v2 -->

## Prompt v3 (v2 with two lines changed)

<!-- BEGIN:code_prompt_v3 -->
```text
You pick the next green phase for one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
queue = stopped vehicles a phase serves; pressure = vehicles waiting to go minus vehicles already stopped on their exit roads. HIGHER pressure = the phase needs green MORE.
Reply JSON: {"phase": <allowed id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_v3 -->

## Guided prompt (hybrid arm)

<!-- BEGIN:code_prompt_guided -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = stopped vehicles a phase serves minus stopped vehicles on their exit roads; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Reply JSON: {"phase": <offered id>, "reason": "<at most 15 words>"}
```
<!-- END:code_prompt_guided -->

## Guided prompt v3 (hybrid_v3 and the pre-registered guarded arm)

<!-- BEGIN:code_prompt_guided_v3 -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = vehicles waiting to go minus vehicles already stopped on their exit roads; HIGHER pressure = the phase needs green MORE; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Reply JSON: {"phase": <offered id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_guided_v3 -->

In the emergency scenarios one sentence is added:

<!-- BEGIN:code_prompt_guided_v3_amb -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = vehicles waiting to go minus vehicles already stopped on their exit roads; HIGHER pressure = the phase needs green MORE; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Ambulances, if listed, must get through quickly: give green to a phase that serves them.
Reply JSON: {"phase": <offered id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_guided_v3_amb -->

## An example user message

The user message of the guided prompts at a real simulator state:
<!-- BEGIN:code_example_time -->
Indian 2x2 peak with ambulances, seed 2, `intersection_2_2` at t = 265 s, under MaxPressure control up to that moment. MaxPressure ranks phase 2 (S+N straight) first, but an ambulance 70 m from the stop line is served by phases 6, 1, so a phase that serves it is among the options.
<!-- END:code_example_time -->

<!-- BEGIN:code_prompt_user -->
```text
Phase 1 (W+E straight) green for 15 s.
Options, best MaxPressure rank first (phase: pressure, queue):
2 S+N straight: 3, 4
3 W+E cross-turn: 3, 4
6 E only: -2, 3
1 W+E straight (keep current): -4, 0
Ambulances within 150 m:
E straight, 70 m from the stop line; served by phase 6, 1
Neighbours:
W: phase 1 (W+E straight); 9 stopped toward us, 7 on green; 4 stopped on our road to it
S: phase 5 (W only); 0 stopped toward us, 0 on green; 1 stopped on our road to it
```
<!-- END:code_prompt_user -->

## A logged decision

One decision of the pre-registered arm, as logged in `decisions.jsonl` (selected keys): the first
decision of its emergency run (seed 0) in which the LLM's choice differed from MaxPressure's and
served an ambulance. The model's reason still mentions "low pressure", but its choice gives the
ambulance green; because that phase serves a listed ambulance, the guard does not apply. The
guard's pressures are those shown in the prompt, which leave out the free turns.

<!-- BEGIN:code_decision -->
```json
{
 "step": 1980,
 "intersection": "intersection_1_2",
 "current_phase": 5,
 "time_in_phase": 15,
 "allowed": [1, 2, 5, 8],
 "mp_ranking": [1, 2, 8, 4, 6, 7, 5, 3],
 "mp_choice": 1,
 "ambulances": [{"vehicle": "flow_4668_0", "approach": "N", "distance_m": 44.2, "movement": "N cross-turn", "phases": [8, 4]}],
 "latency_s": 1.42,
 "prompt_tokens": 340,
 "server_model": "llama3.2:3b",
 "raw": "{\"phase\": 8, \"reason\": \"Low pressure, serving ambulances within 150m\"}",
 "llm_phase": 8,
 "guard_threshold": 2.4,
 "guard_llm_pressure": 3,
 "guard_override": false,
 "guard_ambulance_exempt": true,
 "phase": 8
}
```
<!-- END:code_decision -->
