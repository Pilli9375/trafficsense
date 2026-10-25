# System Design {#sec:design}

This chapter describes what TrafficSense is made of and how a decision is made at one
intersection. The design follows from three rules the project set itself before any code was
written, because the results will be examined and must be trusted:

1. **No invented data in the results path.** Every number in a result file is measured from the
   simulator or from a real model's answer. Test doubles exist only inside the test suite.
2. **Fail loudly.** If the LLM server is down, an answer cannot be parsed, a file is missing or
   a setting is invalid, the run stops with an error or, where a fallback is part of the design,
   the fallback is counted and reported. Nothing silently falls back to a default.
3. **Every result records where it came from**: controller, model as reported by the server,
   seed, scenario, run length, git commit and time, and for LLM runs the number of calls,
   failures and the latency.

## Architecture {#sec:architecture}

@fig:architecture shows the components. The **CityFlow engine** simulates every vehicle and is
the only place where metrics are measured. An **environment wrapper** around it parses the road
network, enforces signal timing and computes metrics. Controllers do not read the engine
directly; they read lane counts through an **observation layer**, which returns either the exact
counts or, in the camera experiment, counts degraded by the detector's measured errors
(@sec:camera-design). A **controller** decides the next phase for each intersection. The LLM
controllers are built on top of **MaxPressure's ranking** of phases, ask an **LLM agent** per
intersection, and pass its answer through a **guard** and the timing rules. Each run writes its
results to `outputs/`, from which the dashboard, the documentation and this report are
generated.

![System architecture. The simulator holds the exact state; controllers see it only through the
observation layer, which can add camera errors measured offline. Ambulance positions reach the
agent through a separate channel and are never noised.](figures/architecture.png){#fig:architecture width=100%}

The code is a Python package, `trafficsense`, with sub-packages for the simulator wrapper
(`sim`), the controllers (`control`), the LLM clients and prompts (`llm`), perception
(`perception`), the dashboard (`dashboard`) and the report tooling (`report`). Settings and paths
come from YAML files in `configs/`; no path is hard-coded.

## Simulation layer {#sec:sim-layer}

**Road network and phases.** The wrapper reads a CityFlow road network and builds, for each
intersection, its incoming lanes, the movements (straight, left, right) and which movements each
phase serves. In the CoLLMLight networks and in ours, phase 0 is a 5 s transition phase in which
only the kerb-side free turn may move, and phases 1–8 are green phases. The transition phase is
detected from the network, not assumed.

**Signal timing.** CityFlow switches a signal instantly when told to, so the wrapper inserts the
transition phase on every change and enforces a minimum green of
10<!--=cfg.signal.min_green--> s and a maximum green of 60<!--=cfg.signal.max_green--> s for
every controller. The tuned MaxPressure and all LLM controllers use their own, longer minimum
green of 15<!--=cfg.mp.min_green--> s (@sec:baselines).

**Metrics** are measured from the engine at every second (@sec:metrics).

## The multi-agent decision loop {#sec:loop}

Each signalised intersection is controlled by its own agent. Every
5<!--=cfg.mp.interval--> s of simulated time, every intersection whose current green has lasted
at least the minimum green is asked for its next phase. One decision goes through five steps
(@fig:loop):

![One decision of one agent. The simulator is paused during the LLM call, so slow answers cost
wall-clock time, not simulated traffic.](figures/agent_loop.png){#fig:loop width=100%}

1. **Observe.** The agent receives a short text describing its own intersection and its
   neighbours (@sec:cooperation). For each phase it may choose, it is given the phase's
   **pressure** (stopped vehicles the phase would serve minus stopped vehicles on their exit
   roads) and its **queue** (stopped vehicles it would serve), so that it needs no arithmetic.
   The pre-registered controller's prompts averaged
   277<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Prompt tokens--> tokens
   in the benchmark.
2. **Reason.** The prompt is sent to a local model through Ollama's native `/api/chat` endpoint
   with a JSON schema that restricts the answer to the allowed phase numbers and a short
   reason. Sampling uses temperature 0 and a fixed seed, a context of
   2048<!--=cfg.llm.num_ctx--> tokens, at most 128<!--=cfg.llm.num_predict--> answer tokens and a
   timeout of 60<!--=cfg.llm.timeout_s--> s; the model's "thinking" mode is switched off.
3. **Act.** The answer is parsed and checked: the phase must be one of those offered and the
   reason must be at most 15<!--=code.reason_words.guided_v3--> words. A failure (timeout, invalid JSON, a phase not offered, a
   reason that is too long) is counted by type. In the hybrid controllers, a failed call applies
   MaxPressure's choice for that decision and is reported as such.
4. **Enforce.** The chosen phase is requested from the wrapper, which inserts the transition and
   applies the green limits.
5. **Log.** The decision is written to the run's `decisions.jsonl`: the state the agent saw,
   MaxPressure's ranking and pressures, the raw answer, its latency and token counts, whether
   the guard intervened, and the phase applied.

All agents share one GPU, so the calls of one decision round run one after another. The
pre-registered selection rule therefore sets the decision interval to the shortest multiple of
the transition time that is at least the model's 95th-percentile latency times the number of
intersections (@sec:llm-selection). The simulator waits during calls; slow models make a run
take longer in wall-clock time but do not change the simulated traffic.

## Cooperation through neighbour information {#sec:cooperation}

Following CoLLMLight, cooperation is through the prompt. For each neighbouring intersection,
the agent is told the neighbour's current phase, how many vehicles are stopped on the
neighbour's approaches heading towards this intersection and how many of those have green, and
how many vehicles are stopped on this intersection's road into the neighbour. The agent can thus
see a platoon about to be released towards it, or a neighbour whose approach from this
intersection is full. An example prompt, rendered by the controller's own code from a real
simulator state, is in Appendix B.

## Controller variants {#sec:arms}

The project compared six LLM controller designs ("arms"). They differ in how much the LLM decides
and in the prompt version (Appendix B).

::: {#tbl:arms}
| Arm | Controller | What the LLM chooses | Prompt |
|:-------------|:--------------------|:------------------------|:--------------------------------|
| v1 | `llm_v1` | any green phase | v1: per-movement counts, vehicle types, neighbours |
| v2 | `llm_cooperative` | any green phase | v2: shorter; pressure and queue per phase |
| hybrid | `llm_guided_mp` | MaxPressure's top 2 or keep current | guided |
| v3 | `llm_v3` | any green phase | v3 = v2 with two lines fixed |
| hybrid_v3 | `llm_guided_mp_v3` | MaxPressure's top 2 or keep current | guided_v3 |
| guarded_v3 | `llm_guarded_mp` | as hybrid_v3, then the guard | guided_v3 |

: The LLM controller designs. The pre-registered final design round compared the last three.
:::

**Plain arms** (v1, v2, v3) let the LLM choose any green phase. **Hybrid arms** let MaxPressure
propose and the LLM decide: MaxPressure ranks the phases by pressure, and the LLM is offered
MaxPressure's two best phases and keeping the current phase. The **guarded arm** adds a check:
the LLM's choice is applied only if its pressure is close enough to the best phase's,

$$P(\text{LLM's phase}) \ge P_{\text{top}} - (1 - r)\,\lvert P_{\text{top}} \rvert,$$

with $r$ = 0.8<!--=cfg.guard.ratio--> in the configuration, i.e. within
20<!--=cfg.guard.margin-->% of the top pressure. The absolute value keeps the top phase
acceptable when every pressure is negative. Otherwise MaxPressure's choice is applied and the
override is counted. The guard was added because the small models in the earlier rounds
preferred low-pressure phases (@sec:res-bench); it limits how much harm such a choice can do.

## Ambulance handling {#sec:ambulance-design}

In the emergency scenarios, ambulances are part of the traffic (@sec:emergency-scenario). An
ambulance on an incoming lane within 150<!--=cfg.amb.range--> m of the stop line is detected.
For the hybrid and guarded arms:

* the prompt lists each detected ambulance with its movement, its distance to the stop line and
  the phases that serve it, and the system prompt adds one sentence: "Ambulances, if listed, must
  get through quickly: give green to a phase that serves them.";
* if no offered phase serves the ambulance, the best-ranked phase that does is added to the
  options;
* in the guarded arm, a phase that serves a listed ambulance is exempt from the guard, so the
  guard cannot block priority.

The non-LLM competitor, `preemption_mp`, is MaxPressure with a rule: when an ambulance is
detected in the same way, the phase that serves it with the highest pressure is given green,
within the same minimum and maximum green. Ambulance positions are assumed to come from a
separate channel (GPS or V2X) and are not passed through the camera-noise layer.

## Camera-noise observation layer {#sec:camera-design}

To test controllers on realistic counts without changing the traffic, the observation layer can
replace the engine's lane counts with noisy ones. Every time a controller observes, a fresh
snapshot is drawn for the whole network: each vehicle is detected with a class-dependent
probability, a detected vehicle may be given another class (a vehicle labelled as a pedestrian
is lost from the count), and each road gains a random number of phantom stopped vehicles. All
the rates come from the detector's measured errors (@sec:error-model). The simulator itself
stays exact, so every metric is still measured from the true traffic.

## Dashboard {#sec:dashboard}

A Streamlit dashboard presents the results. It reads only files in `outputs/` (and the detector
weights), and every chart and number carries a source chip naming the file it came from. Its
four pages show the headline result (@fig:screen-overview), live detection on video with the
trained detector, a side-by-side replay of two controllers on the same traffic
(@fig:screen-replay) and the result tables. A test renders every page and fails if any number
shown does not appear in the files the page read.

![Dashboard, Overview page. The headline is the pre-registered arm's ambulance
result; exploratory numbers are labelled as such.](figures/screen_overview.png){#fig:screen-overview width=92%}

![Dashboard, Network Replay page: MaxPressure (left) and the pre-registered LLM arm (right) on
the same traffic, one ambulance's trip. Replays re-drive the simulator with each run's logged
decisions and are kept only if they reproduce the run's metrics exactly.](figures/screen_replay.png){#fig:screen-replay width=92%}
