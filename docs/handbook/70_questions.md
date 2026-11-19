# Likely Questions

Short, plain answers. Practise saying them aloud. The answers only use what is in the report, the
deck and the dashboard.

## About the Idea

1. **What is TrafficSense in one line?** One small local LLM agent at each junction chooses the
   next signal phase, guarded by MaxPressure, tested in the CityFlow simulator on an Indian-style
   network.

2. **Why use an LLM at all?** An LLM can be told things in words, such as "an ambulance is
   approaching" or what its neighbours are doing, and it can explain its choice in a short reason.
   A classical rule cannot use that kind of extra context.

3. **Why not just use MaxPressure?** For routine traffic, MaxPressure is just as good, and that is
   our honest finding. The LLM adds value only where it has information MaxPressure lacks, such as
   ambulances. So we suggest the LLM as a safe layer *on top of* MaxPressure, not as its
   replacement.

4. **Why a small model?** We wanted something that runs locally on a cheap GPU, with no internet
   and no paid service, as a junction computer might. Our laptop's GTX 1650 has 4 GB of memory, so
   models of 3–4 B parameters were the limit (`gemma3:4b` did not even fit).

5. **Why not a big hosted model like ChatGPT?** Prompts would leave the machine and need internet
   at every junction. In the exploratory model-size study, even a hosted
   550<!--=m.size.nemo--> B model only brought the controller back to MaxPressure's level; it chose
   the highest-pressure option in 99<!--=m.peak.nemo.follows-->% of its calls, so it nearly copied
   MaxPressure.

6. **What is your base paper and how do you differ?** CoLLMLight (ICLR 2026). We take its
   one-agent-per-junction structure and neighbour cooperation. We differ: no fine-tuning, small
   local models, tuned baselines, a guard, ambulances in the prompt, and real camera errors.

7. **Does your result contradict CoLLMLight?** No. Our results neither confirm nor contradict it,
   because the settings differ: it fine-tunes its model and uses a different architecture and metric
   definitions, and its FixedTime baseline does not serve north–south traffic.

8. **What bug did you find in CoLLMLight's code?** Its fixed-time agent computes the next phase so
   that it alternates only between the two east–west phases: north–south traffic never gets a
   green. We used only our own, correct fixed-time controllers.

## About the Method

9. **How do you know your simulator setup is correct?** We validated it against the CoLLMLight
   authors' own code: driven the same way, throughput, queue and waiting time were identical on all
   three of their datasets.

10. **What is pressure?** For a phase: vehicles waiting on the roads it would serve, minus vehicles
    queued on the roads they would drive into. High pressure means the phase needs green more.

11. **What does the guard do exactly?** It applies the LLM's choice only if that phase's pressure
    is within 20<!--=cfg.guard.margin-->% of the top pressure. Otherwise MaxPressure's choice is
    applied and the override is counted.

12. **Is the guard not cheating, since it makes the LLM act like MaxPressure?** We say exactly that
    in the report: the guard made the LLM safe, not useful. It is part of the pre-registered design,
    and we report how often it intervened.

13. **Why pre-registration?** So that we could not tune the plan after seeing the results. We
    wrote the plan and the decision rule in git first. The rule even sent the selected controller
    to the full experiments if it was worse than MaxPressure.

14. **What exactly is exploratory?** Four things: the prompt v3 fix (post-hoc), the gemma4 arm, the
    model-size study, and the camera-error decomposition. All are labelled wherever they appear.

15. **Why only three seeds?** LLM runs are slow on our GPU (the gemma4 arm took
    3.2<!--=l.peak.gem.wall_h--> hours for an hour of traffic over three seeds). Three seeds are few,
    so we did not claim small differences, and no significance test was run.

16. **Why is the decision interval 5 seconds?** A pre-registered rule: the shortest multiple of the
    5 s transition that fits a full round of four decisions at the model's 95th-percentile latency.

17. **How was the model chosen?** A pre-registered benchmark on 600<!--=b.steps--> s of peak
    traffic: eligible if fewer than 2<!--=b.rule.fail_pct-->% of calls failed and the 95th-percentile
    latency was under 3<!--=b.rule.p95_s--> s; then the lowest mean queue. It selected the guarded
    controller with `llama3.2:3b`.

18. **What happens if the LLM gives a bad answer or the server is down?** The answer is checked;
    a failure is counted by type and, in the hybrid controllers, MaxPressure's choice is applied and
    reported. Our rule is "fail loudly": nothing is silently replaced. The pre-registered arm never
    failed a call off-peak or at peak.

19. **Is the LLM's answer repeatable?** Temperature 0 and a fixed seed make it as predictable as
    possible, but a GPU is not bit-for-bit repeatable. So every decision is logged, and runs can be
    replayed exactly from the log.

20. **How did you set the traffic demand?** A pre-registered rule based on when the network stops
    draining: peak 4750<!--=cal.peak--> veh/h, off-peak 2375<!--=cal.offpeak--> veh/h.

## About the Results

21. **What is your main result?** The pre-registered LLM controller matches MaxPressure, within
    0.5<!--=f.peak.llm.vs_mp-->–0.9<!--=f.off.llm.vs_mp-->% in average travel time, but does not
    beat it.

22. **Why does it not beat MaxPressure?** Three reasons from the report. An LLM that reads pressure
    correctly becomes MaxPressure. Small models misread pressure. And the guard turns a poor model
    into MaxPressure with a little noise.

23. **What does the ambulance result really mean?** Told where ambulances are, the LLM cut their
    mean travel time by 31.7<!--=e.llm.amb_cut_vs_mp-->%, mostly by removing time stopped at red,
    with no measurable cost to other traffic. A simple preemption rule was still slightly better
    (81.2<!--=e.pre.amb--> s against 88.9<!--=e.llm.amb--> s). So the LLM's advantage is
    flexibility, not performance, and we tested only ambulances.

24. **Is part of the ambulance benefit "by design"?** Yes, and we say so: a phase serving a listed
    ambulance is always offered and is exempt from the guard.

25. **What does the camera-error study mean?** Adaptive control is only as good as its counts.
    With our detector's errors, count-based controllers lost a few percent, and at peak MaxPressure
    fell behind the Webster plan (118.2<!--=c.peak.mp.junction.att--> s against
    116.3<!--=c.peak.web.junction.att--> s). False detections hurt more than misses.

26. **Why do false detections hurt more than misses?** Missing vehicles evenly shrinks every
    phase's pressure, so the ranking stays the same on average. A phantom vehicle adds pressure where
    there is none, so it can pull the green to the wrong road. For signal control, precision matters
    more than recall.

27. **What is the caveat of the camera study?** The errors are those of our detector on
    dash-camera images, not a pole camera at a junction. They are a measured proxy.

28. **Is gemma4 better?** It was faster than MaxPressure at peak on all three seeds
    (−1.5<!--=f.peak.gem.vs_mp-->%), but slower off-peak (+2.7<!--=f.off.gem.vs_mp-->%) and too slow
    for real time on our GPU. It is exploratory: a lead, not a result. We have not identified why.

29. **What did the model-size study find?** Exploratory: without the guard, the 3B models make the
    hybrid much worse (+51.0<!--=m.peak.qwen.vs_mp-->% and +81.4<!--=m.peak.llama3b.vs_mp-->% at
    peak); larger models only bring it back to MaxPressure's level.

30. **Why is FixedTime so bad at peak?** A naive 30<!--=cfg.ft.green--> s plan cannot keep up:
    about 308<!--=i.peak.fixedtime.backlog--> vehicles are still waiting to enter at the end of the
    hour.

31. **How good is the detector?** mAP50 0.563<!--=d.test.map50--> on held-out drives. High
    precision, moderate recall: it undercounts, mostly small distant objects at 640 pixels.

32. **Which classes are hardest?** Bicycle and person (mAP50 0.339<!--=d.test.bicycle.map50--> and
    0.444<!--=d.test.person.map50-->): they are small and, for bicycles, rare.

## About Reality and the Future

33. **Is it tested on real roads?** No. It is a simulation study. No real signal was controlled.

34. **How could it be deployed?** First in shadow mode beside an existing controller, only logging
    what it would do. A deployment would need cameras on every approach (with new images to retrain
    the detector), a GPU at the junction or in a control centre, an interface to the existing
    signal controller with a safe fallback to its fixed plan, links between neighbouring junctions,
    and ambulance positions from GPS or V2X. We did not price any of it.

35. **Is it safe?** In simulation, the guard keeps every applied choice close to MaxPressure, and
    the wrapper always inserts the transition and enforces the green limits. Real-world safety was
    not tested.

36. **What would you do next?** Agents with memory and tools, fine-tuning small models, real
    junction-camera footage, larger networks and real demand, faster inference, and field testing in
    shadow mode.

37. **What did it cost?** Nothing was bought. All software is free and open source or free of
    charge; the dataset and model weights are free for research under their own terms; the laptops
    were our own.

## About the Team and the Work

38. **What did each member do?** From the report's team table: **Bhargav** (computer vision and
    machine learning lead): chose YOLOv8n and set up its training on the 4 GB GPU, mapped IDD's labels
    to our seven classes, built the inference pipeline, and ran the detector evaluation behind the
    camera error model. **Akul** (system architect and multi-agent lead): the overall architecture,
    the cooperative LLM controller and its guard, the prompts and structured output, CityFlow
    integration, the Indian 2x2 network and flows, and ambulance priority. **Amit** (frontend and
    dashboard lead): the Streamlit dashboard and its four pages, the Live Detection and Network
    Replay views, reading only from `outputs/` with a source chip on every number. **Abhishek**
    (data engineering and integration lead): dataset acquisition (CoLLMLight's networks and flows,
    and IDD converted to YOLO format with drive-level splits), integration and configuration, the
    pytest suite, README, git and GitHub, and the environment.

39. **Did you use AI to write the code?** Yes, and the report says so: "The project was developed
    with the help of an AI coding assistant (Claude Code), working under the team's direction: the
    team decided what to build and how to evaluate it, reviewed the code and the text, ran the
    experiments and checked the results, and is responsible for all of the work presented in this
    report."

40. **How can someone reproduce your results?** Clone <https://github.com/Pilli9375/trafficsense>,
    follow the README (`pip install -e ".[dev]" -c requirements-lock.txt`, then `pytest -q`), run
    `python scripts/run_full_experiments.py`, and check every number with
    `python scripts/make_report.py --check`. A fresh clone reproduced all
    42<!--=r.det_runs_identical--> deterministic runs exactly, and a short LLM run repeated all
    121<!--=r.llm_identical_answers--> answers. The IDD dataset, the detector weights and the API key
    are not in the repository.

41. **How do you know the numbers in your report are right?** Every number is tied to a result
    file and checked by a script; the dashboard has a test that fails if any shown number is not in
    the files it read; every run records its git commit, model, seed and settings.

42. **Why are there two laptops in the report?** All experiments ran on the project laptop. A second
    laptop was used only to check that the setup can be reproduced from the README.

43. **What is the licence issue with YOLOv8?** Ultralytics YOLOv8 is AGPL-3.0, which requires
    sharing the source of a networked application that uses it. The model weights and IDD are not
    redistributed.

44. **What was the hardest part?** One clear lesson from the report: getting small models to read
    pressure the right way. They preferred low pressure, and prompting fixed only the larger model.
