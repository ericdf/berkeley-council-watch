"""Member pages and the Council-wide view: what each member brought to the Council, how they voted,
what they moved, and when they were recorded absent. Counts only, by kind, never combined into a
score; every count sits beside the range across the Council. Votes and authorship are as the City
Clerk printed them in the annotated agendas (archive L2), from the first meeting of the Council
seated in December 2024.
"""
import statistics
from collections import Counter, defaultdict

SEATED = "2024-12-10"
BINS = [
    ("lead", "Lead author", "The only author named, or the author whose office the agenda gives as the contact"),
    ("joint", "Joint author", "One of several authors or co-authors, where the agenda does not name a lead"),
    ("listed", "Co-sponsor, on the agenda as posted", "Named as a co-sponsor in the agenda's From line"),
    ("at_meeting", "Co-sponsor, added at the meeting", "The annotated agenda records the addition, and the transcript shows it at the meeting"),
    ("later", "Co-sponsor, added later; when is not stated", "The annotated agenda records the addition; the transcript does not show when it was made"),
    ("unlabeled", "Named, role not printed", "Named in the From line with no role"),
]
VOTE_COLS = [("aye", "Aye"), ("all_ayes", "“All Ayes”"), ("no", "No"), ("abstain", "Abstain"), ("absent", "Absent"), ("recused", "Recused")]
CELL = {"aye": ("Y", "Aye"), "no": ("N", "No"), "abstain": ("A", "Abstain"), "absent": ("–", "Absent"), "recused": ("R", "Recused"),
        "all_ayes": ("Y*", "All Ayes"), None: ("", "Not recorded")}


def slug(member):
    return member[4:] if member.startswith("off-") else member


class Members:
    def __init__(self, a, d):
        self.a = a
        self.members = d["members.json"]
        self.name = {m["member"]: m["name"] for m in self.members}
        self.items = [i for i in d["items.json"] if i["meeting_date"] >= SEATED]
        rv = d["review"]
        self.item_thread = {x["record_id"]: x["thread"] for x in rv["threads.json"].get("items", [])}
        self.timing = {(c["record_id"], c["member"]): c for c in rv["cosponsors.json"]["additions"]}
        self.substitutes = {(m["record_id"], m["seq"]): m for m in rv["motions.json"]["motions"]}
        self.attendance = [x for x in d["attendance.json"] if x["meeting_date"] >= SEATED]
        self.roles = defaultdict(list)       # member -> [(bin, item)]
        for it in self.items:
            authors = [x for x in it["attribution"] if x["role"] in ("author", "co-author")]
            contact = (it["contact"] or "").lower()
            for x in it["attribution"]:
                if x["role"] in ("author", "co-author"):
                    surname = self.name.get(x["member"], x["as_printed"]).split()[-1].lower()
                    lead = len(authors) == 1 or (surname and surname in contact and
                                                 sum(1 for y in authors if self.name.get(y["member"], y["as_printed"]).split()[-1].lower() in contact) == 1)
                    b = "lead" if lead else "joint"
                elif x["role"] == "co-sponsor":
                    b = "listed"
                else:
                    b = "unlabeled"
                self.roles[x["member"]].append((b, it))
            for x in it["added_cosponsors"]:
                t = self.timing.get((it["record_id"], x["member"]))
                self.roles[x["member"]].append(("at_meeting" if t and t["finding"] == "at_meeting" else "later", it))

    def thread_of(self, it):
        return self.a.record_thread.get(it["record_id"]) or self.item_thread.get(it["record_id"]) or "other"

    def ids(self):
        return [m["member"] for m in self.members]

    # votes ---------------------------------------------------------------
    @staticmethod
    def position(vote, member):
        for k in ("ayes", "noes", "abstain", "absent", "recused"):
            if member in vote[k]:
                return {"ayes": "aye", "noes": "no"}.get(k, k)
        return "all_ayes" if vote["all_ayes"] else None

    def final_votes(self):
        for it in self.items:
            for m in it["motions"]:
                if m["final"] and m["vote"]:
                    yield it, m

    def divided(self):
        """Every recorded motion, other than procedural ones, on which a named member voted no or abstained."""
        out = []
        for it in self.items:
            for m in it["motions"]:
                v = m["vote"]
                if v and m["kind"] != "procedural" and not v["all_ayes"] and (v["noes"] or v["abstain"]):
                    out.append((it, m))
        return out

    def kind(self, it, m):
        if (it["record_id"], m["seq"]) in self.substitutes:
            return "substitute"
        return m["kind"]

    def stats(self, values):
        vals = list(values)
        return statistics.median(vals), min(vals), max(vals)


def baseline(med, lo, hi):
    m = f"{med:g}" if isinstance(med, (int, float)) else med
    return f'<span class="muted">Council median {m}; range {lo}–{hi}</span>'


def member_page(M, member, h):
    esc, link, fd, a = h["esc"], h["link"], h["fmt_date"], M.a
    info = next(m for m in M.members if m["member"] == member)
    office = info["office"] + (f", District {info['district']}" if info.get("district") else "")
    body = [f"<h1>{esc(info['name'])}</h1>", f"<p class=\"muted\">{esc(office)} · {link('index.html', 'All members')}</p>",
            "<p>What the record shows for this member since the Council was seated in December 2024: the items they "
            "brought, how they voted on each item's final motion, the motions they made, and roll-call attendance. "
            "Each kind of count stands on its own and is never added to another. Each total is shown beside the "
            "median and range across the Council's nine members.</p>"]
    # items brought
    per_bin = Counter(b for b, _ in M.roles[member])
    others = {k: [Counter(b for b, _ in M.roles[x])[k] for x in M.ids()] for k, _, _ in BINS}
    by_thread = defaultdict(Counter)
    for b, it in M.roles[member]:
        by_thread[M.thread_of(it)][b] += 1
    head = "".join(f'<th scope="col">{esc(lab)}</th>' for _, lab, _ in BINS)
    rows = []
    for t in sorted(by_thread, key=lambda t: (t == "routine", t == "other", -sum(by_thread[t].values()))):
        lab = "Routine items (relinquishments, donations, commemorations, appointments)" if t == "routine" else a.thread_info[t]["label"]
        cell = link(f"../time/{t}.html", lab) if t in a.rows else esc(lab)
        rows.append(f"<tr><th scope=\"row\">{cell}</th>" + "".join(f'<td class="num">{by_thread[t][k] or ""}</td>' for k, _, _ in BINS) + "</tr>")
    rows.append('<tr class="tot"><th scope="row">Total</th>' + "".join(
        f'<td class="num">{per_bin[k]}<br>{baseline(*M.stats(others[k]))}</td>' for k, _, _ in BINS) + "</tr>")
    body.append('<h2 id="items">Items they brought to the Council</h2>'
                "<p>How the agenda named them, by subject. The kinds are kept apart and never added together.</p>"
                f'<dl class="bins">{"".join(f"<dt>{esc(lab)}</dt><dd>{esc(desc)}</dd>" for _, lab, desc in BINS)}</dl>'
                f'<div class="table-wrap"><table><caption>Items by subject and role</caption><thead><tr><th scope="col">Subject</th>{head}</tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')
    for k, lab, _ in BINS:
        its = [it for b, it in M.roles[member] if b == k]
        if not its:
            continue
        lis = []
        for it in sorted(its, key=lambda i: i["meeting_date"]):
            extra = ""
            if k in ("at_meeting", "later"):
                t = M.timing.get((it["record_id"], member))
                if t and t.get("quote") and k == "at_meeting":
                    loc = t.get("start") or f"line {t.get('line')}"
                    extra = f"<br><span class=\"muted\">Transcript, {esc(loc)}: “{esc(t['quote'])}”</span>"
            lis.append(f"<li>{h['mlink'](h, it['meeting_id'], fd(it['meeting_date']))}, Item {esc(it['item'])}: {esc(it['heading'])}{extra}</li>")
        body.append(f"<details><summary>{esc(lab)}: {len(its)} items</summary><ul>{''.join(lis)}</ul></details>")
    body.append(f'<p class="muted">Many member items are adopted on the consent calendar without discussion. For an '
                f'argument about how Berkeley sorts work between the two calendars, see the Berkeley Decision '
                f'Project\'s <a href="{h["bdp"]}consent-drip.html">Two Calendars</a>.</p>')
    # votes
    tv = defaultdict(Counter)
    for it, m in M.final_votes():
        tv[M.thread_of(it)][M.position(m["vote"], member)] += 1
    tallies = {x: Counter(M.position(m["vote"], x) for _, m in M.final_votes()) for x in M.ids()}
    allc = {k: [tallies[x][k] for x in M.ids()] for k, _ in VOTE_COLS}
    mine = Counter(M.position(m["vote"], member) for _, m in M.final_votes())
    rows = []
    for t in sorted(tv, key=lambda t: (t == "routine", t == "other", -sum(tv[t].values()))):
        lab = "Routine items" if t == "routine" else a.thread_info[t]["label"]
        rows.append(f"<tr><th scope=\"row\">{esc(lab)}</th>" + "".join(f'<td class="num">{tv[t][k] or ""}</td>' for k, _ in VOTE_COLS) + "</tr>")
    rows.append('<tr class="tot"><th scope="row">Total</th>' + "".join(
        f'<td class="num">{mine[k]}<br>{baseline(*M.stats(allc[k]))}</td>' for k, _ in VOTE_COLS) + "</tr>")
    body.append('<h2 id="votes">How they voted on final motions</h2>'
                '<p>The vote on the motion that decided each item, as the Clerk recorded it. Where the Clerk printed '
                '“All Ayes” without names, the vote is counted under “All Ayes”, not as a named aye: who was present at '
                'that moment is not printed. Consent calendar items, adopted together in one vote, have no vote of '
                'their own and are not counted.</p>'
                f'<div class="table-wrap"><table><caption>Final votes by subject</caption><thead><tr><th scope="col">Subject</th>'
                f'{"".join(f"<th scope=col>{esc(l)}</th>" for _, l in VOTE_COLS)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    dv = [(it, m) for it, m in M.divided() if M.position(m["vote"], member) in ("no", "abstain", "aye", "absent", "recused")]
    lis = []
    for it, m in dv:
        pos = M.position(m["vote"], member)
        v = m["vote"]
        lis.append(f"<li>{h['mlink'](h, it['meeting_id'], fd(it['meeting_date']))}, Item {esc(it['item'])} "
                   f"({esc(KIND_TEXT.get(M.kind(it, m), M.kind(it, m)))}, {esc(m['disposition'])} {len(v['ayes'])}–{len(v['noes'])}"
                   f"{', ' + str(len(v['abstain'])) + ' abstaining' if v['abstain'] else ''}): <strong>{esc(CELL[pos][1])}</strong> · {esc(it['heading'])}</li>")
    body.append(f"<details><summary>Every divided vote, and this member's vote on it: {len(dv)}</summary><ul>{''.join(lis)}</ul></details>")
    # motions
    moved, seconded, subs = Counter(), 0, []
    for it in M.items:
        for m in it["motions"]:
            if not m["movers"]:
                continue
            k = M.kind(it, m)
            if m["movers"][0] == member:
                moved[k] += 1
                if k in ("substitute", "competing"):
                    subs.append((it, m, k))
            elif m["movers"][1] == member:
                seconded += 1
    allm = [sum(1 for it in M.items for m in it["motions"] if m["movers"] and m["movers"][0] == x and m["kind"] != "procedural") for x in M.ids()]
    alls = [sum(1 for it in M.items for m in it["motions"] if m["movers"] and m["movers"][1] == x) for x in M.ids()]
    body.append('<h2 id="motions">Motions they made</h2><ul>'
                f"<li>Moved {sum(v for k, v in moved.items() if k != 'procedural')} motions on items, other than procedural ones. {baseline(*M.stats(allm))}</li>"
                f"<li>Moved {moved['procedural']} procedural motions (suspending the rules, extending the meeting, accepting materials).</li>"
                f"<li>Seconded {seconded} motions. {baseline(*M.stats(alls))}</li></ul>")
    if subs:
        body.append("<p>Competing and substitute motions they moved:</p><ul>")
        for it, m, k in subs:
            v = m["vote"]
            tally = f" {len(v['ayes'])}–{len(v['noes'])}" if v and not v["all_ayes"] else ""
            body.append(f"<li>{h['mlink'](h, it['meeting_id'], fd(it['meeting_date']))}, Item {esc(it['item'])}: "
                        f"{esc(KIND_TEXT.get(k, k))}, {esc(m['disposition'])}{tally} · {esc(it['heading'])}</li>")
        body.append("</ul>")
    # attendance
    def att(x):
        out = Counter()
        for r in M.attendance:
            if x in r["absent"]:
                out["late" if any(l["member"] == x for l in r["arrived_late"]) else "absent"] += 1
        return out
    mine_a = att(member)
    alla = [att(y) for y in M.ids()]
    body.append(f'<h2 id="attendance">Roll-call attendance</h2><p>Of {len(M.attendance)} meetings with an annotated agenda: '
                f'arrived after roll call at {mine_a["late"]} {baseline(*M.stats(c["late"] for c in alla))}; recorded absent with no '
                f'arrival noted at {mine_a["absent"]} {baseline(*M.stats(c["absent"] for c in alla))}.</p>')
    rows = [r for r in M.attendance if member in r["absent"]]
    if rows:
        body.append("<details><summary>Meetings</summary><ul>" + "".join(
            f"<li>{h['mlink'](h, x['meeting_id'], fd(x['meeting_date']))}: "
            + (f"arrived {esc(next(l['time'] for l in x['arrived_late'] if l['member'] == member))}"
               if any(l['member'] == member for l in x['arrived_late']) else "absent; no arrival noted") + "</li>"
            for x in rows) + "</ul></details>")
    body.append('<p class="muted">Attendance is what the annotated agenda records at roll call and after it; it says nothing about the reason. A member who left early is not recorded here.</p>')
    return h["page"](info["name"], "\n".join(body), 1, h["meta"])


KIND_TEXT = {"main": "main motion", "substitute": "substitute motion", "competing": "competing motion", "amendment": "amendment",
             "action": "action", "procedural": "procedural motion", "unattributed": "vote"}


def index_page(M, h):
    esc, link, fd, a = h["esc"], h["link"], h["fmt_date"], M.a
    ids = M.ids()
    body = ["<h1>Members</h1>",
            "<p>What the record shows for each member of the Council seated in December 2024, and for the body as a whole. "
            "Counts are by kind and never combined into a score.</p>",
            '<ul class="members">' + "".join(f"<li>{link(slug(x) + '.html', M.name[x])}</li>" for x in ids) + "</ul>"]
    head = "".join(f'<th scope="col">{esc(lab)}</th>' for _, lab, _ in BINS)
    rows = "".join(f"<tr><th scope=\"row\">{link(slug(x) + '.html', M.name[x])}</th>" +
                   "".join(f'<td class="num">{Counter(b for b, _ in M.roles[x])[k]}</td>' for k, _, _ in BINS) + "</tr>" for x in ids)
    body.append('<h2 id="items">Items brought, by role</h2>'
                f'<div class="table-wrap"><table><caption>Agenda items naming each member, by role</caption><thead><tr><th scope="col">Member</th>{head}</tr></thead>'
                f'<tbody>{rows}</tbody></table></div><p class="muted">Each member\'s page breaks these down by subject. Routine items '
                'such as relinquishments of office funds are included; member pages show them separately.</p>')
    finals = list(M.final_votes())
    unan = sum(1 for _, m in finals if m["vote"]["all_ayes"] or not (m["vote"]["noes"] or m["vote"]["abstain"]))
    dv = M.divided()
    body.append(f'<h2 id="divided">Where the vote divided</h2><p>Of {len(finals)} recorded final votes, {unan} had no named no '
                f'or abstention. Below is every recorded motion, other than procedural ones, on which at least one member voted '
                f'no or abstained: {len(dv)} motions, including the competing and substitute motions that often carry the '
                f'disagreement on an item whose final vote was unanimous.</p>'
                '<p class="legend">Y aye · N no · A abstain · – absent · R recused · blank: not recorded. Substitute '
                'motions are those the transcript confirms; a failed motion followed by the one that decided the item is '
                'shown as competing.</p>')
    th = "".join(f'<th scope="col" class="m">{esc(M.name[x].split()[-1])}</th>' for x in ids)
    rows = []
    for it, m in dv:
        v = m["vote"]
        cells = []
        for x in ids:
            pos = M.position(v, x)
            sym, lab = CELL[pos]
            cells.append(f'<td class="v {pos or "none"}"><span aria-hidden="true">{sym}</span><span class="sr-only">{lab}</span></td>')
        t = M.thread_of(it)
        rows.append(f"<tr><td class=\"num\">{h['mlink'](h, it['meeting_id'], fd(it['meeting_date']))}</td>"
                    f"<td>Item {esc(it['item'])}: {esc(it['heading'][:90])}{'…' if len(it['heading']) > 90 else ''}<br>"
                    f"<span class=\"muted\">{esc(KIND_TEXT.get(M.kind(it, m), M.kind(it, m)))}, {esc(m['disposition'])} · "
                    f"{esc(a.thread_info[t]['label'] if t != 'routine' else 'Routine')}</span></td>{''.join(cells)}</tr>")
    body.append(f'<div class="table-wrap"><table class="grid"><caption>Divided votes</caption><thead><tr><th scope="col">Meeting</th>'
                f'<th scope="col">Motion</th>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    rows = []
    for x in ids:
        mv = Counter(M.kind(it, m) for it in M.items for m in it["motions"] if m["movers"] and m["movers"][0] == x)
        sec = sum(1 for it in M.items for m in it["motions"] if m["movers"] and m["movers"][1] == x)
        rows.append(f"<tr><th scope=\"row\">{link(slug(x) + '.html', M.name[x])}</th><td class=\"num\">{mv['main'] + mv['action']}</td>"
                    f"<td class=\"num\">{mv['substitute'] + mv['competing']}</td><td class=\"num\">{mv['amendment']}</td>"
                    f"<td class=\"num\">{mv['procedural']}</td><td class=\"num\">{sec}</td></tr>")
    body.append('<h2 id="motions">Motions moved and seconded</h2><div class="table-wrap"><table><caption>Motions by mover</caption>'
                '<thead><tr><th scope="col">Member</th><th scope="col">Main motions</th><th scope="col">Substitute or competing</th>'
                '<th scope="col">Amendments</th><th scope="col">Procedural</th><th scope="col">Seconded</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')
    body.append('<p class="muted">Votes, motions and authorship are as the City Clerk printed them in the annotated agendas. '
                f'A member\'s record is a set of facts to read together, not a grade. Data: '
                f'{link("../data/council-time/items.json", "items.json")}, {link("../data/council-time/attendance.json", "attendance.json")}.</p>')
    return h["page"]("Members", "\n".join(body), 1, h["meta"])


CSS = """
dl.bins{grid-template-columns:max-content 1fr;font-size:.92rem}
tr.tot th,tr.tot td{border-top:2px solid var(--line)}
table.grid{table-layout:auto}
table.grid td:nth-child(2){min-width:22em}
table.grid td.v{text-align:center;font-weight:600;min-width:2.4em;padding:6px 2px}
table.grid th.m{font-size:.85rem;text-align:center}
td.v.no{background:#f6d5d0}td.v.abstain{background:#f3e7c4}td.v.absent,td.v.recused{color:var(--muted)}
@media (prefers-color-scheme:dark){td.v.no{background:#5a2a24}td.v.abstain{background:#4f4421}}
ul.members{columns:3;padding-left:20px}
"""
