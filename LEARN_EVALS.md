# How this eval was built: a guide to eval design, using Loose Ends as the example

## 1. An eval is tasks + a grader + evidence
- **Task:** what the model is asked to do (`looseends.build_day`: a workday of requests in a seeded ERP).
- **Grader:** code that decides pass or fail without a human (`grader.py`).
- **Evidence:** saved runs that show *why* the score is what it is (`results/`).

## 2. Find a failure before you build a benchmark
The most common mistake is building a polished eval that the model aces. We wrote cheap *probes* first and ran them
blind. Opus passed about 20 hypotheses (56/56 trap items, 56/56 close checkpoints) before one broke it. Keep those
negative results: they show judges you didn't cherry-pick, and they mark where the real boundary sits.

## 3. Grade the outcome, not the words
We never read the agent's prose. After it stops, we run the company's night jobs (`run_end_of_day`) and inspect
the books: *is the invoice paid exactly once? Is the IBAN changed? Is account 6450 up by the right amount?* Any valid
path passes, so a model that solves the problem differently is never wrongly failed. This is the τ-bench idea
(final database state), applied to finance.

## 4. Minimal pairs kill shortcut strategies
Every `clear` day has a `hold` twin with the same text, and only the hidden colleague action differs. "Always act" fails
the hold day and "never revisit" fails the clear day. Pair accuracy is the metric a lazy strategy can't game.

## 5. Test the grader before you test the model
Scripted agents (`careful`, `never_revisit`, `always_act`) have known-correct scores. If the grader scores them
wrong, the grader is broken. `python -m doublebooked.validate --all` runs this over 600+ generated scenarios.
That's how you can claim "no false passes or false fails."

## 6. Procedural generation stops memorisation
Vendors, amounts, references and IDs come from a seed, so every seed is a fresh instance of the same task. It's also
reproducible: the same seed always gives the same world.

## 7. Blind runs
The subject model must not know it is being evaluated. Our agents got a neutral operating brief and a CLI. Tool
descriptions are neutral (`erp.py: TOOLS`), and nothing says "check for duplicates" or "follow up".

## 8. Explain the failure with an ablation
A score alone says *that* something fails. An ablation says *why*:
- **Channel ablation:** the same blocker cleared by email gives 24/24, cleared silently in the ERP gives 14/24. So the cause is
  *where the signal lives*, not difficulty.
- **Prompt ablation:** one "own your open items" sentence moves 58% to 83%. The capability is there, and the default habit is the problem.
- **Taxonomy from logs:** `checked_inbox_only` for all 10 drops gives the mechanism, deterministically.

## 9. Report uncertainty honestly
Small samples give wide confidence intervals (Wilson 95%, `score.py`). Say so, show the CI, and make re-running one command.

## 10. Make it reproducible in a clean environment
Stdlib-only Python, one runner for Anthropic/OpenAI/OpenRouter, an offline scripted mode that needs no key, and every
run record saved as JSON.

**Further reading:** τ-bench / τ²-bench (Sierra), Anthropic's *Demystifying evals for AI agents*, SemiAnalysis GDPx
(Nov 2026), FINCH (ACL 2026).
