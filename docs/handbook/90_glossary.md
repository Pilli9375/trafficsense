# A to Z Glossary

**Agent.** A program that observes, decides and acts on its own. We have one agent per junction.

**AGPL-3.0.** The licence of Ultralytics YOLOv8. It requires sharing the source code of a networked
application that uses it.

**Ambulance travel time.** For each signal-relevant ambulance: finish time minus scheduled start.

**API.** A way for one program to call another over a connection, for example a hosted model's
web service.

**Arm.** One controller design in a comparison, like one arm of a medical trial.

**ATT (average travel time).** Our main measure: the average time from a vehicle's scheduled start
to its arrival, including time waiting to enter the network. Lower is better.

**Baseline.** A standard method we compare against: FixedTime, Webster and MaxPressure.

**Benchmark.** A short standard test (600<!--=b.steps--> s of peak traffic) used to pick the model by
a pre-registered rule.

**Bootstrap.** Repeating a calculation many times on random resamples of the data (here, whole
drives) to see how much a result could vary.

**Calibration (of demand).** Choosing the traffic levels by a fixed rule: the network must still
"drain" (empty out) at the end of the hour.

**CityFlow.** The free traffic simulator we used. It moves every vehicle second by second.

**Class.** The type of object a detector reports: car, motorcycle, autorickshaw, bus, truck,
bicycle, person.

**CoLLMLight.** Our base paper (ICLR 2026): cooperative LLM agents, one per junction, sharing
neighbour information.

**COCO.** A large public image dataset. Our detector started from weights trained on it, and we use
its small / medium / large object sizes.

**Confidence threshold.** The minimum score a detection needs to be kept. Ours is
0.3<!--=d.conf-->, frozen on validation data.

**Confusion.** A detector mistake where a real vehicle gets the wrong class.

**Cooperation.** Each agent's prompt includes its neighbours' state.

**Dash camera (dashcam).** A camera mounted in a car. IDD was filmed this way, not from a pole at a
junction.

**Dashboard.** Our Streamlit web page with four pages that shows the results from the files.

**Decision interval.** How often a controller may change the phase: every 5<!--=cfg.mp.interval--> s
(after the minimum green).

**Detector.** An AI that finds objects in an image and draws a box with a class around each.

**Deterministic.** Gives exactly the same result every time it is run with the same input.

**Epoch.** One full pass of training over all the training images.

**Exploratory.** A result added after the plan was fixed. A lead, not proof.

**F1.** A single score that balances precision and recall.

**False detection.** A box where there is no real object (a "phantom" vehicle).

**Fine-tuning.** Extra training of a model on one task. We did not fine-tune.

**FixedTime.** A plan that repeats the same green times; our naive one gives
30<!--=cfg.ft.green--> s per phase.

**Flow file.** The list of vehicles, their start times and routes for one simulated hour.

**GPS.** Satellite positioning. We assume ambulance positions come from GPS or V2X, never from the
camera.

**GPU.** Graphics card. It runs AI models fast. Ours is a GTX 1650 with 4 GB of memory.

**Guard.** Our safety check: the LLM's phase is applied only if its pressure is within
20<!--=cfg.guard.margin-->% of the top; otherwise MaxPressure's choice is applied.

**gemma4:e4b, llama3.2:3b, qwen2.5:3b, llama3.1:8b.** The small local models we tried, by name and
size. `llama3.2:3b` was selected; `gemma4:e4b` is the exploratory arm.

**Git / GitHub.** Git records every change to the code with a date and an identifier (a commit);
GitHub is the website that hosts our repository.

**Hosted model.** A model run by a company on its servers, reached over the internet (here, the
exploratory Nemotron 3 Ultra).

**Hybrid controller.** MaxPressure proposes its two best phases (or keeping the current one) and the
LLM decides among them.

**IDD (India Driving Dataset).** Images of Indian roads with labelled boxes, from IIIT Hyderabad and
Intel. Our detector's training and test data.

**IoU (intersection over union).** How much two boxes overlap: shared area divided by combined area.

**Jinan 3x4.** A 12-junction network with a real-world traffic flow, from CoLLMLight's data.

**JSON.** A simple text format for structured data. The LLM must answer in JSON.

**Junction camera level.** The camera-error level using detection rates of medium and large
objects, as for queued vehicles near a pole camera.

**Latency.** How long one LLM call takes. The 95th percentile is the time within which 95% of
calls finish.

**Lane-based.** A simulator in which vehicles stay in lanes; it cannot show two-wheelers filtering.

**LLM (large language model).** An AI that reads and writes text.

**Loop detector.** A sensor cut into the road surface under a lane that detects vehicles passing.

**mAP50.** Mean average precision when a detection counts as correct at IoU 0.5 or more; from 0 to
1. Ours: 0.563<!--=d.test.map50-->.

**mAP50-95.** The same, averaged over stricter overlap thresholds from 0.5 to 0.95. Ours:
0.375<!--=d.test.map5095-->.

**MaxPressure.** A classical rule: green to the phase with the highest pressure. Our main baseline.

**Maximum / minimum green.** The longest and shortest time a green may last. For MaxPressure and the
LLM arms: 15<!--=cfg.mp.min_green--> s minimum, 60<!--=cfg.signal.max_green--> s maximum.

**Miss.** A real vehicle the detector did not find.

**Multi-agent.** Many agents, here one per junction, working at the same time.

**Observation layer.** The part that gives controllers their counts: exact, or with camera errors.

**Off-peak / peak.** Light and heavy demand: 2375<!--=cal.offpeak--> and 4750<!--=cal.peak--> vehicles
per hour on the Indian network.

**Ollama.** A free program that runs AI models locally on your own computer.

**Paired by seed.** Comparing two controllers on exactly the same traffic (the same seed).

**Parameters (of a model).** The internal numbers of an AI model; "3B" means about three billion.

**Phase.** A set of movements that get green together.

**Precision.** Of the boxes a detector drew, the share that were real.

**Preemption.** A hand-written rule that gives green to the phase serving a detected ambulance.

**Post-hoc.** Done after seeing the results (for example the prompt v3 fix and the camera
decomposition). Always labelled.

**Pre-registration.** Writing down the plan and decision rule before running an experiment, and
saving it in git.

**Pressure.** For a phase: vehicles waiting on the roads it serves minus vehicles queued on the
roads they would enter.

**Prompt.** The text given to an LLM.

**Provenance.** The record of where a result came from: controller, model, seed, scenario, run
length, git commit and time. Every result file stores it.

**Proxy.** A stand-in measurement used when the real one is not available.

**pytest.** The tool that runs our automatic tests.

**Queue length.** The number of waiting vehicles (speed below 0.1<!--=code.stop_speed--> m/s) on a
junction's incoming lanes, averaged over time.

**Recall.** Of the real objects, the share the detector found.

**Repository.** The folder of code, configuration and results kept in git and on GitHub.

**Reinforcement learning (RL).** A way of training an AI by trial and error in a simulator.

**Replay.** Re-driving the simulator with a run's logged decisions to show it second by second.

**SCATS / SCOOT.** Real adaptive city signal systems (Sydney Coordinated Adaptive Traffic System /
Split Cycle Offset Optimisation Technique). Discussed, not tested.

**Seed.** A number that fixes the random choices of a run; each seed gives a different traffic file
on the Indian network.

**Shadow mode.** Running a new controller beside the real one, only logging what it would do.

**Signal-relevant ambulance.** One whose route crosses at least one movement a signal controls.

**Significance test.** A statistical test of whether a difference could be due to chance. We did not
run one.

**Simulation.** A computer model of reality. Nothing in our project happened on a real road.

**Source chip.** The "ⓘ source" button on the dashboard that names the file behind a number.

**Standard deviation (± spread).** How much a result varies between seeds.

**Streamlit.** A Python tool for building data web pages; our dashboard uses it.

**Temperature.** An LLM setting for randomness. At 0 the model always takes its most likely answer.

**sha256.** A fingerprint of a file. The dashboard uses it to check that the detector weights are the
evaluated ones.

**Throughput.** The number of vehicles that finished their trip. Higher is better.

**Time-lapse.** A video made of frames taken far apart in time; our sample clip is one.

**Token.** A word or part of a word, the unit an LLM reads and writes.

**Tracking.** Following the same vehicle across video frames. The Live Detection page does not track;
it counts each frame on its own.

**Transition.** The short yellow / all-red phase between two greens; 5 s in our networks.

**V2X.** Vehicle-to-everything radio communication; one possible source of ambulance positions.

**Validation (of the simulator).** Checking our setup gives the same numbers as the CoLLMLight
authors' code.

**Validation split / test split.** Data used to tune settings, and data used once at the end to
measure the final result.

**Waiting time.** Seconds a vehicle spends nearly stopped, averaged over vehicles.

**Webster's method.** A 1958 textbook method to compute a good fixed-time plan from traffic flows.

**WSL (Windows Subsystem for Linux).** Runs Ubuntu Linux inside Windows; all our code runs there.

**YOLOv8n.** "You Only Look Once", version 8, nano size: a small, fast object detector.
