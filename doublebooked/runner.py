"""Official API runner: native tool-calling loop against Anthropic, OpenAI or OpenRouter.

    export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY / OPENROUTER_API_KEY
    python -m doublebooked.runner --provider anthropic --model claude-opus-5-5 --seeds 1-5 --out runs/opus
    python -m doublebooked.runner --provider scripted --model careful --out runs/careful   # offline, no key
    (scripted models for --suite loose: careful | never_revisit | always_act)

Zero third-party dependencies (stdlib urllib). Each scenario writes one JSON
record (transcript, action log, grade, failure category) to --out.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .agents import SCRIPTED
from .erp import TOOLS, call_tool, json_schema
from .families import FAMILIES, VARIANTS, SYSTEM_PROMPT, ABLATION_LINE, all_scenarios, user_message
from .grader import grade, classify
from .validate import parse_seeds

MAX_TURNS = 40


MIN_INTERVAL = [0.0]   # seconds between API calls (free tiers: ~10-15 requests/minute)
_last = [0.0]


def _post(url, headers, body, retries=8):
    data = json.dumps(body).encode()
    for attempt in range(retries):
        wait = MIN_INTERVAL[0] - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < retries - 1:
                time.sleep(min(90, 2 ** attempt * 5))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            raise RuntimeError(str(e))


def _tool_result_text(out):
    s = json.dumps(out)
    return s if len(s) < 30000 else s[:30000] + "...(truncated)"


def run_anthropic(S, system, user, model, temperature, msgs=None, transcript=None):
    key = os.environ["ANTHROPIC_API_KEY"]
    tools = [{"name": n, "description": t["description"], "input_schema": json_schema(n)} for n, t in TOOLS.items()]
    msgs = msgs if msgs is not None else []
    msgs.append({"role": "user", "content": user})
    transcript = transcript if transcript is not None else []
    transcript.append({"role": "user", "content": user})
    for _ in range(MAX_TURNS):
        body = {"model": model, "max_tokens": 4096, "system": system, "messages": msgs, "tools": tools}
        if temperature is not None:
            body["temperature"] = temperature
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
        msgs.append({"role": "assistant", "content": r["content"]})
        transcript.append({"role": "assistant", "content": r["content"]})
        uses = [c for c in r["content"] if c["type"] == "tool_use"]
        if not uses:
            break
        results = []
        for u in uses:
            out = call_tool(S, u["name"], u["input"])
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": _tool_result_text(out)})
        msgs.append({"role": "user", "content": results})
        transcript.append({"role": "tool", "content": results})
    return transcript, msgs


def run_openai_compat(S, system, user, model, temperature, base_url, key_env, msgs=None, transcript=None):
    key = os.environ[key_env]
    tools = [{"type": "function", "function": {"name": n, "description": t["description"],
                                               "parameters": json_schema(n)}} for n, t in TOOLS.items()]
    msgs = msgs if msgs is not None else [{"role": "system", "content": system}]
    msgs.append({"role": "user", "content": user})
    transcript = transcript if transcript is not None else []
    transcript.append({"role": "user", "content": user})
    for _ in range(MAX_TURNS):
        body = {"model": model, "messages": msgs, "tools": tools}
        if temperature is not None:
            body["temperature"] = temperature
        r = _post(base_url + "/chat/completions", {"authorization": f"Bearer {key}"}, body)
        m = r["choices"][0]["message"]
        m = {k: v for k, v in m.items() if k in ("role", "content", "tool_calls")}
        if m.get("content") is None:
            m["content"] = ""
        msgs.append(m)
        transcript.append(m)
        calls = m.get("tool_calls") or []
        if not calls:
            break
        for c in calls:
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"__unparseable__": c["function"]["arguments"]}
            out = call_tool(S, c["function"]["name"], args)
            tm = {"role": "tool", "tool_call_id": c["id"], "content": _tool_result_text(out)}
            msgs.append(tm)
            transcript.append(tm)
    return transcript, msgs


def converse(provider, S, system, user, model, temperature, msgs=None, transcript=None):
    if provider == "anthropic":
        return run_anthropic(S, system, user, model, temperature, msgs, transcript)
    if provider == "openai":
        return run_openai_compat(S, system, user, model, temperature,
                                 os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), "OPENAI_API_KEY",
                                 msgs, transcript)
    if provider == "openrouter":
        return run_openai_compat(S, system, user, model, temperature, "https://openrouter.ai/api/v1",
                                 "OPENROUTER_API_KEY", msgs, transcript)
    if provider == "gemini":  # Google AI Studio key, OpenAI-compatible endpoint
        return run_openai_compat(S, system, user, model, temperature,
                                 "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
                                 msgs, transcript)
    raise ValueError(provider)


def run_day(sc, provider, model, ablation, temperature):
    """Loose Ends: morning conversation -> colleagues act while the agent is idle -> 15:30 follow-up turn."""
    from .looseends import morning_message, afternoon_message, apply_events, system_prompt, grade_day, run_scripted_day
    from .sandbox import classify_day_item
    S = copy.deepcopy(sc["state"])
    system = system_prompt(sc, ablation)
    err, transcript = None, []
    try:
        if provider == "scripted":
            def ev(S_, events):
                S_["log"].append({"seq": len(S_["log"]) + 1, "tool": "__AFTERNOON__", "args": {}, "write": False})
                apply_events(S_, events)
            S = run_scripted_day(sc, model, ev)
        else:
            transcript, msgs = converse(provider, S, system, morning_message(sc), model, temperature)
            S["log"].append({"seq": len(S["log"]) + 1, "tool": "__AFTERNOON__", "args": {}, "write": False})
            apply_events(S, sc["events"])
            transcript, msgs = converse(provider, S, system, afternoon_message(sc), model, temperature, msgs, transcript)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    r = grade_day(sc, S)
    for p, it in zip(r["items"], sc["items"]):
        p["phase"] = it["phase"]
        p["category"] = classify_day_item(it, S, p["effect_ok"])
    return {"scenario_id": sc["scenario_id"], "mode": "day", "seed": sc["seed"], "variant": sc["variant"],
            "channel": sc["channel"], "ablation": ablation, "model": model, "provider": provider, "harness": "api",
            "passed": r["passed"] if not err else None, "error": err, "grade": r, "system": system,
            "actions": S["log"], "messages_sent": S["outbox"], "transcript": transcript}


def run_one(sc, provider, model, ablation, temperature):
    S0 = copy.deepcopy(sc["state"])
    S = copy.deepcopy(sc["state"])
    system = SYSTEM_PROMPT + (ABLATION_LINE if ablation else "")
    user = user_message(sc)
    err = None
    try:
        if provider == "scripted":
            SCRIPTED[model](S, sc)
            transcript = [{"role": "scripted", "agent": model}]
        else:
            transcript, _ = converse(provider, S, system, user, model, temperature)
    except Exception as e:  # infrastructure error: recorded, excluded from scoring
        transcript, err = [], f"{type(e).__name__}: {e}"
    r = grade(S0, S, sc["target"])
    return {"scenario_id": sc["scenario_id"], "family": sc["family"], "variant": sc["variant"], "seed": sc["seed"],
            "tier": sc["tier"], "ablation": ablation, "model": model, "provider": provider, "harness": "api",
            "passed": r["passed"] if not err else None, "category": classify(sc, S, r) if not err else "infra_error",
            "error": err, "grade": r, "system": system, "user": user, "actions": S["log"],
            "messages_sent": S["outbox"], "transcript": transcript}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True, choices=["anthropic", "openai", "openrouter", "gemini", "scripted"])
    ap.add_argument("--min-interval", type=float, default=None,
                    help="seconds between API calls (default 0; 6 for --provider gemini to fit free-tier limits)")
    ap.add_argument("--suite", default="loose", choices=["loose", "doublebooked"],
                    help="loose = Loose Ends workdays (headline); doublebooked = single-request exactly-once traps")
    ap.add_argument("--channels", default="silent,email", help="Loose Ends signal channels to run")
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", default="1-3")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--ablation", action="store_true", help="add the one-line 'check in-flight work' instruction")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    need = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GEMINI_API_KEY"}.get(a.provider)
    MIN_INTERVAL[0] = a.min_interval if a.min_interval is not None else (6.0 if a.provider == "gemini" else 0.0)
    if a.provider == "gemini":
        a.workers = 1
    if need and not os.environ.get(need):
        sys.exit(f"error: set {need} to run --provider {a.provider} (or use --provider scripted for an offline run)")
    os.makedirs(a.out, exist_ok=True)
    if a.suite == "loose":
        from .looseends import build_day
        sfx = {"silent": "_silent", "email": ""}
        scs = [build_day(seed, v + sfx[ch]) for seed in parse_seeds(a.seeds) for ch in a.channels.split(",")
               for v in ("clear", "hold")]
    else:
        scs = list(all_scenarios(seeds=parse_seeds(a.seeds), families=a.families.split(","),
                                 variants=a.variants.split(",")))
    todo = [sc for sc in scs if not os.path.exists(os.path.join(a.out, sc["scenario_id"] + ".json"))]
    print(f"{len(scs)} scenarios, {len(scs) - len(todo)} already done, running {len(todo)} "
          f"({a.provider}:{a.model}{' +ablation' if a.ablation else ''})")

    def work(sc):
        rec = (run_day if sc.get("mode") == "day" else run_one)(sc, a.provider, a.model, a.ablation, a.temperature)
        with open(os.path.join(a.out, sc["scenario_id"] + ".json"), "w") as f:
            json.dump(rec, f, indent=1)
        flag = "PASS" if rec["passed"] else ("ERR " if rec["passed"] is None else "FAIL")
        cat = rec.get("category") or ", ".join(p["category"] for p in rec["grade"]["items"] if p["category"] != "pass") or "all pass"
        print(f"  {flag} {sc['scenario_id']:32s} {cat}" + (f"  {rec['error'][:120]}" if rec["error"] else ""), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        list(ex.map(work, todo))
    print(f"done -> {a.out}.  Score with: python -m doublebooked.score {a.out}")


if __name__ == "__main__":
    sys.exit(main())
