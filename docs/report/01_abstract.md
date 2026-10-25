# Abstract {.unnumbered}

Signalised junctions in Indian cities carry a mixed stream of two-wheelers, auto-rickshaws,
cars, buses and trucks, and many still run fixed signal plans. Large language models (LLMs) have
recently been proposed as traffic-signal agents that can explain their choices and use extra
information, such as an approaching ambulance. This project asks whether such agents, running a
small model on a laptop GPU, can control signals as well as the best classical method, and how
they cope with vehicle counts from a real camera detector instead of exact simulator counts.

We built TrafficSense on the CityFlow simulator and validated it against the CoLLMLight authors'
own code, whose baseline results it reproduces exactly; along the way we found a bug in their
fixed-time baseline. We built a 2x2 network with an Indian vehicle mix, calibrated its demand,
and tuned MaxPressure and a Webster fixed-time plan before any LLM run. The LLM controller, its
selection rule and the experiment plan were fixed in advance (pre-registration).

The selected controller, `llama3.2:3b` guided and guarded by MaxPressure, matched MaxPressure's
average travel time to within 0.5<!--=f.peak.llm.vs_mp-->–0.9<!--=f.off.llm.vs_mp-->% but did not
improve on it. With ambulances listed in its prompt, their mean travel time fell from
130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s, close to rule-based preemption
(81.2<!--=e.pre.amb--> s), at no measurable cost to other traffic. A YOLOv8n detector trained on the
India Driving Dataset reached mAP50 0.563<!--=d.test.map50--> on held-out drives. Feeding its
measured errors into the controllers' counts raised MaxPressure's travel time by
2.3<!--=c.peak.mp.junction.pct-->–4.8<!--=c.off.mp.junction.pct-->%, mainly through false
detections, while the fixed-time plan was unaffected. An exploratory study found that 3 B models
make the guided controller much worse, and larger models only bring it back to MaxPressure's
level. An LLM agent is therefore best used as a safe layer that adds context MaxPressure cannot
use, not as its replacement.

**Keywords:** traffic signal control, large language models, multi-agent systems, MaxPressure,
emergency vehicle priority, YOLOv8, India Driving Dataset, CityFlow, pre-registration.

\newpage
