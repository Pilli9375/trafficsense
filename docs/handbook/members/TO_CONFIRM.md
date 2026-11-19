# Member speaking guides: points to confirm

The four guides (`Bhargav_Kumar.md`, `Akul_Lakhan.md`, `Darsi_Amit.md`, `Abhishek_Raj.md`) were
written only from the report's team table (`docs/report/10_ch1_introduction.md`), the handbook's
"Who Explains What" part, and the repository. Every file, feature and claim in them was checked
against the code. Every number carries the report's tags and is checked by
`scripts/check_handbook.py`.

## 1. Who did what cannot be checked from git

The git history is under two author names, "Pilli" and "Naga Adithya", neither of them one of the
four students. So the repository proves that each file or feature in a guide **exists**, but not
**which student** built it. Each guide's "What I did" list follows the report's team table, which
the team gave and must confirm (see also `docs/report/CONTRIBUTIONS_TO_CONFIRM.md`). Each member
should read their guide and correct anything they would not say in the first person.

## 2. Left out because it could not be verified

- Nothing from the old pre-restart contribution sheets is used. `scripts/check_handbook.py` fails if
  any of their outdated claims (model, accuracy, GPU, baseline, run length, test server) appear.
- **Personal effort or time spent** by each member (hours, weeks): not recorded anywhere, left out.
- **Which member ran which experiment:** not recorded per person, left out. The guides say only
  "the team ran the experiments", in the report's wording.
- **The TrafficSense.bat launcher:** not found on this machine, so Amit's guide gives only the
  manual start command.
