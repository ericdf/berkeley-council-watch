"""The Ordinances page: every ordinance the annotated agendas number, who brought it, and how each
reading was taken.

An ordinance is identified by the number the Clerk printed in an item's Action line ("Adopted first
reading of Ordinance No. 7,953–N.S."). Its first and second readings are usually at different meetings;
they are joined here by that number. An ordinance whose first reading came before this record began
(December 2024) appears with its second reading only.
"""
import re
from collections import Counter, defaultdict

from . import time_site

NUMBER = re.compile(r"Ordinance\s+No\.?\s*([\d,]+)\s*[–—-]?\s*N\.?S\.?", re.I)
READING = re.compile(r"(first|second)\s+reading", re.I)

ORIGINS = [
    ("voters", "Voters, at an election"),
    ("member", "Councilmembers and the Mayor"),
    ("City Manager", "City Manager"),
    ("City Attorney", "City Attorney"),
    ("commission", "Commissions and boards"),
    ("other", "Other"),
]


def origin(item):
    if re.search(r"Confirming the Results", item.get("heading") or "", re.I):
        return "voters"
    f = item.get("from") or ""
    if re.search(r"Councilmember|Mayor", f):
        return "member"
    if f.strip() in ("City Manager", "City Attorney"):
        return f.strip()
    if re.search(r"Commission|Board", f):
        return "commission"
    return "other"


def readings(item):
    """(ordinance number, reading) pairs named in an item's Action line. The reading is the nearest
    'first reading' or 'second reading' before the number, or 'adopted' when none is printed."""
    action = item.get("action") or ""
    out = []
    for m in NUMBER.finditer(action):
        before = list(READING.finditer(action, 0, m.start()))
        out.append((m.group(1).replace(",", ""), before[-1].group(1).lower() if before else "adopted"))
    return out


def collect(items):
    ords = defaultdict(dict)
    for it in sorted(items, key=lambda x: x["meeting_date"]):
        for num, reading in readings(it):
            ords[num].setdefault(reading, it)
    return ords


def on_consent(it):
    return bool(it) and "consent" in (it.get("section") or "").lower()


def divided(it):
    fm = (it or {}).get("final_motion")
    v = fm and fm["vote"]
    return bool(v) and not v["all_ayes"] and (v["noes"] or v["abstain"])


def page(items, h, item_roles):
    esc, link = h["esc"], h["link"]
    ords = collect(items)
    rows, counts = [], defaultdict(Counter)
    leads = Counter()
    for num in sorted(ords, key=int, reverse=True):
        r = ords[num]
        first, second, adopted = r.get("first"), r.get("second"), r.get("adopted")
        src = first or adopted or second
        o = origin(src)
        c = counts[o]
        c["n"] += 1
        c["early"] += first is None and adopted is None
        if first:
            c["consent1" if on_consent(first) else "action1"] += 1
        c["divided"] += any(divided(x) for x in (first, second, adopted))
        for member, b in item_roles.get(src["record_id"], []):
            if b == "lead":
                leads[member] += 1

        def cell(it, label):
            if not it:
                return '<span class="muted">before this record</span>' if label == "first" else ""
            where = "consent" if on_consent(it) else "action calendar"
            vote = time_site.vote_text(it)
            return (time_site.mlink(h, it["meeting_id"], h["fmt_date"](it["meeting_date"]))
                    + f'<br><span class="muted">Item {esc(it["item"])} · {where}' + (f" · {esc(vote)}" if vote else "")
                    + "</span>")
        roles = h["roles_html"](src["record_id"])
        brought = ("Voters; recorded when the Council confirmed the election results" if o == "voters"
                   else roles if o == "member" and roles else esc(src.get("from") or ""))
        topic = h["item_thread_label"](src)
        rows.append(f"<tr><td>No. {int(num):,}–N.S.</td><td>{esc(src['heading'])}"
                    + (f'<br><span class="muted">{topic}</span>' if topic else "")
                    + f"</td><td>{brought}</td>"
                    + (f'<td colspan="2">{cell(adopted, "adopted")} <span class="muted">(adopted in one step)</span></td>'
                       if adopted and not first and not second else f"<td>{cell(first, 'first')}</td><td>{cell(second, 'second')}</td>")
                    + "</tr>")
    total = sum(c["n"] for c in counts.values())
    summary = []
    for key, label in ORIGINS:
        c = counts.get(key)
        if not c:
            continue
        summary.append(f"<tr><th scope=\"row\">{esc(label)}</th><td>{c['n']}</td><td>{c['consent1']}</td>"
                       f"<td>{c['action1']}</td><td>{c['early']}</td><td>{c['divided']}</td></tr>")
    name = h["member_name"]
    lead_list = ", ".join(f"{link('../members/' + h['member_slug'](m) + '.html', name.get(m, m).split()[-1])} {n}"
                          for m, n in leads.most_common())
    body = [
        "<h1>Ordinances</h1>",
        "<p>An ordinance is a local law: it changes the Municipal Code, sets a fee or tax, or authorizes a lease or "
        "a contract that the Charter requires to be adopted by ordinance. The Council adopts most ordinances in two "
        "steps, a first reading and, at a later meeting, a second reading. This page lists every ordinance the "
        "annotated agendas give a number, who brought it, and how each reading was taken.</p>",
        f'<p class="muted">{esc(h["record_through"])} An ordinance whose first reading came before this record began, '
        "in December 2024, shows its second reading only. Who brought an ordinance is the From line of its first "
        "reading as printed; a ballot measure is counted under the voters who adopted it. Items on the consent calendar "
        "pass in the calendar's single vote, which is not repeated for each item here.</p>",
        '<h2 id="who">Who brought them</h2>',
        '<div class="table-wrap"><table><caption>Ordinances by who brought them</caption><thead><tr>'
        '<th scope="col">Brought by</th><th scope="col">Ordinances</th><th scope="col">First reading on consent</th>'
        '<th scope="col">First reading on the action calendar</th><th scope="col">First reading before this record</th>'
        '<th scope="col">A reading with a divided vote</th></tr></thead><tbody>'
        + "".join(summary)
        + f'<tr><th scope="row">All</th><td>{total}</td><td>{sum(c["consent1"] for c in counts.values())}</td>'
        f'<td>{sum(c["action1"] for c in counts.values())}</td><td>{sum(c["early"] for c in counts.values())}</td>'
        f'<td>{sum(c["divided"] for c in counts.values())}</td></tr></tbody></table></div>',
    ]
    if lead_list:
        body.append(f"<p>Lead authors of the ordinances members brought: {lead_list}.</p>")
    body += [
        '<h2 id="all">Every ordinance</h2>',
        '<div class="table-wrap"><table><caption>Ordinances, newest number first</caption><thead><tr>'
        '<th scope="col">Number</th><th scope="col">Title, as printed</th><th scope="col">Brought by</th>'
        '<th scope="col">First reading</th><th scope="col">Second reading</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>",
    ]
    return "\n".join(body)
