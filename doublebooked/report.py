"""Aggregate Loose Ends run records into RESULTS tables.

    python -m doublebooked.report results/loose_ends > results/LOOSE_ENDS_RESULTS.md
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

from .score import fmt


def condition(r):
    sid = r["scenario_id"]
    ch = "silent (system of record)" if "_silent" in sid else "email notification"
    if "_noinbox" in sid:
        ch += ", no inbox sentence"
    return ch


def main(argv=None):
    root = (argv or sys.argv[1:])[0]
    recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(root, "**", "LOOSE-*.json"), recursive=True))]
    by = defaultdict(lambda: {"clear": [0, 0], "hold": [0, 0], "fill": [0, 0], "days": [0, 0], "fam": defaultdict(lambda: [0, 0]),
                              "cat": defaultdict(int), "coll": 0})
    skipped = [r for r in recs if r.get("error")]
    recs = [r for r in recs if not r.get("error")]
    for r in recs:
        key = (r["model"].replace("--ablation", ""), condition(r), "yes" if r.get("ablation") else "no")
        b = by[key]
        b["days"][1] += 1
        b["days"][0] += r["grade"]["passed"]
        b["coll"] += not r["grade"]["collateral_ok"]
        for p in r["grade"]["items"]:
            if p["family"].startswith("B_"):
                v = p["variant"]
                b[v][1] += 1
                b[v][0] += p["effect_ok"]
                if v == "clear":
                    b["fam"][p["family"]][1] += 1
                    b["fam"][p["family"]][0] += p["effect_ok"]
                if not p["effect_ok"]:
                    b["cat"][p["category"]] += 1
            else:
                b["fill"][1] += 1
                b["fill"][0] += p["effect_ok"]
    out = ["| model | blocker cleared via | ownership line | days | clear: loose ends closed | hold: correctly held | "
           "routine items | failure categories |", "|---|---|---|---|---|---|---|---|"]
    for (m, ch, ab), b in sorted(by.items()):
        cats = ", ".join(f"{k.split(':')[-1]}={v}" for k, v in sorted(b["cat"].items())) or "-"
        out.append(f"| {m} | {ch} | {ab} | {b['days'][1]} | {fmt(*b['clear'])} | {fmt(*b['hold'])} | "
                   f"{fmt(*b['fill'])} | {cats} |")
    out.append("\n**Per blocker family (clear days only):**\n")
    out.append("| model | channel | ownership line | B_APPROVAL | B_GR | B_BANK | B_INFO |\n|---|---|---|---|---|---|---|")
    for (m, ch, ab), b in sorted(by.items()):
        f = b["fam"]
        cell = lambda k: f"{f[k][0]}/{f[k][1]}" if f[k][1] else "-"
        out.append(f"| {m} | {ch} | {ab} | {cell('B_APPROVAL')} | {cell('B_GR')} | {cell('B_BANK')} | {cell('B_INFO')} |")
    # micro1-guide format: task = blocker family; trials = instances across seeds; pass^k = every trial passed
    out.append("\n**Guide-format summary (blocked requests only; task = blocker family, trials = seeded instances, "
               "clear + hold days pooled):**\n")
    out.append("| model (harness: CLI agent, default temperature) | channel | ownership line | trials per task (min-max) | "
               "pass rate | pass^k (share of tasks with every trial passed) |\n|---|---|---|---|---|---|")
    tri = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in recs:
        key = (r["model"].replace("--ablation", ""), condition(r), "yes" if r.get("ablation") else "no")
        for p in r["grade"]["items"]:
            if p["family"].startswith("B_"):
                t = tri[key][p["family"]]
                t[0] += p["effect_ok"]; t[1] += 1
    for key, fams in sorted(tri.items()):
        k_ = [v[1] for v in fams.values()]
        ok = sum(v[0] for v in fams.values()); n = sum(k_)
        pk = sum(1 for v in fams.values() if v[0] == v[1])
        out.append(f"| {key[0]} | {key[1]} | {key[2]} | {min(k_)}-{max(k_)} | {fmt(ok, n)} | {pk}/{len(fams)} |")
    if skipped:
        out.append(f"\n_{len(skipped)} run(s) with infrastructure errors excluded._")
    print("\n".join(out))


if __name__ == "__main__":
    main()
