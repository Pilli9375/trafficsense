# Conclusion and Future Work {#sec:conclusion}

## Conclusion

This project built and evaluated TrafficSense, a multi-agent traffic-signal controller in which
each intersection is run by a local LLM agent that observes its own and its neighbours' state,
reasons and acts, adapted from CoLLMLight to a 4 GB laptop GPU. The objectives set in
@sec:objectives were met as follows.

1. **A validated pipeline.** Our CityFlow environment reproduces the CoLLMLight authors' own
   baseline results when driven the same way (throughput and queue exactly, waiting and travel times
   to within the simulator's run-to-run noise), and the validation exposed a bug in their
   fixed-time baseline.
2. **An Indian test network with documented parameters**, calibrated against measured capacity,
   and **baselines tuned before the comparison**: MaxPressure with a 15<!--=cfg.mp.min_green--> s
   minimum green, and a Webster plan computed from perfect counts.
3. **A pre-registered comparison.** The selected LLM controller, `llama3.2:3b` guided and guarded
   by MaxPressure, performs within 0.5<!--=f.peak.llm.vs_mp-->–0.9<!--=f.off.llm.vs_mp-->% of
   MaxPressure's travel time and runs in real time, but does not improve on it. The reason is
   clear from its decision logs: small models misread pressure, and the guard, which makes them
   safe, also makes them MaxPressure.
4. **A clear benefit for emergency vehicles.** Told about approaching ambulances, the agent cut
   their mean travel time from 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s, close to a
   hand-written preemption rule, without slowing other traffic.
5. **A measured camera-error study.** A YOLOv8n detector trained on IDD reaches mAP50
   0.563<!--=d.test.map50--> on held-out drives. Its measured errors cost count-based controllers a
   few percent of travel time, mostly through false detections, and remove adaptive control's
   small lead over a fixed plan at peak.
6. **A dashboard and a report generated from the data**, with every number checked against the
   result files.

The overall answer to the question in @sec:intro is therefore modest and, we believe, useful: a
small local LLM does not yet beat a well-tuned classical controller on routine traffic, but as a
guarded layer on top of one it is safe, and it adds value where the situation is described in
words rather than in queue counts.

## Future work {#sec:future}

* **Memory and tool-using agents.** The agents here see one snapshot and answer once. An agent that
  remembers its recent decisions and their effects, and can call tools (MaxPressure's ranking, a
  short look-ahead simulation, the queue history of an approach), could plan over several
  decisions, which is where an agent might beat a one-step rule.
* **Fine-tuning small models.** CoLLMLight's training stages (reasoning refinement and policy
  refinement with simulation feedback) were not reproduced. Fine-tuning a 3 B model on decisions
  scored by the simulator may fix the pressure misreading that prompting could not.
* **Real junction camera footage.** Collecting and labelling video from a fixed camera at an Indian
  junction would replace the dash-camera proxy with the true error, and would allow tracking-based
  counting that rejects one-frame false detections.
* **Larger networks and real demand.** Hangzhou and New York networks are available in the same
  format; counts from a real Indian corridor would replace the synthetic demand. A simulator with
  sub-lane movement would represent two-wheeler filtering.
* **Faster inference.** A larger GPU or a smaller, faster model would make the stronger
  `gemma4:e4b`-class controller real-time and allow more seeds for a confirmatory test of its peak
  gain.
* **Field testing.** A first deployment would run the agent in shadow mode beside an existing
  controller, logging what it would have done, before it is allowed to switch a real signal.
  Ambulance positions would come from a GPS or V2X feed, as assumed here.
