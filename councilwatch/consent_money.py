"""Money on the consent calendar: every consent item with a printed amount, sorted by what the amount is.

The amount is the one the Council time data already carries for each consent item: the largest figure
under Financial Implications, otherwise the first figure in the Recommendation, as printed. Printed
figures are not all City spending. A resolution supporting a state bond prints the bond's size; the
appropriations limit is a legal ceiling; a bid list names work not yet awarded; a grant application names
money the City may receive. Each item is sorted into one kind by the rules below, and a reviewed file
(data/review/council-time/consent_money.json) overrides the rules where they are wrong. Only the kinds
that authorize City spending are added into the spending total.
"""
import json
import os
import re
from collections import defaultdict

from . import ordinance_site

KINDS = [
    # key, label, counted in the spending total, note
    ("contracts", "Contracts, purchases and leases", True,
     "Contracts, amendments, purchase orders and leases. A contract amount is usually a not-to-exceed figure, "
     "often over several years; an amendment may print the amount added or the new total."),
    ("grants_out", "Grants, allocations and housing funds to others", True,
     "Money the City gives or lends: grant allocations, Housing Trust Fund reservations, predevelopment funds "
     "and loan changes."),
    ("appropriations", "Budget amendments", True,
     "Amendments to the Annual Appropriations Ordinance, each counted once, on its net appropriation."),
    ("temporary", "Temporary appropriations", False,
     "The spending authority adopted each June to carry the City from July 1 until the budget is adopted, "
     "which then replaces it. Counting it with the budget would count the same spending twice."),
    ("staffing", "Positions and pay", True, "Salaries set for appointed directors and new job classifications."),
    ("incoming", "Grants and revenue the City receives", False,
     "Grant acceptances, revenue contracts, donations and property sales: money coming in."),
    ("applications", "Grant applications", False, "Money the City has applied for and may or may not receive."),
    ("planned", "Bids to be issued", False,
     "The lists of bids and requests for proposals staff plan to issue. No contract exists yet; awarded "
     "contracts come back to the Council."),
    ("referrals", "Budget referrals", False,
     "Requests to consider funding in the next budget. A referral spends nothing until the budget appropriates it."),
    ("not_spending", "Figures that are not City spending", False,
     "Figures printed in the item that the City is not spending: a state bond named in a resolution of support, "
     "the State-required appropriations limit, a threshold written into a rule, a revenue estimate in a referral."),
    ("repeat", "Repeats of an amount already listed", False,
     "An item whose action the Clerk records under its companion item, and second readings of ordinances "
     "whose first reading is listed."),
    ("other", "Other", False, "Items the rules did not sort and no review has assigned."),
]
KIND = {k: (label, counted, note) for k, label, counted, note in KINDS}

RULES = [
    ("not_spending", r"appropriations limit|in support of|bond act|recommendations for the formulation|poll question"),
    ("referrals", r"budget referral|^refer\b|^referral|^defer .*referral"),
    ("planned", r"formal bid solicitations|^request for proposals"),
    ("temporary", r"temporary appropriations"),
    ("appropriations", r"annual appropriations ordinance"),
    ("applications", r"grant application|funding application|^application|application for|joint .* application"),
    ("incoming", r"revenue|accept|donation|sale of real property|^grant award"),
    ("grants_out", r"housing trust fund|funding reservation|reserving|predevelopment|loan|ownership transfer|"
                   r"grant allocation|funding recommendations"),
    ("staffing", r"classification and salary|^appointment of director"),
    ("contracts", r"contract|purchase order|agreement|lease|purchase|piggyback"),
]


def rule_kind(heading):
    h = heading.lower()
    return next((k for k, r in RULES if re.search(r, h)), "other")


def load_review(review_dir):
    path = os.path.join(review_dir, "consent_money.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["record_id"]: r for r in json.load(f)["items"]}


def classify(consent, items, review):
    """Each consent item with an amount, as (kind, item, how) where how is 'rule' or 'reviewed'."""
    by_id = {x["record_id"]: x for x in items}
    first_read = {num for x in items for num, reading in ordinance_site.readings(x) if reading == "first"}
    out = []
    for c in consent:
        if not c.get("amount") or re.search(r"relinquish", c["heading"], re.I):
            continue
        if c["record_id"] in review:
            out.append((review[c["record_id"]]["kind"], c, "reviewed"))
            continue
        it = by_id.get(c["record_id"]) or {}
        if re.search(r"See action for Item", it.get("action") or "", re.I):
            out.append(("repeat", c, "rule"))
            continue
        second = [n for n, r in ordinance_site.readings(it) if r == "second"]
        if second and all(n in first_read for n in second) and not c.get("aao"):
            out.append(("repeat", c, "rule"))
            continue
        out.append((rule_kind(c["heading"]), c, "rule"))
    return out


def money(x):
    if x >= 1e6:
        return f"${x / 1e6:,.1f} million"
    return f"${x:,.0f}"


def page(consent, items, h, review_dir, thread_link):
    esc = h["esc"]
    rows = classify(consent, items, load_review(review_dir))
    groups = defaultdict(list)
    for kind, c, how in rows:
        groups[kind].append((c, how))
    years = sorted({c["meeting_date"][:4] for _, c, _ in rows})
    spent = [(k, c) for k, c, _ in rows if KIND[k][1]]
    total = sum(c["amount"] for _, c in spent)
    n_consent = len(consent)
    summary = []
    for k, label, counted, note in KINDS:
        g = groups.get(k)
        if not g:
            continue
        by_year = defaultdict(float)
        for c, _ in g:
            by_year[c["meeting_date"][:4]] += c["amount"]
        summary.append(f'<tr><th scope="row"><a href="#{k}">{esc(label)}</a></th><td>{len(g)}</td>'
                       + "".join(f"<td>{money(by_year[y]) if by_year[y] else ''}</td>" for y in years)
                       + f'<td>{money(sum(c["amount"] for c, _ in g))}</td><td>{"Yes" if counted else "No"}</td></tr>')
    body = [
        "<h1>Money on the consent calendar</h1>",
        f"<p>The consent calendar is adopted in one vote, without discussion of its items. Of the {n_consent:,} "
        f"consent items in this record, {len(rows):,} print an amount of money. The amounts that authorize City "
        f"spending (contracts, grants and housing funds to others, budget amendments, and positions) add up to "
        f"<strong>{money(total)}</strong> across {len(spent):,} items, as printed.</p>",
        f'<p class="muted">{esc(h["record_through"])} An amount is as printed in the agenda: the largest figure under '
        "Financial Implications, otherwise the first figure in the Recommendation. Printed amounts are authorized "
        "maximums, often over several years; they are not amounts spent. Relinquishments of Council office funds "
        "are routine items and are not listed. Each item links to its meeting, where the agenda shows the figure in "
        "context. How each item is sorted is shown beside it: by rule from its title, or by review.</p>",
        '<h2 id="summary">By kind</h2>',
        '<div class="table-wrap"><table><caption>Consent items with a printed amount, by what the amount is</caption>'
        '<thead><tr><th scope="col">Kind</th><th scope="col">Items</th>'
        + "".join(f'<th scope="col">{y}{" (December)" if y == "2024" else ""}</th>' for y in years)
        + '<th scope="col">All</th><th scope="col">In the spending total</th></tr></thead><tbody>'
        + "".join(summary) + "</tbody></table></div>",
    ]
    for k, label, counted, note in KINDS:
        g = groups.get(k)
        if not g:
            continue
        trs = []
        for c, how in sorted(g, key=lambda x: (x[0]["meeting_date"], x[0]["item"]), reverse=True):
            topic = thread_link(c["record_id"])
            trs.append(f"<tr><td>{h['mlink'](h, c['meeting_id'], h['fmt_date'](c['meeting_date']))}"
                       f'<br><span class="muted">Item {esc(c["item"])}</span></td>'
                       f"<td>{esc(c['heading'])}<br><span class=\"muted\">{esc(c['from'] or '')}"
                       + (f" · {topic}" if topic else "") + "</span></td>"
                       f'<td class="num">{money(c["amount"])}</td><td class="muted">{how}</td></tr>')
        body.append(f'<h2 id="{k}">{esc(label)}</h2><p>{esc(note)} {len(g)} items, '
                    f'{money(sum(c["amount"] for c, _ in g))}.</p>'
                    f'<details><summary>Show the {len(g)} items</summary><div class="table-wrap"><table>'
                    f'<caption>{esc(label)}</caption><thead><tr><th scope="col">Meeting</th>'
                    '<th scope="col">Item, as printed</th><th scope="col">Amount</th><th scope="col">Sorted by</th>'
                    f'</tr></thead><tbody>{"".join(trs)}</tbody></table></div></details>')
    return "\n".join(body)
