# Team contributions: what the team must confirm

Section 1.4 of the report (Table 1.2, "Team contributions") was written from the four role
descriptions the team gave, not from the old individual contribution sheets. Every line in the
table was checked against the current repository: each names a file or feature that exists in
the code at the commit the report was built from. Please read the table and confirm or correct
the points below before submission.

## 1. Who did what cannot be checked from git

The git history has 200+ commits under two author names, "Pilli" and "Naga Adithya", neither of
which is one of the four students' names. So the repository proves that each listed file or
feature **exists**, but not **which student** built it. The assignment of each line to a student
follows the roles the team gave and must be confirmed by the team.

## 2. Lines that follow the roles and need the team's confirmation

All of these exist in the code; the team should confirm the person.

| Student | Line in Table 1.2 | Verified in the repository |
|---|---|---|
| C Bhargav Kumar | Chose YOLOv8n and set up its GPU training (probe run, mixed precision off) | `scripts/train_detector.py` (`--probe`), `configs/default.yaml` `amp: false` |
| C Bhargav Kumar | IDD class mapping to seven classes | `src/trafficsense/perception/idd.py` (`rider`, `vehicle fallback` dropped) |
| C Bhargav Kumar | Inference pipeline | `src/trafficsense/perception/detector.py` |
| C Bhargav Kumar | Detector evaluation feeding the camera error model | `scripts/eval_detector.py`, `outputs/perception/error_model.json` |
| Achalla Akul Lakhan | Overall architecture | package layout `src/trafficsense/{sim,control,llm,perception,dashboard}` |
| Achalla Akul Lakhan | Cooperative LLM controller and guard | `src/trafficsense/control/llm.py`, `control/guided.py` |
| Achalla Akul Lakhan | Prompts and JSON-schema structured output | `src/trafficsense/llm/prompt.py`, `llm/client.py` |
| Achalla Akul Lakhan | CityFlow integration, Indian 2x2 network and flows | `sim/env.py`, `sim/roadnet.py`, `scripts/generate_indian_roadnet.py`, `scripts/generate_indian_flow.py` |
| Achalla Akul Lakhan | Ambulance priority | `sim/emergency.py`, `control/preemption.py` |
| Darsi Amit | Streamlit dashboard, four pages | `dashboard/app.py`, `dashboard/screens/` |
| Darsi Amit | Theme and charts | `dashboard/theme.py`, `dashboard/ui.py`, `dashboard/views/results.py` |
| Darsi Amit | Live Detection and Network Replay views | `dashboard/views/detection.py`, `dashboard/views/replay.py` |
| Darsi Amit | Reads only `outputs/`, source chip on every number | `dashboard/data.py`, `tests/test_dashboard.py` |
| Mylapalli Abhishek Raj | Dataset research and acquisition | `scripts/fetch_collmlight_data.sh`; commit "acquire and verify datasets (step 1.4)" |
| Mylapalli Abhishek Raj | IDD to YOLO conversion and drive-level splits | `scripts/prepare_idd.py`, `scripts/resize_idd.py` |
| Mylapalli Abhishek Raj | Integration and configuration | `configs/default.yaml`, `config.py`, `experiment.py`, `scripts/run_experiment.py` |
| Mylapalli Abhishek Raj | pytest suite, LLM test doubles only in `tests/` | `tests/test_llm_client.py` (in-process fake HTTP session, no port), `tests/test_llm_controller.py` |
| Mylapalli Abhishek Raj | README, git/GitHub, environment and requirements | `README.md`, `pyproject.toml`, `requirements-lock.txt` |

"Dataset preparation" appeared in two roles (Bhargav: dataset preparation and class mapping;
Abhishek: preprocessing, format conversion and splits). The table splits it: the class mapping
under Bhargav, the conversion and splits under Abhishek. Confirm this split.

## 3. Left out (could not be verified)

Nothing from the role descriptions had to be left out: each named area has code in the
repository. As instructed, nothing was taken from the old contribution sheets: no numbers, model
names, paths, hardware, ports, Python versions or metrics. The outdated claims of those sheets
(model, accuracy, dataset size, GPU, baseline, run length, test server) appear nowhere in the
report: `scripts/check_report_format.py` enforces this. The old sheets' individual "Declaration"
signature blocks are not included.

## 4. The AI-assistant paragraph: confirm the wording with the guide

Under Table 1.2 the report says:

> The project was developed with the help of an AI coding assistant (Claude Code), working under
> the team's direction: the team decided what to build and how to evaluate it, reviewed the code
> and the text, ran the experiments and checked the results, and is responsible for all of the
> work presented in this report.

Please confirm this wording with the guide, Dr. Mohd Irfan, and change it in
`docs/report/10_ch1_introduction.md` if the university asks for a different statement.

## 5. Other points for the team

* **Table number.** The table is **Table 1.2**, not Table 1.1: the literature survey's comparison
  of controller families (Section 1.2.9) is Chapter 1's first table. If it must be Table 1.1,
  that comparison table has to move out of Chapter 1 or lose its number; say which.
* **Hosted model cost.** Chapter 3 says the cost of the NVIDIA API used for the exploratory
  model-size study was "not recorded by the project". If the team knows it (for example, free
  developer credits), give the fact and it will be stated.
* **By hand after printing:** examiners' signatures, the Program Chair's and Dean's names and
  signatures (certificate), each student's mobile number, permanent address and photo
  (biodata). These are blank lines in the Word file; never commit the real values.
