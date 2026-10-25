# Discussion {#sec:discussion}

## Why the LLM agents match MaxPressure but do not beat it {#sec:disc-why}

Three observations together explain the main result.

**First, an LLM that reads pressure correctly becomes MaxPressure.** In the hybrid controllers the
LLM is shown each option's pressure and queue, the same information MaxPressure uses. The largest
model tested, the hosted Nemotron 3 Ultra, chose the highest-pressure option in
99<!--=m.peak.nemo.follows-->% of its calls, and its ATT is within seed noise of MaxPressure's
(@sec:res-size). This is the expected end point: for steady demand on a small grid, serving the
largest pressure is close to the best a one-step rule can do, and the extra information in the
prompt, the neighbours' queues, rarely points to a better phase. To beat MaxPressure an agent
must use information MaxPressure does not have, or plan over more than one decision. Neither was
asked of the agents in the pre-registered design.

**Second, small models misread the task.** With prompts v2 and guided, the 3 B models treated low
pressure as good and kept the current phase most of the time, and their reasons said so in words
(@sec:res-bench). The v3 fix, which states which direction of pressure is better, changed
`gemma4:e4b` but not the 3 B models. A model of this size follows the surface of the prompt
("keep", "low queue") more than its stated rule. Without a guard their choices are applied and
the controller is far worse than MaxPressure (@tbl:model-size).

**Third, the guard converts a poor model into MaxPressure with noise.** The pre-registered
controller's answers differ from MaxPressure's in about nine of ten calls, but the guard replaces
most of them, and the applied phase differs in about one in ten. What remains are choices within
20<!--=cfg.guard.margin-->% of the top pressure. Off-peak, when queues are short, such a choice
gives green to a slightly smaller queue and costs a little; this is the small, consistent
deficit seen on every off-peak seed. The guard therefore made the LLM safe to deploy, not useful.

The exploratory `gemma4:e4b` arm follows pressure in most calls and departs from MaxPressure in
about one call in five at peak, where it was faster on every seed. We have not identified the
mechanism. One hypothesis is that its departures more often keep a phase that is still discharging
a long queue, avoiding a transition; this was not tested, and with three seeds the gain itself
needs confirmation.

## Why the LLM agents help ambulances {#sec:disc-amb}

The ambulance experiment is the one case where the agent has information MaxPressure lacks:
the prompt lists each approaching ambulance, its distance and the phases that serve it. A
one-sentence instruction was enough for the pre-registered arm to cut ambulance travel time by
31.7<!--=e.llm.amb_cut_vs_mp-->% compared with MaxPressure, mostly by removing time stopped at a
red. Two design choices helped: the phase that serves the ambulance is always among the options,
and it is exempt from the guard. Normal traffic was not measurably slowed, because ambulances are
rare and each priority decision affects one intersection for a short time.

A hand-written preemption rule did slightly better. This is the honest comparison for a
deployment decision: for a single, well-defined rule like "give green to the ambulance", a rule
is simpler, faster and verifiable. The case for an LLM agent is flexibility, not performance. The
same mechanism, a sentence in the system prompt and a line in the observation, can carry rules
that are awkward to hard-code: a road closure, a school zone at certain hours, a police
instruction, priority for a bus that is late. This project tested only the ambulance case.

## What the camera study means {#sec:disc-camera}

Adaptive control is only as good as its counts. With counts degraded by the errors of a real
detector, every count-based controller lost a few percent of travel time, and at peak its
advantage over a well-timed fixed plan, already small with exact counts, disappeared. Three
lessons follow for a deployment.

1. **False detections hurt more than misses.** Missing vehicles uniformly scales every pressure
   down and barely changes the ranking. A phantom vehicle adds pressure where there is none and
   changes the decision directly. For signal control a detector's precision matters more than
   its recall, the opposite of the usual emphasis, and temporal smoothing or tracking that rejects
   one-frame detections should help (each snapshot here is independent, the worst case).
2. **Camera placement matters.** The junction level, which assumes queued vehicles are close
   enough to be medium or large in the image, costs about half as much as the crowded / far
   level.
3. **A fixed plan is a robust fallback.** Webster's plan does not depend on counts at all. Where
   detection is unreliable, at night or in heavy rain, a controller should fall back to a good
   fixed plan rather than act on bad counts.

These conclusions rest on a proxy: the detector's errors on dash-camera images. The same detector
on a pole-mounted camera could be better (closer, less occlusion) or worse (unfamiliar viewpoint).

## Threats to validity {#sec:threats}

**Internal validity.** Three seeds per scenario (five with ambulances) are few, and no significance
test was pre-registered; differences of one or two percent are within seed noise and are reported
as such. LLM runs are not bit-for-bit repeatable on the GPU, although every decision is logged
and replayable. Prompt v3 was a post-hoc fix, the `gemma4:e4b` arm and the model-size study were
added after the plans were fixed, and the camera decomposition was post-hoc; all are labelled. The
hosted model's runs were affected by heavy API throttling, which turned some decisions into
MaxPressure fallbacks.

**Construct validity.** ATT counts time spent waiting to enter the network, which penalises
controllers that block entries; this is intended but makes ATT differ from definitions used
elsewhere, including CoLLMLight's (@sec:validation). The ambulance metric assumes that nobody yields
and that ambulances cannot overtake, so it measures only what the signal can do. The camera layer
draws independent snapshots and does not model occlusion between lanes or ambulance detection.

**External validity.** CityFlow is lane-based and cannot represent lane-free Indian driving
(@sec:sim-limits). The Indian network is a 2 × 2 grid with synthetic, steady demand; its vehicle
mix comes from one city in one year; and the turning shares are assumptions. Jinan provides one
real-world flow. Latencies are specific to a GTX 1650. The results show what a small local
model does on this network; they do not show how a deployed system would perform on a real
junction.

## Relation to the base paper {#sec:disc-collmlight}

CoLLMLight reports that cooperative LLM agents outperform existing methods. Our results neither
confirm nor contradict that claim, because the settings differ in ways that matter: CoLLMLight
fine-tunes its model in several stages and uses an asynchronous reasoning architecture, while we
used small models as released; we compared against MaxPressure and Webster tuned on the test
networks; and we found that CoLLMLight's own fixed-time baseline does not serve north–south
traffic. Its metric definitions also differ from CityFlow's, so numbers cannot be compared
directly. What our results do show is that, without fine-tuning, a 3–4 B model is not enough to
improve on a tuned MaxPressure, and that the clearest value of an LLM agent appears when it is
given information a classical controller cannot use.
