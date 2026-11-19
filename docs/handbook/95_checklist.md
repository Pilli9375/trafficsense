# Last-Minute Checklist for Tomorrow Morning

## Before Leaving Home

- [ ] Laptop **fully charged**; charger packed.
- [ ] Deck open-able: `docs/ppt/TrafficSense_Capstone_Final_Review.pptx`, and the **backup PDF**
      `docs/ppt/TrafficSense_Capstone_Final_Review.pdf`, also copied to a USB drive.
- [ ] The report PDF (`docs/report/report.pdf`) on the laptop and the USB drive.
- [ ] This handbook on your phone.

## 30 Minutes Before

- [ ] **Close GPU-heavy apps** (games, video editors, extra browser tabs playing video).
- [ ] **Start the dashboard** (the team's `TrafficSense.bat` launcher if it is on the laptop, or the
      command in Part 6) and open each of the four pages once: Overview, Live Detection, Network
      Replay, Results.
- [ ] On Live Detection, run the **Sample clip** once to check it works (GPU or CPU, either is fine).
- [ ] **Ollama:** not needed for the dashboard. If it is running, `ollama ps` shows whether a model
      holds the GPU; `ollama stop llama3.2:3b` frees it.
- [ ] **Open the PPTX** in presenter view so the speaker notes are visible.
- [ ] Browser zoom at 100%; notifications off; the screen does not sleep.

## Time Plan (About 10 Minutes)

| Minutes | Part | Speaker |
|:--|:----------------------------|:--|
| 0:00–1:30 | Slides 1–3: title, outline, overview | Akul |
| 1:30–2:30 | Slide 4: problem; slides 5–6: objectives, related work | Bhargav, Abhishek |
| 2:30–4:00 | Slides 7–10: improvements, architecture, modules, tools | Akul, Amit, Bhargav |
| 4:00–5:00 | Slides 11–12: data and parameters | Abhishek |
| 5:00–7:00 | Slides 13–15: results (main, ambulances and camera, detector) | Akul, Bhargav, Amit |
| 7:00–8:00 | Slides 16–18: findings, limitations, bibliography, thank you | Abhishek, Amit |
| 8:00–10:00 | Short demo: Overview, Network Replay, one Results tab | Amit, Akul |

If the panel asks for a longer demo, use the 5 to 7 minute order in Part 6.

## Quiz Yourself

Cover the answers (in brackets) and test each other.

1. Was any real signal controlled? (No. Simulation only.)
2. What is the base paper? (CoLLMLight, ICLR 2026.)
3. Which simulator? (CityFlow, validated against CoLLMLight's code.)
4. Which model was selected, and how? (`llama3.2:3b`, guarded, by the pre-registered benchmark rule.)
5. What does the guard do? (Accepts the LLM's phase only within 20<!--=cfg.guard.margin-->% of the
   top pressure.)
6. Main result? (Matches MaxPressure, +0.5<!--=f.peak.llm.vs_mp-->% to +0.9<!--=f.off.llm.vs_mp-->%,
   does not beat it.)
7. Why so close? (The guard replaces most of the model's answers.)
8. Ambulance numbers? (130.1<!--=e.mp.amb--> s → 88.9<!--=e.llm.amb--> s; preemption
   81.2<!--=e.pre.amb--> s.)
9. Does other traffic pay for ambulance priority? (No measurable cost: within seed spread.)
10. Detector score? (mAP50 0.563<!--=d.test.map50-->, mAP50-95 0.375<!--=d.test.map5095-->.)
11. Camera-error cost for MaxPressure, junction level? (+4.8<!--=c.off.mp.junction.pct-->% off-peak,
    +2.3<!--=c.peak.mp.junction.pct-->% peak.)
12. Why is Webster unaffected by camera errors? (It never reads counts.)
13. Which camera error hurts most? (False detections.)
14. What is the camera caveat? (Dash-camera images: a proxy for a junction camera.)
15. What is exploratory? (Prompt v3 fix, the gemma4 arm, the model-size study, the camera
    decomposition.)
16. How many seeds? (Three; five with ambulances. No significance test.)
17. Peak and off-peak demand? (4750<!--=cal.peak--> and 2375<!--=cal.offpeak--> veh/h.)
18. What is ATT? (Average travel time, including waiting to enter the network.)
19. What does the dashboard read? (Only the result files; a source chip on every number.)
20. Where is the code? (<https://github.com/Pilli9375/trafficsense>.)
21. What do you say when you do not know? ("We did not test that.")
