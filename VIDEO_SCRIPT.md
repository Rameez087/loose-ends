# Video script: "Loose Ends" (about 4.5 minutes, AI voice is fine)

**[0:00–0:25] Hook.** *Screen: README headline table.*
"Frontier AI agents don't double-pay invoices, they don't fall for bank-change fraud, and they don't leak confidential
notes. I tested all of that. Where they fail is simpler: they don't go back. When an approval clears quietly in the ERP,
Claude Opus 5.5 leaves 42% of its own open requests unfinished, then reports them as still pending."

**[0:25–1:05] Who I am and why this matters.**
"I work on SAP S/4HANA finance data. In an ERP, the approver approves in the workflow and the warehouse posts the goods
receipt. Nobody emails accounts payable. Real ops work is mostly follow-up, so an agent that waits for a notification
leaves vendors unpaid, accruals unbooked, and false status reports for colleagues."

**[1:05–2:00] The task.** *Screen: `looseends.py` blocker table, then a PROMPT.txt.*
"Each scenario is one workday in a seeded ERP. In the morning, three of four requests correctly can't be finished:
an invoice awaiting approval, a goods receipt missing, an unverified bank change, an accrual without an amount. While the
agent is idle, colleagues act. At 15:30 two unrelated requests arrive. Every clear day has a hold twin where nothing clears,
so an agent that always acts fails one and an agent that never revisits fails the other."

**[2:00–2:45] The grader.** *Screen: terminal running `python -m doublebooked.validate --all`.*
"No LLM judge. After the agent stops, the ERP runs its night jobs, then we check business effects: paid exactly once,
IBAN changed, account balance correct, and nothing else touched. Scripted reference agents validate it: careful scores 100%,
never-revisit scores 0% on clear days, over hundreds of generated days."

**[2:45–3:45] Results.** *Screen: results table, then the s214 action log.*
"Emailed blockers: Opus closes 24 of 24. Silent blockers in the system of record: 14 of 24. All ten failures look the same:
it re-reads the inbox and never re-queries the ERP. Here's seed 214: approval at 13:52, goods receipt at 14:10, and at 15:30
Opus reports 'still waiting on approval'. Sonnet closes half and Haiku none. On hold days every model held correctly, so
this isn't recklessness. One sentence telling it to re-check open items lifts Opus to 5 of 6, so it's a default habit, not
missing capability."

**[3:45–4:15] Credibility.** *Screen: RESULTS.md failure-search table.*
"Before finding this I tried about twenty other failure ideas blind: duplicate payments, timeouts, fraud, confidentiality,
a full month-end close on raw SAP exports. Opus passed all of them. Those negative results are in the repo, so this finding
isn't cherry-picked."

**[4:15–4:30] Close.** *Screen: reproduce commands.*
"Stdlib-only Python, one command per provider, and every run saved. Agents need to finish what they start. Loose Ends
measures whether they do."
