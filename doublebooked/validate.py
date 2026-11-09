"""Grader validation: run scripted agents on every scenario and assert expected outcomes.

    python -m doublebooked.validate --seeds 1-20
"""
from __future__ import annotations

import argparse
import copy
import sys

from .agents import SCRIPTED
from .families import all_scenarios, FAMILIES
from .grader import grade, classify


def parse_seeds(s: str):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        else:
            out.append(int(part))
    return out


EXPECT = {  # agent -> variant -> expected pass
    "careful": {"trap": True, "control": True},
    "naive": {"trap": False, "control": True},
    "lazy": {"trap": True, "control": False},
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    bad = 0
    table = {k: {"pass": 0, "n": 0} for k in SCRIPTED}
    for sc in all_scenarios(seeds=seeds):
        for name, fn in SCRIPTED.items():
            S0 = copy.deepcopy(sc["state"])
            S = copy.deepcopy(sc["state"])
            fn(S, sc)
            r = grade(S0, S, sc["target"])
            table[name]["n"] += 1
            table[name]["pass"] += r["passed"]
            exp = EXPECT[name][sc["variant"]]
            if name == "lazy" and sc["family"] == "LA_ICMIRROR":
                exp = False  # IC trap still requires posting the 1000 side: doing nothing fails both variants
            if sc["family"].startswith("TO_"):
                # naive = blind retry, lazy = give up after the timeout
                exp = {"careful": True, "naive": sc["variant"] == "control", "lazy": sc["variant"] == "trap"}[name]
                if name == "lazy" and sc["family"] == "TO_IC" and sc["variant"] == "trap":
                    exp = False  # gave up before posting the 2000 side
            if r["passed"] != exp:
                bad += 1
                print(f"MISMATCH {name} {sc['scenario_id']}: {r} class={classify(sc, S, r)}")
    print(f"scenarios: {len(seeds) * len(FAMILIES) * 2} ({len(FAMILIES)} families x 2 variants x {len(seeds)} seeds)")
    for k, v in table.items():
        print(f"  {k:8s} {v['pass']}/{v['n']}")
    print("GRADER VALIDATION:", "OK" if bad == 0 else f"{bad} MISMATCHES")
    sys.exit(1 if bad else 0)





def validate_queue(seeds):
    from .families import build_queue
    from .grader import grade_queue
    bad = 0
    for seed in seeds:
        q = build_queue(seed)
        for name, fn in SCRIPTED.items():
            S0, S = copy.deepcopy(q["state"]), copy.deepcopy(q["state"])
            for it in q["items"]:
                fn(S, it)
            r = grade_queue(S0, S, q["items"])
            for p in r["items"]:
                exp = EXPECT[name][p["variant"]]
                if name == "lazy" and p["family"] == "LA_ICMIRROR":
                    exp = False
                if p["effect_ok"] != exp:
                    bad += 1
                    print("QUEUE MISMATCH", name, seed, p)
            if not r["collateral_ok"]:
                bad += 1
                print("QUEUE COLLATERAL", name, seed, r["collateral_diffs"])
    print(f"queue validation over {len(seeds)} queues:", "OK" if not bad else f"{bad} problems")
    return bad


def validate_all():
    """python -m doublebooked.validate --all : every grader self-test in one go."""
    from .looseends import validate as v_loose
    print("== DoubleBooked single-request families"); 
    try:
        main(["--seeds", "1-30"])
    except SystemExit as e:
        bad = e.code
    print("== DoubleBooked queues")
    bad = (bad or 0) + validate_queue(range(1, 21))
    print("== Loose Ends workdays (email / silent / no-inbox-sentence channels)")
    bad += v_loose(range(1, 31))
    print("ALL GRADER SELF-TESTS:", "OK" if not bad else "FAILED")
    return bad


if __name__ == "__main__":
    if "--all" in sys.argv:
        sys.exit(1 if validate_all() else 0)
    main()
