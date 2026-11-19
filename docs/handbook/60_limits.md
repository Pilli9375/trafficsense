# Limitations and Honest Answers

A limitation said calmly by us sounds like good science. The same limitation found by the panel
sounds like hiding. So say them first. Each item: what we did not do, and how to say it.

| What we did not do | How to say it calmly |
|:--------------------------------|:------------------------------------------------------|
| No real signal was controlled; everything is a simulation | "This is a simulation study. A real deployment would start in shadow mode, only logging what the agent would do." |
| No junction-camera footage; IDD is dash-camera images | "Our camera errors are a measured proxy. The junction and crowded levels bracket a range rather than predict one value." |
| Only three seeds (five with ambulances), no significance test | "Three seeds are few, so we only call a difference a result when it is consistent on every seed; small differences are within seed noise." |
| CityFlow is lane-based; no lane-free driving | "We modelled the Indian vehicle mix, not Indian driving behaviour such as two-wheelers filtering between cars." |
| Synthetic demand on a 2x2 grid | "The Indian demand is generated and calibrated against measured capacity, not counted at a real junction. Jinan gives one real-world flow." |
| No fine-tuning (CoLLMLight fine-tunes) | "We used models as released; our question was what an off-the-shelf local model can do. Fine-tuning is future work." |
| The LLM does not beat MaxPressure | "It matches it. The guard made it safe, not better. Its value is where it has information MaxPressure lacks." |
| gemma4 arm and model-size study are exploratory | "They were added after the plan was fixed; we label them exploratory. They are leads for future work." |
| LLM runs are not bit-for-bit repeatable on a GPU | "Every decision is logged, and every run can be replayed exactly from its log." |
| The hosted 550 B model's runs were throttled | "Its API throttled the account; calls that ran out of retries fell back to MaxPressure and were counted as failures. Its prompts leave the machine, so it is not an on-device option." |
| Only the ambulance case of "extra context" was tested | "We showed it for ambulances only. Road closures or school zones are ideas, not results." |
| No cost of a real deployment | "We listed what a deployment would need but did not price it; any price would be invented." |
| Camera layer: independent snapshots, no occlusion, no ambulance detection by camera | "Each snapshot is independent, which is the worst case; tracking over time should help. Ambulance positions are assumed to come from GPS or V2X." |
| The ambulance metric assumes nobody yields | "In CityFlow nobody pulls over, so we measure only what the signal can do." |

## The Magic Sentence

When you do not know, or when the question is about something outside the project, say:

> **"We did not test that."** Then, if you can, add what we *did* test: "What we tested is ...".

Never guess a number. Never claim the project shows something it does not. It is always better to
say "that is a good question for future work" than to bluff. The panel examines honesty as much as
results.

## Words to Avoid, and What to Say Instead

| Avoid | Say instead |
|:--|:--|
| "Our AI beats MaxPressure" | "Our controller matches MaxPressure; it does not beat it" |
| "It reduces traffic in Indian cities" | "In simulation, on our 2x2 network" |
| "The detector is 56 percent accurate" | "mAP50 of 0.563<!--=d.test.map50-->" |
| "gemma4 is better" | "The exploratory gemma4 arm was faster at peak; it is a lead, not a result" |
| "Significant improvement" | "Consistent on every seed" (or "within seed noise") |
| "Real camera at a junction" | "Dash-camera images as a proxy" |
| "The LLM is better for ambulances than preemption" | "Close to preemption; preemption is still slightly better" |
