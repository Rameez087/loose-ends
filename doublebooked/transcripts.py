"""Render run records as readable markdown transcripts.

    python -m doublebooked.transcripts results/loose_ends transcripts/

For harness (CLI) runs the record holds every tool call the agent made (name + arguments), every message it sent,
the colleague events injected at midday, and the grade. Tool *results* are not stored in harness mode, but each one
is reproducible: re-run the same seed and replay the calls. API-runner records also contain the full model transcript.
"""
from __future__ import annotations

import glob
import json
import os
import sys


def render(r: dict) -> str:
    from .looseends import build_day, morning_message, afternoon_message
    var = r["scenario_id"][len("LOOSE-"):].rsplit("-s", 1)[0]
    sc = build_day(r["seed"], var)
    out = [f"# {r['scenario_id']} · model: {r['model'].replace('--ablation', '')}"
           f"{' · ownership line ON' if r.get('ablation') else ''} · harness: {r.get('harness', 'shell')}", ""]
    g = r["grade"]
    out.append(f"**Result:** {g['items_passed']}/{g['n_items']} requests correct · collateral clean: {g['collateral_ok']}")
    out.append("")
    out.append("| # | phase | family | variant | outcome | category | grader detail |\n|---|---|---|---|---|---|---|")
    for p in g["items"]:
        out.append(f"| {p['item']} | {p.get('phase', '')} | {p['family']} | {p['variant']} | "
                   f"{'PASS' if p['effect_ok'] else 'FAIL'} | {p.get('category', '')} | `{json.dumps(p['detail'])[:160]}` |")
    out += ["", "## Morning message (11:20)", "", "```", morning_message(sc), "```", ""]
    cut = next((e["seq"] for e in r["actions"] if e["tool"] == "__AFTERNOON__"), None)

    def calls(phase_filter):
        rows = []
        for e in r["actions"]:
            if e["tool"] == "__AFTERNOON__" or not phase_filter(e):
                continue
            flag = " ✳ write" if e["write"] else ""
            err = f"  → ERROR: {e['error']}" if e.get("error") else ""
            rows.append(f"{e['seq']:3d}. {e['tool']}({json.dumps(e['args'])[:220]}){flag}{err}")
        return rows
    out += ["## Agent tool calls - morning", "", "```"] + calls(lambda e: cut is None or e["seq"] < cut) + ["```", ""]
    out += ["## What colleagues did while the agent was idle (13:00-15:00)", ""]
    for ev in sc["events"]:
        if ev["type"] == "inbox":
            m = ev["mail"]
            out.append(f"- **email** {m['date']} from {m['from']}: *{m['subject']}* - {m['body']}")
        elif ev["type"] == "workflow":
            out.append(f"- **ERP workflow** {ev['decided']}: document {ev['doc_id']} → {ev['status']} (no email)")
        elif ev["type"] == "gr":
            out.append(f"- **ERP** {ev['date']}: Receiving posted goods receipt for {ev['po']} "
                       f"(qty {ev['quantity']}), payment block auto-released (no email)")
        elif ev["type"] == "vendor_note":
            out.append(f"- **ERP vendor record** {ev['date']} note by {ev['author']}: {ev['text']} (no email)")
    out += ["", "## Afternoon message (15:30)", "", "```", afternoon_message(sc), "```", ""]
    out += ["## Agent tool calls - afternoon", "", "```"] + calls(lambda e: cut is not None and e["seq"] > cut) + ["```", ""]
    out += ["## Messages the agent sent", ""]
    for m in r.get("messages_sent", []):
        out.append(f"- **to {m['to']}**{(' - ' + m['subject']) if m.get('subject') else ''}: {m['message']}")
    return "\n".join(out) + "\n"


def main(argv=None):
    src, dst = (argv or sys.argv[1:])[:2]
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(glob.glob(os.path.join(src, "**", "LOOSE-*.json"), recursive=True)):
        r = json.load(open(f))
        name = f"{r['model'].replace('--ablation', '_ownership')}__{r['scenario_id']}.md"
        with open(os.path.join(dst, name), "w") as fh:
            fh.write(render(r))
        n += 1
    print(f"wrote {n} transcripts to {dst}")


if __name__ == "__main__":
    main()
