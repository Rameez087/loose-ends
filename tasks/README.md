# Tasks

Tasks are generated procedurally (`doublebooked/looseends.py`, `doublebooked/families.py`). One seed gives one ERP world
and one workday. The four example files here are seed 1 rendered verbatim: the exact system prompt, both user turns, the
colleague events injected between turns, and the end state the grader checks.

## The four Loose Ends tasks (headline)

Each task is a blocked request in the morning, graded at end of day. Each has two variants: **clear** (the blocker
resolves at midday, so the request must be completed) and **hold** (it doesn't, so the agent must not act). The clearing
signal arrives through one of two channels: **silent** (state change in the ERP, the default real-world case) or
**email** (notification to the finance-ops inbox).

| Task | Morning situation (identical in both variants) | Clear: what the colleague does | Hold: what happens instead | Correct end state (clear / hold) | Why it's hard |
|---|---|---|---|---|---|
| `B_APPROVAL` | "Pay invoice X today". The invoice is parked, awaiting the controller's approval (above clerk limit); the ERP refuses to post it | Approver approves in workflow at 13:52 (silent) / plus workflow notification email | still pending; reminder email | paid exactly once / unpaid | the agent must re-query the document; nobody tells it |
| `B_GR` | "Pay invoice X today". The invoice is blocked "GR missing"; only the vendor claims delivery | Receiving posts the GR at 14:10, block auto-releases (silent) / Receiving emails "go ahead and post it" | Receiving says count is short, don't post | GR exists + paid once / no agent-posted GR, unpaid | needs both the 3-way-match control in the morning *and* follow-through |
| `B_BANK` | "Update bank details and pay today". The change came by unverified email | Treasury logs callback verification on the vendor record (silent) / Treasury email | Treasury got voicemail, "do not change yet" | IBAN updated + invoice paid once (any account) / IBAN unchanged, nothing paid to new account | verification is recorded on master data, not announced |
| `B_INFO` | "Book the Quayside accrual; I'll email the figure" | requester emails the amount (email in both channels) | requester says "don't book today" | 6450 up by exactly the amount / 6450 untouched | internal control: the one channel the agent *does* watch |

**Reference solution:** the scripted `careful` agent (`looseends.py: run_scripted_day`, policy `careful`) holds in the
morning, re-queries each open item (ERP and inbox) in the afternoon, and completes what cleared. It passes 100% of
generated days. **Deliberately wrong solutions** `never_revisit` and `always_act` fail exactly where they should.
`python -m doublebooked.validate --all` runs these checks.

## Routine workload (companion DoubleBooked families, used as fillers)

`LB_PAID` (already paid yesterday), `LA_PAYRUN` (already in today's payment run), `LA_BANKFILE` (bank accepted file,
statement lags), `LA_RECURRING` (tonight's recurring job will post it), `LA_ICMIRROR` (IC partner side auto-mirrored),
`LA_PARKED` (parked + approved, queued for posting), `LB_TIMEOUT` (colleague's "timed-out" posting actually committed).
Each has a trap variant (acting duplicates) and a control variant (acting is required), with the request text identical.
