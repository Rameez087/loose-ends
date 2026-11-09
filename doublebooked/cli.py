"""Command-line access to the ERP, for agent harnesses that act through a shell
(Claude Code, Codex CLI, etc.).

    erp help                      list tools
    erp <tool> --arg value ...    call a tool (values are parsed as JSON when possible)
"""
from __future__ import annotations

import json
import os
import sys

from .erp import TOOLS, call_tool


def _load(path):
    with open(path) as f:
        return json.load(f)


def _save(path, S):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(S, f)
    os.replace(tmp, path)


def _help():
    lines = ["Meridian ERP command line. Usage: erp <tool> --arg value ...",
             "Values are parsed as JSON when possible (use quotes for lists/objects).", ""]
    for name, spec in TOOLS.items():
        args = " ".join(f"--{p}{'' if req else '?'}" for p, (_, _, req) in spec["params"].items())
        lines.append(f"  {name} {args}\n      {spec['description']}")
    lines.append("\n(? = optional)")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    state_path = os.environ.get("ERP_STATE")
    if argv[:1] == ["--state"]:
        state_path, argv = argv[1], argv[2:]
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(_help())
        return 0
    tool, rest = argv[0], argv[1:]
    args, i = {}, 0
    while i < len(rest):
        k = rest[i]
        if not k.startswith("--"):
            print(json.dumps({"ok": False, "error": f"expected --arg, got {k!r}"}))
            return 2
        k = k[2:].replace("-", "_")
        if "=" in k:
            k, v = k.split("=", 1)
            i += 1
        else:
            v = rest[i + 1] if i + 1 < len(rest) else ""
            i += 2
        try:
            val = json.loads(v)
            if isinstance(val, (int, float)) and k in ("doc_id", "vendor_id", "company", "account", "reference",
                                                       "invoice_doc_id", "run_id", "payment_id", "entry_id"):
                val = v
        except (json.JSONDecodeError, ValueError):
            val = v
        args[k] = val
    S = _load(state_path)
    out = call_tool(S, tool, args)
    _save(state_path, S)
    print(json.dumps(out, indent=1))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
