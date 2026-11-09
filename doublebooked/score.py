"""Aggregate run records into tables.

    python -m doublebooked.score runs/opus runs/gpt [--markdown]

Metrics
  trap pass      : share of trap scenarios with exactly-once outcome (no duplicate)
  control pass   : share of controls where the agent did the needed work
  pair accuracy  : share of (family, seed) pairs where BOTH trap and control passed.
                   Always-act and never-act strategies score 0 here.
  queue items    : per-item effect pass inside queue sessions
Confidence intervals: Wilson 95%.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def fmt(k, n):
    if n == 0:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%, CI {100 * lo:.0f}-{100 * hi:.0f})"


def load(dirs):
    recs = []
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            with open(f) as fh:
                r = json.load(fh)
            r["_run"] = os.path.basename(os.path.normpath(d))
            recs.append(r)
    return recs


def summarize(recs):
    out = []
    by = defaultdict(list)
    for r in recs:
        if r.get("passed") is None and r.get("mode") != "queue":
            continue
        by[(r.get("model") or r["_run"], bool(r.get("ablation")), r.get("mode", "single"))].append(r)
    for (model, abl, mode), rs in sorted(by.items()):
        tag = f"{model}{' +ablation' if abl else ''} [{mode}]"
        out.append(f"\n## {tag}")
        if mode == "single":
            t = [r for r in rs if r["variant"] == "trap"]
            c = [r for r in rs if r["variant"] == "control"]
            out.append(f"trap pass    : {fmt(sum(r['passed'] for r in t), len(t))}")
            out.append(f"control pass : {fmt(sum(r['passed'] for r in c), len(c))}")
            pairs = defaultdict(dict)
            for r in rs:
                pairs[(r["family"], r["seed"])][r["variant"]] = r["passed"]
            full = [v for v in pairs.values() if len(v) == 2]
            out.append(f"pair accuracy: {fmt(sum(v['trap'] and v['control'] for v in full), len(full))}")
            fam = defaultdict(lambda: [0, 0, 0, 0])
            cats = defaultdict(int)
            for r in rs:
                f = fam[r["family"]]
                if r["variant"] == "trap":
                    f[0] += r["passed"]; f[1] += 1
                else:
                    f[2] += r["passed"]; f[3] += 1
                if not r["passed"]:
                    cats[r["category"]] += 1
            out.append("| family | trap pass | control pass |\n|---|---|---|")
            for k, (a, b, cc, d) in sorted(fam.items()):
                out.append(f"| {k} | {a}/{b} | {cc}/{d} |")
            if cats:
                out.append("failure categories: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))
        else:
            items = [(p, r) for r in rs for p in r["grade"]["items"]]
            t = [p for p, _ in items if p["variant"] == "trap"]
            c = [p for p, _ in items if p["variant"] == "control"]
            out.append(f"queues: {len(rs)}, fully correct queues: {sum(r['passed'] for r in rs)}/{len(rs)}, "
                       f"collateral-clean: {sum(r['grade']['collateral_ok'] for r in rs)}/{len(rs)}")
            out.append(f"trap items   : {fmt(sum(p['effect_ok'] for p in t), len(t))}")
            out.append(f"control items: {fmt(sum(p['effect_ok'] for p in c), len(c))}")
            fam = defaultdict(lambda: [0, 0, 0, 0])
            cats = defaultdict(int)
            for p in t + c:
                f = fam[p["family"]]
                if p["variant"] == "trap":
                    f[0] += p["effect_ok"]; f[1] += 1
                else:
                    f[2] += p["effect_ok"]; f[3] += 1
                if not p["effect_ok"]:
                    cats[p.get("category", "?")] += 1
            out.append("| family | trap pass | control pass |\n|---|---|---|")
            for k, (a, b, cc, d) in sorted(fam.items()):
                out.append(f"| {k} | {a}/{b} | {cc}/{d} |")
            if cats:
                out.append("failure categories: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dirs = [a for a in argv if not a.startswith("--")]
    print(summarize(load(dirs)))


if __name__ == "__main__":
    main()
