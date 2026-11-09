"""Month-end close generator (pilot).

python -m closebench.generate --seed 1 --out DIR   -> writes policy.md + registers (CSV) into DIR
and returns ground truth (expected net movement per account, per checkpoint).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import random
from decimal import Decimal, ROUND_HALF_UP

D = dt.date
PERIOD_START, PERIOD_END = D(2026, 3, 1), D(2026, 3, 31)


def r2(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def days_incl(a: D, b: D) -> int:
    return (b - a).days + 1


def overlap_days(a: D, b: D, c: D = PERIOD_START, d: D = PERIOD_END) -> int:
    lo, hi = max(a, c), min(b, d)
    return max(0, days_incl(lo, hi)) if lo <= hi else 0


ACCOUNTS = {
    "1100": "Bank - operating", "1210": "AR revaluation adjustment", "1250": "Prepaid expenses",
    "1500": "Fixed assets at cost", "1600": "Accumulated depreciation", "2000": "Trade payables",
    "2010": "AP revaluation adjustment", "2400": "Accrued expenses", "2450": "Accrued bonus",
    "4000": "Revenue", "4800": "Interest income", "6050": "Bonus expense", "6200": "Utilities",
    "6300": "Insurance", "6400": "Professional fees", "6500": "Software subscriptions",
    "6600": "Repairs and maintenance", "6700": "Depreciation", "6800": "Contract labour",
    "6900": "Marketing", "6950": "Bank charges", "7900": "Unrealised FX gain/loss",
}

POLICY = """# Meridian Components Inc. - Month-end close policy (company 1000, USD)

Applies to the March 2026 close (period 2026-03, 1 Mar - 31 Mar 2026). All amounts USD unless stated.
Round every individual calculated amount to cents (half up) before posting. Post closing entries dated 2026-03-31.

## 1. Accrued expenses (cut-off)
Goods and services received in March but invoiced later must be accrued at 31 March.
Use the April AP invoice register (`ap_invoices_april.csv`, invoices received 1-10 April). Each invoice has a
service period (`service_from` to `service_to`, both dates inclusive).
- Accrue the part of the invoice's net amount that relates to days in March, pro rata by calendar days:
  `net_amount x (service days falling in March) / (total service days)`.
- Invoices whose service period lies entirely after 31 March are not accrued.
- Debit the invoice's expense account, credit 2400 Accrued expenses.

## 2. Prior-month accruals
`accruals_feb.csv` lists accruals booked at the February close. Accruals with `auto_reverse = Y` were reversed
automatically on 1 March and need no action. Accruals with `auto_reverse = N` must be reversed manually
(debit 2400, credit the original expense account, full accrued amount) at the March close if the related vendor
invoice was posted in March (`ap_invoices_march.csv`, match on `po_number`). If the invoice has not been
posted yet, leave the accrual in place.

## 3. Prepaid expenses
`prepaids.csv` lists amounts capitalised to 1250 Prepaid expenses.
- Amortise each prepaid straight-line by calendar days over its coverage period (inclusive):
  March expense = `amount x (coverage days falling in March) / (total coverage days)`.
- Capitalisation threshold: a payment below 5,000.00 must not be held as a prepaid. If such an item was
  capitalised in March, expense the full amount in March instead of amortising it.
- Debit the item's expense account, credit 1250.

## 4. Depreciation
`fixed_assets.csv` is the asset register. Straight-line method:
monthly depreciation = `(cost - salvage_value) / useful_life_months`.
- Mid-month convention: an asset placed in service on day 1-15 of a month is depreciated for that whole month;
  placed in service on day 16 or later, depreciation starts the following month.
- Disposals: an asset disposed of on day 16 or later of a month is depreciated for that month; disposed of on
  day 1-15, no depreciation for the month of disposal.
- Never depreciate below salvage value: if the remaining depreciable amount
  (`cost - salvage_value - accumulated_depreciation_feb28`) is less than the monthly amount, depreciate only the
  remaining amount.
- Debit 6700, credit 1600.

## 5. Foreign-currency revaluation
`open_items_eur.csv` lists EUR-denominated AP and AR items. Revalue every item that is still open at 31 March
using the closing rate in `fx_rates.csv` (USD per 1 EUR) for 2026-03-31. The February revaluation was reversed
on 1 March, so measure the difference against each item's booked rate.
- AP item: USD difference = `eur_amount x (closing_rate - booked_rate)`; a positive difference increases the
  liability: debit 7900, credit 2010. A negative difference is a gain: debit 2010, credit 7900.
- AR item: USD difference = `eur_amount x (closing_rate - booked_rate)`; positive = gain: debit 1210,
  credit 7900; negative = loss: debit 7900, credit 1210.
- Items with `settled_date` on or before 31 March are not open.

## 6. Bank
Compare `bank_statement_march.csv` with the ERP cash book `cash_book_march.csv`. Bank charges (type FEE) and
interest received (type INT) that appear on the statement but not in the cash book (match on date and amount)
must be recorded: charges debit 6950 / credit 1100; interest debit 1100 / credit 4800. No entries are made for
timing differences (deposits in transit, unpresented cheques).

## 7. Bonus accrual
Accrue 8% of March base salary for every employee in `payroll_march.csv` with `bonus_eligible = Y` who is
employed on 31 March (`termination_date` is the employee's last day of employment). Employees hired during March: prorate the 8% accrual by calendar days employed in March
(hire date inclusive) / 31. Debit 6050, credit 2450.
"""

VENDORS = ["Halcyon Logistics", "Brightwell Packaging", "Norvik Steel", "Kestrel Electronics", "Atlas Fasteners",
           "Corvane Plastics", "Pinecrest Office Supply", "Tidewater Freight", "Lumen Industrial Gas",
           "Orchard IT Services", "Sable Chemicals", "Vantage Tooling", "Greyfield Bearings", "Marlow Castings",
           "Quayside Legal LLP", "Aldridge & Finch CPAs", "Northgate Facilities", "Cobalt Cloud Inc."]


def _rng(seed):
    return random.Random(int(hashlib.sha256(f"close|{seed}".encode()).hexdigest()[:16], 16))


def amt(rng, lo, hi):
    return r2(rng.uniform(lo, hi))


def rand_date(rng, a: D, b: D) -> D:
    return a + dt.timedelta(days=rng.randrange((b - a).days + 1))


def generate(seed: int):
    rng = _rng(seed)
    files, truth = {}, {}

    # ---- 1 accrual cut-off ------------------------------------------------
    rows, acc = [], {}
    exp_accts = ["6200", "6400", "6600", "6900"]
    kinds = ["march_full", "span_mar_apr", "span_mar_may", "april_only", "april_only", "span_mar_apr",
             "march_full", "april_may", "span_mar_apr", "march_full", "april_only", "span_feb_apr"]
    rng.shuffle(kinds)
    for k, kind in enumerate(kinds):
        a = rng.choice(exp_accts)
        net = amt(rng, 900, 24000)
        if kind == "march_full":
            s = rand_date(rng, D(2026, 3, 1), D(2026, 3, 20)); e = rand_date(rng, s, D(2026, 3, 31))
        elif kind == "span_mar_apr":
            s = rand_date(rng, D(2026, 3, 2), D(2026, 3, 28)); e = s + dt.timedelta(days=rng.choice([29, 30]))
        elif kind == "span_mar_may":
            s = rand_date(rng, D(2026, 3, 5), D(2026, 3, 25)); e = rand_date(rng, D(2026, 5, 1), D(2026, 5, 20))
        elif kind == "span_feb_apr":  # Feb part belongs to Feb (already a Feb problem); March part must be accrued
            s = rand_date(rng, D(2026, 2, 10), D(2026, 2, 25)); e = rand_date(rng, D(2026, 4, 2), D(2026, 4, 12))
        elif kind == "april_only":
            s = rand_date(rng, D(2026, 4, 1), D(2026, 4, 10)); e = s + dt.timedelta(days=rng.choice([0, 29, 30]))
        else:
            s = D(2026, 4, 1); e = D(2026, 5, 31)
        tot = days_incl(s, e)
        mar = overlap_days(s, e)
        accrual = r2(net * mar / tot) if mar else 0.0
        acc[a] = r2(acc.get(a, 0) + accrual)
        rows.append({"invoice_ref": f"INV-{rng.randrange(10000, 99999)}", "vendor": rng.choice(VENDORS),
                     "received": str(rand_date(rng, D(2026, 4, 1), D(2026, 4, 10))),
                     "invoice_date": str(rand_date(rng, D(2026, 3, 31), D(2026, 4, 8))),
                     "service_from": str(s), "service_to": str(e), "net_amount": f"{net:.2f}",
                     "tax_amount": f"{r2(net * 0.07):.2f}", "expense_account": a})
    files["ap_invoices_april.csv"] = rows
    truth["CP1_cutoff_accruals"] = {a: v for a, v in acc.items() if v}

    # ---- 2 Feb accruals -----------------------------------------------------
    feb, mar_ap, rev = [], [], 0.0
    for k in range(9):
        po = f"PO-{rng.randrange(40000, 49999)}"
        a_amt = amt(rng, 1500, 15000)
        auto = rng.random() < 0.5
        invoiced = rng.random() < 0.7
        feb.append({"accrual_id": f"ACR-02-{k + 1:02d}", "po_number": po, "vendor": rng.choice(VENDORS),
                    "description": rng.choice(["Contract labour - line 3", "Temp staff - warehouse",
                                               "Contract engineers", "Agency staff - QA"]),
                    "expense_account": "6800", "amount": f"{a_amt:.2f}", "auto_reverse": "Y" if auto else "N"})
        if invoiced:
            mar_ap.append({"doc_id": f"5100{rng.randrange(10000, 99999)}", "po_number": po,
                           "vendor": feb[-1]["vendor"], "posting_date": str(rand_date(rng, D(2026, 3, 2), D(2026, 3, 30))),
                           "amount": f"{r2(a_amt * rng.uniform(0.97, 1.05)):.2f}", "expense_account": "6800"})
        if not auto and invoiced:
            rev += a_amt
    for k in range(8):  # unrelated March invoices
        mar_ap.append({"doc_id": f"5100{rng.randrange(10000, 99999)}", "po_number": f"PO-{rng.randrange(40000, 49999)}",
                       "vendor": rng.choice(VENDORS), "posting_date": str(rand_date(rng, D(2026, 3, 2), D(2026, 3, 30))),
                       "amount": f"{amt(rng, 500, 9000):.2f}", "expense_account": rng.choice(["6200", "6600", "6900"])})
    rng.shuffle(mar_ap)
    files["accruals_feb.csv"] = feb
    files["ap_invoices_march.csv"] = mar_ap
    truth["CP2_feb_accrual_reversal"] = {"6800": -r2(rev)}

    # ---- 3 prepaids ---------------------------------------------------------
    pre, pe = [], {}
    specs = [("6300", "Property insurance", D(2025, 7, 1), D(2026, 6, 30)),
             ("6300", "Product liability insurance", D(2025, 10, 15), D(2026, 10, 14)),
             ("6500", "ERP licence - annual", D(2026, 1, 1), D(2026, 12, 31)),
             ("6500", "CAD seats - annual", D(2026, 3, 15), D(2027, 3, 14)),
             ("6300", "Cyber insurance", D(2026, 3, 10), D(2027, 3, 9)),
             ("6500", "Design tool - 6 months", D(2026, 3, 1), D(2026, 8, 31)),
             ("6500", "Monitoring add-on", D(2026, 3, 1), D(2027, 2, 28)),  # small item -> threshold
             ("6300", "Vehicle insurance", D(2025, 4, 1), D(2026, 3, 31))]
    for k, (a, desc, s, e) in enumerate(specs):
        if desc == "Monitoring add-on":
            amount = amt(rng, 2400, 4800)
            paid = D(2026, 3, rng.randrange(2, 12))
        else:
            amount = amt(rng, 9000, 60000)
            paid = s if s.month == 3 else s - dt.timedelta(days=rng.randrange(1, 20))
        if amount < 5000 and paid.month == 3:
            x = amount
        else:
            x = r2(amount * overlap_days(s, e) / days_incl(s, e))
        pe[a] = r2(pe.get(a, 0) + x)
        pre.append({"prepaid_id": f"PP-{k + 1:03d}", "description": desc, "expense_account": a,
                    "paid_date": str(paid), "amount": f"{amount:.2f}", "coverage_from": str(s), "coverage_to": str(e)})
    rng.shuffle(pre)
    files["prepaids.csv"] = pre
    truth["CP3_prepaids"] = pe

    # ---- 4 depreciation ------------------------------------------------------
    fa, dep = [], 0.0
    for k in range(14):
        cost = amt(rng, 8000, 250000)
        life = rng.choice([36, 60, 60, 84, 120])
        salv = r2(cost * rng.choice([0, 0, 0.05, 0.1]))
        kind = rng.choice(["normal"] * 6 + ["add_early", "add_late", "disp_early", "disp_late", "nearly_done",
                                            "done", "add_on15", "disp_on16"])
        monthly = r2((cost - salv) / life)
        in_service = rand_date(rng, D(2021, 1, 1), D(2025, 6, 30))
        disposed = ""
        months_before = (2026 - in_service.year) * 12 + (2 - in_service.month) + (1 if in_service.day <= 15 else 0)
        accum = r2(min(cost - salv, monthly * max(0, months_before)))
        if kind == "add_early":
            in_service = D(2026, 3, rng.randrange(1, 15)); accum = 0.0
        if kind == "add_on15":
            in_service = D(2026, 3, 15); accum = 0.0
        if kind == "add_late":
            in_service = D(2026, 3, rng.randrange(16, 31)); accum = 0.0
        if kind in ("disp_early", "disp_late", "disp_on16"):
            disposed = str(D(2026, 3, rng.randrange(2, 15) if kind == "disp_early" else
                             (16 if kind == "disp_on16" else rng.randrange(17, 31))))
        if kind == "nearly_done":
            accum = r2(cost - salv - r2(monthly * rng.uniform(0.2, 0.8)))
        if kind == "done":
            accum = r2(cost - salv)
        remaining = r2(cost - salv - accum)
        m = monthly
        if kind == "add_late":
            m = 0
        if kind == "disp_early":
            m = 0
        m = min(m, remaining) if m else 0
        dep += m
        fa.append({"asset_id": f"FA-{1000 + k}", "description": rng.choice(["CNC mill", "Forklift", "Laptops batch",
                   "Injection mould", "Server rack", "Packaging line", "Delivery van", "Test bench"]),
                   "in_service_date": str(in_service), "cost": f"{cost:.2f}", "salvage_value": f"{salv:.2f}",
                   "useful_life_months": life, "accumulated_depreciation_feb28": f"{accum:.2f}",
                   "disposal_date": disposed})
    files["fixed_assets.csv"] = fa
    truth["CP4_depreciation"] = {"6700": r2(dep)}

    # ---- 5 FX -----------------------------------------------------------------
    rates, r = [], 1.0780
    for d in range(1, 32):
        day = D(2026, 3, d)
        r = round(r + rng.uniform(-0.004, 0.004), 4)
        if day.weekday() < 5:
            rates.append({"date": str(day), "usd_per_eur": f"{r:.4f}"})
    close = float(rates[-1]["usd_per_eur"])
    files["fx_rates.csv"] = rates
    items, fxp = [], 0.0
    for k in range(10):
        typ = rng.choice(["AP", "AP", "AR"])
        eur = amt(rng, 3000, 90000)
        booked = round(rng.uniform(1.05, 1.11), 4)
        settled = str(rand_date(rng, D(2026, 3, 3), D(2026, 3, 30))) if rng.random() < 0.25 else ""
        if k == 0:
            settled = "2026-04-02"
        items.append({"item_id": f"{typ}-EUR-{k + 1:03d}", "type": typ, "counterparty": rng.choice(VENDORS),
                      "eur_amount": f"{eur:.2f}", "booked_rate": f"{booked:.4f}", "booked_date": "2026-0" +
                      f"{rng.randrange(1, 4)}-{rng.randrange(1, 28):02d}", "settled_date": settled})
        if settled and settled <= "2026-03-31":
            continue
        diff = r2(eur * (close - booked))
        fxp += diff if typ == "AP" else -diff  # positive = loss (debit 7900)
    files["open_items_eur.csv"] = items
    truth["CP5_fx_revaluation"] = {"7900": r2(fxp)}

    # ---- 6 bank ---------------------------------------------------------------
    stmt, book = [], []
    fees = ints = 0.0
    for k in range(40):
        d = str(rand_date(rng, D(2026, 3, 2), D(2026, 3, 31)))
        t = rng.choice(["PAYMENT", "PAYMENT", "RECEIPT", "RECEIPT", "FEE", "INT"] if k > 6 else ["FEE", "INT"])
        a = amt(rng, 15, 180) if t == "FEE" else (amt(rng, 40, 900) if t == "INT" else amt(rng, 500, 50000))
        sign = -1 if t in ("PAYMENT", "FEE") else 1
        stmt.append({"date": d, "type": t, "amount": f"{sign * a:.2f}", "text": {"FEE": "BANK CHARGES",
                     "INT": "CREDIT INTEREST", "PAYMENT": "ACH OUT", "RECEIPT": "CUSTOMER RECEIPT"}[t]})
        recorded = rng.random() < (0.45 if t in ("FEE", "INT") else 0.95)
        if recorded:
            book.append({"date": d, "description": stmt[-1]["text"].title(), "amount": f"{sign * a:.2f}"})
        elif t == "FEE":
            fees += a
        elif t == "INT":
            ints += a
    for k in range(3):  # timing differences: in book, not in bank
        book.append({"date": "2026-03-31", "description": rng.choice(["Cheque 10442", "Deposit - lockbox"]),
                     "amount": f"{rng.choice([-1, 1]) * amt(rng, 800, 9000):.2f}"})
    stmt.sort(key=lambda x: x["date"]); book.sort(key=lambda x: x["date"])
    files["bank_statement_march.csv"] = stmt
    files["cash_book_march.csv"] = book
    truth["CP6_bank"] = {"6950": r2(fees), "4800": -r2(ints)}

    # ---- 7 bonus --------------------------------------------------------------
    pay, bon = [], 0.0
    for k in range(16):
        sal = amt(rng, 4200, 14000)
        elig = rng.random() < 0.7
        hire = rand_date(rng, D(2018, 1, 1), D(2025, 12, 31))
        term = ""
        kind = rng.choice(["n"] * 10 + ["hire_mar", "term_mar", "term_31"])
        if kind == "hire_mar":
            hire = D(2026, 3, rng.randrange(2, 28))
        if kind == "term_mar":
            term = str(D(2026, 3, rng.randrange(5, 30)))
        if kind == "term_31":
            term = "2026-03-31"
        pay.append({"employee_id": f"E{2000 + k}", "base_salary_march": f"{sal:.2f}",
                    "bonus_eligible": "Y" if elig else "N", "hire_date": str(hire), "termination_date": term})
        if not elig or (term and term < "2026-03-31"):
            continue
        days = overlap_days(max(hire, PERIOD_START), PERIOD_END)
        x = r2(sal * 0.08 * (days / 31 if hire >= PERIOD_START else 1))
        bon += x
    files["payroll_march.csv"] = pay
    truth["CP7_bonus"] = {"6050": r2(bon)}
    return files, truth


def write(seed, out):
    os.makedirs(out, exist_ok=True)
    files, truth = generate(seed)
    with open(os.path.join(out, "policy.md"), "w") as f:
        f.write(POLICY)
    with open(os.path.join(out, "chart_of_accounts.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["account", "name"]); [w.writerow([k, v]) for k, v in ACCOUNTS.items()]
    for name, rows in files.items():
        with open(os.path.join(out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    return truth


def grade(entries, truth, tol=1.00):
    net = {}
    bad = []
    for e in entries:
        dr = sum(float(l.get("debit") or 0) for l in e["lines"])
        cr = sum(float(l.get("credit") or 0) for l in e["lines"])
        if abs(dr - cr) > 0.005:
            bad.append(e)
            continue
        for l in e["lines"]:
            a = str(l["account"])
            net[a] = r2(net.get(a, 0) + float(l.get("debit") or 0) - float(l.get("credit") or 0))
    res = {}
    for cp, exp in truth.items():
        got = {a: net.get(a, 0.0) for a in exp}
        ok = all(abs(got[a] - v) <= tol for a, v in exp.items())
        res[cp] = {"pass": ok, "expected": exp, "actual": got}
    return {"checkpoints": res, "passed": sum(r["pass"] for r in res.values()), "n": len(res),
            "unbalanced_entries": len(bad), "net": net}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    a = ap.parse_args()
    t = write(a.seed, a.out)
    if a.truth:
        with open(a.truth, "w") as f:
            json.dump(t, f, indent=1)
    print(json.dumps(t, indent=1))
