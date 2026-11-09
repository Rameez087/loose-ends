"""Render the same close package as realistic raw exports (SAP ALV lists, German user settings, bank CSV).

Numbers and policy semantics are identical to the clean package; only the representation changes.
"""
from __future__ import annotations

import os

from .generate import generate, POLICY, ACCOUNTS, r2


def de_num(x: float, trailing_minus=True) -> str:
    neg = x < 0
    s = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (s + "-" if trailing_minus else "-" + s) if neg else s


def de_date(iso: str) -> str:
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def acct(a: str) -> str:
    return a.zfill(10)


def alv(title, cols, rows, widths=None, page=12, subtotal_by=None, total_cols=(), user="FINOPS"):
    """SAP 'unconverted' list export: pipe-delimited, dashed rules, page headers repeated, * subtotals, ** total."""
    widths = widths or [max(len(c), *(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    line = "-" * (sum(widths) + len(widths) + 1)

    def fmt(vals):
        out = "|"
        for v, w in zip(vals, widths):
            v = str(v)
            out += (v.rjust(w) if v and (v[0].isdigit() or v[-1] == "-") and any(ch.isdigit() for ch in v) else v.ljust(w)) + "|"
        return out

    out, n, pg = [], 0, 1

    def header():
        nonlocal pg
        out.append(f"{'Meridian Components Inc.':<40}{title:^40}{'Page':>10}{pg:>5}")
        out.append(f"Company code 1000   Run date 31.03.2026  10:58:12   User {user}")
        out.append("")
        out.append(line)
        out.append(fmt(cols))
        out.append(line)
        pg += 1

    header()
    groups = {}
    order = []
    for r in rows:
        k = r[subtotal_by] if subtotal_by is not None else None
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(r)
    grand = {c: 0.0 for c in total_cols}
    for k in order:
        sub = {c: 0.0 for c in total_cols}
        for r in groups[k]:
            if n and n % page == 0:
                out.append(line)
                out.append("")
                header()
            out.append(fmt(r))
            n += 1
            for c in total_cols:
                v = parse_de(r[c])
                sub[c] += v
                grand[c] += v
        if subtotal_by is not None and total_cols:
            vals = ["*"] + [""] * (len(cols) - 1)
            vals[subtotal_by] = groups[k][0][subtotal_by]
            for c in total_cols:
                vals[c] = de_num(r2(sub[c]))
            out.append(fmt(vals))
    if total_cols:
        vals = ["**"] + [""] * (len(cols) - 1)
        for c in total_cols:
            vals[c] = de_num(r2(grand[c]))
        out.append(line)
        out.append(fmt(vals))
    out.append(line)
    return "\n".join(out) + "\n"


def parse_de(s: str) -> float:
    s = s.strip()
    neg = s.endswith("-")
    s = s.rstrip("-").replace(".", "").replace(",", ".")
    v = float(s) if s else 0.0
    return -v if neg else v


MESSY_NOTE = """
## Source files for this close
The registers in this folder are raw exports from the source systems, not prepared schedules:
- SAP list exports (`*.txt`) come from users with German settings (decimal comma, `.` as thousands separator,
  dates DD.MM.YYYY, negative amounts shown with a trailing minus, e.g. `1.234,56-`). They include report headers,
  repeated page headers, subtotal lines (`*`) and a grand total line (`**`). SAP checkbox fields show `X` for yes
  and are blank for no. Accounts are shown with leading zeros.
- In SAP, accumulated depreciation is displayed as a negative amount, and vendor (AP) open items carry a negative
  (credit) sign; amounts in the policy formulas refer to absolute values.
- The bank statement is the bank's CSV download: amounts are unsigned with a separate Debit/Credit indicator.
"""


def write_messy(seed: int, out: str, hygiene: bool = False):
    os.makedirs(out, exist_ok=True)
    files, truth = generate(seed)
    pol = POLICY.replace("`ap_invoices_april.csv`", "`ap_invoices_april.txt`") \
        .replace("`accruals_feb.csv`", "`accruals_feb.txt`").replace("`ap_invoices_march.csv`", "`ap_invoices_march.txt`") \
        .replace("`prepaids.csv`", "`prepaids.txt`").replace("`fixed_assets.csv`", "`fixed_assets.txt`") \
        .replace("`open_items_eur.csv`", "`open_items_eur.txt`").replace("`fx_rates.csv`", "`fx_rates.txt`") \
        .replace("`bank_statement_march.csv`", "`bank_statement_march.csv`").replace("`cash_book_march.csv`", "`cash_book_march.txt`") \
        .replace("`payroll_march.csv`", "`payroll_march.txt`") \
        .replace("with `auto_reverse = Y`", "flagged for automatic reversal") \
        .replace("with `auto_reverse = N`", "not flagged for automatic reversal") \
        .replace("with `bonus_eligible = Y`", "flagged as bonus-eligible")
    pol = pol.replace("using the closing rate in `fx_rates.txt` (USD per 1 EUR) for 2026-03-31",
                      "using the closing rate in `fx_rates.txt` (exchange rate type M, USD per 1 EUR) for 2026-03-31")
    with open(os.path.join(out, "policy.md"), "w") as f:
        f.write(pol + MESSY_NOTE)
    with open(os.path.join(out, "chart_of_accounts.txt"), "w") as f:
        f.write(alv("Chart of accounts", ["G/L Account", "Short text"], [[acct(k), v] for k, v in ACCOUNTS.items()],
                    page=40))

    rows = [[r["invoice_ref"], r["vendor"], de_date(r["received"]), de_date(r["invoice_date"]),
             de_date(r["service_from"]), de_date(r["service_to"]), acct(r["expense_account"]),
             de_num(float(r["net_amount"])), de_num(float(r["tax_amount"])), "USD"]
            for r in sorted(files["ap_invoices_april.csv"], key=lambda r: r["expense_account"])]
    txt = alv("Incoming invoices 01.04.-10.04.2026",
              ["Reference", "Vendor name", "Received", "Inv. date", "Serv. from", "Serv. to", "G/L Acct",
               "Net amount", "Tax amount", "Crcy"], rows, page=7, subtotal_by=6, total_cols=(7, 8))
    if hygiene:  # spool reprint: page 2 appears twice
        pages = txt.split("Meridian Components Inc.")
        if len(pages) > 2:
            pages.insert(3, pages[2])
            txt = "Meridian Components Inc.".join(pages)
    with open(os.path.join(out, "ap_invoices_april.txt"), "w") as f:
        f.write(txt)

    rows = [[r["accrual_id"], r["po_number"], r["vendor"], r["description"], acct(r["expense_account"]),
             de_num(float(r["amount"])), "X" if r["auto_reverse"] == "Y" else ""] for r in files["accruals_feb.csv"]]
    with open(os.path.join(out, "accruals_feb.txt"), "w") as f:
        f.write(alv("Accruals period 02/2026", ["Accrual", "Purch.Doc.", "Vendor name", "Text", "G/L Acct",
                                                 "Amount", "AutoRev"], rows, page=6, total_cols=(5,)))

    rows = [[r["doc_id"], r["po_number"], r["vendor"], de_date(r["posting_date"]), acct(r["expense_account"]),
             de_num(-float(r["amount"]))] for r in files["ap_invoices_march.csv"]]
    with open(os.path.join(out, "ap_invoices_march.txt"), "w") as f:
        f.write(alv("Vendor invoices posted 03/2026 (vendor line items)",
                    ["DocumentNo", "Purch.Doc.", "Vendor name", "Pstng Date", "G/L Acct", "Amount LC"], rows, page=8,
                    total_cols=(5,)))

    rows = [[r["prepaid_id"], r["description"], acct(r["expense_account"]), de_date(r["paid_date"]),
             de_num(float(r["amount"])), de_date(r["coverage_from"]), de_date(r["coverage_to"])]
            for r in sorted(files["prepaids.csv"], key=lambda r: r["expense_account"])]
    with open(os.path.join(out, "prepaids.txt"), "w") as f:
        f.write(alv("Prepaid expenses (account 0000001250)", ["Item", "Description", "Exp. acct", "Paid on", "Amount",
                                                               "Cover from", "Cover to"], rows, page=5,
                    subtotal_by=2, total_cols=(4,)))

    rows = [["1000", r["asset_id"], r["description"], de_date(r["in_service_date"]), de_num(float(r["cost"])),
             de_num(float(r["salvage_value"])), str(r["useful_life_months"]),
             de_num(-float(r["accumulated_depreciation_feb28"])), de_date(r["disposal_date"])]
            for r in files["fixed_assets.csv"]]
    if hygiene:
        import random as _r
        g = _r.Random(seed * 7 + 1)
        for k in range(4):
            cost = round(g.uniform(20000, 120000), 2)
            rows.append(["2000", f"FA-{2000 + k}", g.choice(["Press line", "Forklift", "Laptops batch"]),
                         de_date(f"2023-0{g.randrange(1, 9)}-1{g.randrange(0, 9)}"), de_num(cost), "0,00", "60",
                         de_num(-round(cost * g.uniform(0.3, 0.6), 2)), ""])
        rows.sort(key=lambda r: r[1])
    with open(os.path.join(out, "fixed_assets.txt"), "w") as f:
        f.write(alv("Asset Balances - key date 28.02.2026", ["CoCd", "Asset", "Asset description", "Cap.Date",
                                                              "Acquis.val.", "Scrap value", "Life(mo)", "Accum.dep.",
                                                              "Retirement"], rows, page=6, total_cols=(4, 7))
                .replace("Company code 1000 ", "Company codes 1000-2000" if hygiene else "Company code 1000 "))

    rows = [[r["item_id"], r["type"], r["counterparty"], de_num(-float(r["eur_amount"]) if r["type"] == "AP"
                                                                else float(r["eur_amount"])), "EUR",
             r["booked_rate"].replace(".", ","), de_date(r["booked_date"]), de_date(r["settled_date"])]
            for r in files["open_items_eur.csv"]]
    with open(os.path.join(out, "open_items_eur.txt"), "w") as f:
        f.write(alv("FC open items EUR (AP and AR)", ["Item", "Type", "Business partner", "Amt in FC", "Curr.",
                                                       "Exch.rate", "Doc. date", "Clearing"], rows, page=6))

    rows = []
    for r in files["fx_rates.csv"]:
        m = float(r["usd_per_eur"])
        typ = [("B", m - 0.005), ("M", m), ("G", m + 0.005)] if hygiene else [("M", m)]
        for t, v in typ:
            rows.append([de_date(r["date"]), t, "EUR", "USD", f"{v:.4f}".replace(".", ",")])
    with open(os.path.join(out, "fx_rates.txt"), "w") as f:
        f.write(alv("Exchange rates (USD per 1 EUR)" if hygiene else "Exchange rates type M (USD per 1 EUR)",
                    ["Valid from", "ExRt", "From", "To", "Rate"], rows, page=12))

    def bank_block(f, lo, hi):
        sel = [r for r in files["bank_statement_march.csv"] if lo <= r["date"] <= hi]
        f.write(f"Harbor Bank - Account statement export\nAccount;****4471\nPeriod;{de_date(lo).replace('.', '/')} - "
                f"{de_date(hi).replace('.', '/')}\n\nBooking date;Value date;Description;Amount;D/C;Currency\n")
        for r in sel:
            a = float(r["amount"])
            y, m, d = r["date"].split("-")
            f.write(f"{d}/{m}/{y};{d}/{m}/{y};{r['text']};{abs(a):.2f};{'D' if a < 0 else 'C'};USD\n")
        f.write(f"Number of transactions;{len(sel)}\n\n")
    with open(os.path.join(out, "bank_statement_march.csv"), "w") as f:
        if hygiene:  # two downloads pasted together, overlapping 14-20 March
            bank_block(f, "2026-03-01", "2026-03-20")
            bank_block(f, "2026-03-14", "2026-03-31")
        else:
            bank_block(f, "2026-03-01", "2026-03-31")

    rows = [[de_date(r["date"]), r["description"], de_num(float(r["amount"]))] for r in files["cash_book_march.csv"]]
    with open(os.path.join(out, "cash_book_march.txt"), "w") as f:
        f.write(alv("Cash journal 0001 - 03/2026", ["Pstng Date", "Text", "Amount"], rows, page=10, total_cols=(2,)))

    rows = [[r["employee_id"], de_num(float(r["base_salary_march"])), "X" if r["bonus_eligible"] == "Y" else "",
             de_date(r["hire_date"]), de_date(r["termination_date"])] for r in files["payroll_march.csv"]]
    with open(os.path.join(out, "payroll_march.txt"), "w") as f:
        f.write(alv("Payroll journal 03/2026 - base salary", ["Pers.No.", "Base salary", "BonusElig", "Entry",
                                                               "Leaving"], rows, page=8, total_cols=(1,)))
    return truth


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--hygiene", action="store_true")
    a = ap.parse_args()
    t = write_messy(a.seed, a.out, a.hygiene)
    if a.truth:
        json.dump(t, open(a.truth, "w"), indent=1)
