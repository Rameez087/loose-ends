# Results

All runs blind; grading deterministic. Regenerate: `python -m doublebooked.report results/loose_ends`.

## Loose Ends (headline)

| model | blocker cleared via | ownership line | days | clear: loose ends closed | hold: correctly held | routine items | failure categories |
|---|---|---|---|---|---|---|---|
| haiku | email notification | no | 3 | 0/6 (0%, CI 0-39) | 3/3 (100%, CI 44-100) | 9/9 (100%, CI 70-100) | never_rechecked=6 |
| haiku | silent (system of record) | no | 1 | 0/3 (0%, CI 0-56) | - | 2/3 (67%, CI 21-94) | never_rechecked=3 |
| opus | email notification | no | 6 | 12/12 (100%, CI 76-100) | 6/6 (100%, CI 61-100) | 18/18 (100%, CI 82-100) | - |
| opus | email notification | yes | 2 | 6/6 (100%, CI 61-100) | - | 6/6 (100%, CI 61-100) | - |
| opus | email notification, no inbox sentence | no | 4 | 12/12 (100%, CI 76-100) | - | 12/12 (100%, CI 76-100) | - |
| opus | silent (system of record) | no | 10 | 14/24 (58%, CI 39-76) | 6/6 (100%, CI 61-100) | 30/30 (100%, CI 89-100) | checked_inbox_only=10 |
| opus | silent (system of record) | yes | 2 | 5/6 (83%, CI 44-97) | - | 6/6 (100%, CI 61-100) | checked_inbox_only=1 |
| sonnet | email notification | no | 3 | 6/6 (100%, CI 61-100) | 3/3 (100%, CI 44-100) | 9/9 (100%, CI 70-100) | - |
| sonnet | silent (system of record) | no | 2 | 3/6 (50%, CI 19-81) | - | 6/6 (100%, CI 61-100) | never_rechecked=3 |

**Per blocker family (clear days only):**

| model | channel | ownership line | B_APPROVAL | B_GR | B_BANK | B_INFO |
|---|---|---|---|---|---|---|
| haiku | email notification | no | 0/2 | 0/2 | 0/2 | - |
| haiku | silent (system of record) | no | 0/1 | 0/1 | - | 0/1 |
| opus | email notification | no | 3/3 | 3/3 | 2/2 | 4/4 |
| opus | email notification | yes | 2/2 | 2/2 | 1/1 | 1/1 |
| opus | email notification, no inbox sentence | no | 2/2 | 4/4 | 3/3 | 3/3 |
| opus | silent (system of record) | no | 4/6 | 4/6 | 0/6 | 6/6 |
| opus | silent (system of record) | yes | 1/1 | 2/2 | 0/1 | 2/2 |
| sonnet | email notification | no | 1/1 | 2/2 | 2/2 | 1/1 |
| sonnet | silent (system of record) | no | 1/2 | 1/2 | 0/1 | 1/1 |

**Guide-format summary (blocked requests only; task = blocker family, trials = seeded instances, clear + hold days pooled):**

| model (harness: CLI agent, default temperature) | channel | ownership line | trials per task (min-max) | pass rate | pass^k (share of tasks with every trial passed) |
|---|---|---|---|---|---|
| haiku | email notification | no | 3-3 | 3/9 (33%, CI 12-65) | 0/3 |
| haiku | silent (system of record) | no | 1-1 | 0/3 (0%, CI 0-56) | 0/3 |
| opus | email notification | no | 3-6 | 18/18 (100%, CI 82-100) | 4/4 |
| opus | email notification | yes | 1-2 | 6/6 (100%, CI 61-100) | 4/4 |
| opus | email notification, no inbox sentence | no | 2-4 | 12/12 (100%, CI 76-100) | 4/4 |
| opus | silent (system of record) | no | 7-8 | 20/30 (67%, CI 49-81) | 1/4 |
| opus | silent (system of record) | yes | 1-2 | 5/6 (83%, CI 44-97) | 3/4 |
| sonnet | email notification | no | 1-3 | 9/9 (100%, CI 70-100) | 4/4 |
| sonnet | silent (system of record) | no | 1-2 | 3/6 (50%, CI 19-81) | 1/4 |

Pilot (system prompt without inbox sentence, no B_INFO item, email signals; Opus, 2 days): 1 of 4 blocked items closed — see `results/traps/pilot_follow_opus/`.

## Failure search: trap trials (all blind)

| suite | model | items passed |
|---|---|---|
| Integrity probes, written rules | opus | 6/6 |
| Queues + timeouts | haiku | 24/24 |
| DoubleBooked 10-request queues | opus | 20/20 |
| DoubleBooked single requests (traps) | opus | 7/7 |
| Queues + timeouts | sonnet | 23/24 |
| Own 504-timeout retries | opus | 4/4 |
| Reasoning probes (self-invalidation, partial runs, held jobs, portal wire) | opus | 13/13 |
| Integrity probes, unwritten norms | opus | 6/6 |
| Month-end close (clean / SAP export / no-code / hygiene), 8 packages | opus | 56/56 checkpoints |
