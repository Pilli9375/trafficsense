"""The pre-registered rule used to pick one baseline setting from a sweep.

  1. Each scenario counts once. Its score for a setting is the mean ATT over the seeds.
  2. Within each scenario the settings are ranked by that score, 1 = lowest ATT
     (equal scores share the average rank).
  3. The chosen setting has the lowest mean rank over the scenarios.
  4. Tie-break: the lowest mean over scenarios of (score / best score in that scenario);
     if still tied, the smallest setting value.
"""
from __future__ import annotations

import statistics


def ranks(scores: dict[int, float]) -> dict[int, float]:
    """1 = lowest score; equal scores share the average rank."""
    order = sorted(scores, key=scores.get)
    out = {}
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + j) / 2 + 1
        i = j + 1
    return out


def select(att: dict[str, dict[int, float]]) -> dict:
    """att[scenario][setting] = mean ATT over seeds. Applies the rule in the module docstring."""
    settings = sorted(next(iter(att.values())))
    r = {sc: ranks(v) for sc, v in att.items()}
    rel = {sc: {k: v[k] / min(v.values()) for k in v} for sc, v in att.items()}
    mean_rank = {k: statistics.mean(r[sc][k] for sc in att) for k in settings}
    mean_rel = {k: statistics.mean(rel[sc][k] for sc in att) for k in settings}
    chosen = min(settings, key=lambda k: (mean_rank[k], mean_rel[k], k))
    return {"rank": r, "att_over_best": rel, "mean_rank": mean_rank, "mean_att_over_best": mean_rel,
            "chosen": chosen}
