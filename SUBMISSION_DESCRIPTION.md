**Loose Ends: do AI finance agents finish what they start?**

An agentic eval in a seeded, SAP-style ERP simulator (AP, GL, treasury). Each scenario is a workday. In the morning,
requests are correctly blocked (pending approval, missing goods receipt, unverified bank change, missing accrual amount).
While the agent is idle, colleagues clear the blockers, or don't. At 15:30 new work arrives. Grading is deterministic and
effect-based: after the ERP's night jobs run, each request must have happened exactly once (paid, booked, master data
changed) with no collateral changes. There is no LLM judge. Minimal pairs (blocker clears / doesn't clear) defeat
always-act and never-act strategies, and scripted reference agents validate the grader with no false passes or false fails.

**Finding (blind runs):** frontier agents follow written rules and unwritten controls, and never double-pay; Claude
Opus 5.5 passed every one of about 20 other failure hypotheses I tested. But when a blocker clears *silently in the system of
record*, which is how approvals and goods receipts actually happen in an ERP, Opus leaves **42% (10/24)** of its own
open requests unfinished and reports them as still pending. When the same event arrives by email it closes **24/24**. All 10 drops share one mechanism: it
re-checked the inbox but never re-queried the ERP record that held the update (workflow status, goods receipts, vendor notes). Sonnet 5.5 closes 3/6 and Haiku 5.5 0/3 silent loose ends. Every model
held correctly on no-clear days. A one-line "re-check your open items" instruction lifts Opus to 5/6, which shows a default
habit, not missing capability.

Stdlib-only Python. API runner for Anthropic, OpenAI, OpenRouter and Gemini, offline scripted mode, and all run records included.

Code: https://github.com/Rameez087/loose-ends · Video: https://youtu.be/dx4zKIjnzHI
