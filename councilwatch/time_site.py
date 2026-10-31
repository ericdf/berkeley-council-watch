"""Pages for the council-time lane, and the commitments index.

Charts are SVG written at build time; every number a chart shows is also in a table on the same
page, so nothing depends on hover, color or JavaScript. Thread is a reviewed classification
(data/review/council-time/threads.json); minutes are computed (data/generated/council-time/).
"""
import datetime
import json
import math
import os
from collections import Counter, defaultdict

from . import council_time as ct
from . import tracked as tracked_mod

ARCHIVE_BLOB = "https://github.com/ericdf/berkeley-public-records/blob"
START, END = datetime.date(2024, 12, 1), datetime.date(2026, 11, 1)
FINANCES = "City finances"
OPEN_STATUSES = {"not_yet_due", "no_due_date_stated", "in_progress_reported", "delayed", "unknown_no_update_located"}


def load(data_dir=ct.OUT_DIR, review_dir=ct.REVIEW_DIR):
    d = {}
    for n in ct.NAMES:
        with open(os.path.join(data_dir, n), encoding="utf-8") as f:
            d[n] = json.load(f)
    d["review"] = ct.load_review(review_dir)
    return d


def hours(m):
    return f"{m / 60:.1f}"


def minutes(m):
    return "—" if m is None else f"{m:.0f}"


def locator_text(loc):
    if "start" in loc:
        return f"{loc['start']}–{loc['end']}"
    return f"lines {loc['start_line']}–{loc['end_line']}"


KIND_LABELS = {"opening": "Call to order and roll call", "ceremonial": "Ceremonial matters", "consent": "Consent calendar",
               "item": "Agenda item", "public_comment_nonagenda": "Public comment on items not on the agenda",
               "council_comments": "Council and City Manager comments", "recess": "Recess",
               "other_procedural": "Other procedural business", "closing": "Adjournment"}
BODY_LABELS = {"committee": "Budget & Finance Committee: ", "jpfa": "Joint Powers Financing Authority: ",
               "sabra": "Successor Agency: "}


class Attention:
    """Everything the pages need, assembled once from the dataset and the reviewed classification."""

    def __init__(self, d):
        rv = d["review"]["threads.json"]
        self.meta = d["meta.json"]
        self.thread_info = {t["id"]: t for t in rv["threads"]}
        self.seg_class = {a["segment"]: a for a in rv["segments"]}
        self.items = {i["record_id"]: i for i in d["items.json"]}
        self.segments = d["segments.json"]
        self.decisions = defaultdict(list)
        for x in rv.get("decisions", []):
            self.decisions[x["thread"]].append(x)
        self.matter_thread = {m["matter"]: m["thread"] for m in rv.get("matters", [])}
        self.links = d["review"]["links.json"]["links"]
        heading_thread = {h["heading"]: h["thread"] for h in rv["correspondence_headings"]}

        self.rows = defaultdict(lambda: defaultdict(lambda: {"disc": 0.0, "pc": 0.0, "est": False, "letters": 0, "form": 0,
                                                             "labels": [], "meeting_ids": set(), "aud": 0.0}))
        self.ranking = defaultdict(lambda: {"disc": 0.0, "pc": 0.0, "est": False})
        self.record_thread = {}
        self.by_meeting = defaultdict(list)
        self.by_record = defaultdict(list)
        self.auditor = []
        for s in self.segments:
            c = self.seg_class[s["segment_id"]]
            self.by_meeting[s["meeting_id"] or s["meeting_date"]].append(s)
            for r in s["record_ids"]:
                self.by_record[r].append(s)
            if c["thread"] == "routine" or s["minutes"] is None:
                continue
            r = self.rows[c["thread"]][s["meeting_date"]]
            r["disc"] += s["minutes"] - s["public_comment_minutes"]
            r["pc"] += s["public_comment_minutes"]
            r["est"] |= s["estimated"]
            if s["meeting_id"]:
                r["meeting_ids"].add(s["meeting_id"])
            lab = self.label(s)
            if lab not in r["labels"]:
                r["labels"].append(lab)
            for rid in s["record_ids"]:
                self.record_thread[rid] = c["thread"]
            key = (s["meeting_date"], s["meeting_id"], s["item_as_recorded"] or s["segment_id"], c["thread"])
            k = self.ranking[key]
            k["disc"] += s["minutes"] - s["public_comment_minutes"]
            k["pc"] += s["public_comment_minutes"]
            k["est"] |= s["estimated"]
            k["label"], k["segment"] = lab, s
            if c["auditor"]:
                r["aud"] += s["minutes"]
                self.auditor.append((s, c["thread"], lab))
        self.turns_whole = [t for t in d["turns.json"] if t["extent"] == "whole"]
        self.turns_partial = [t for t in d["turns.json"] if t["extent"] == "partial"]
        for t in self.turns_whole:
            r = self.rows[t["thread"]][t["meeting_date"]]
            r["pc"] += t["minutes"] or 0
            r["est"] |= t["estimated"]
            lab = "Turns in general or consent public comment"
            if lab not in r["labels"]:
                r["labels"].append(lab)
        self.unassigned_letters = defaultdict(lambda: [0, set()])
        self.letters_by_meeting = defaultdict(Counter)   # meeting_id -> topic (None: not assigned) -> letters
        for c in d["correspondence.json"]:
            if not c["letters_public"]:
                continue
            th = next((self.record_thread[r] for r in c["record_ids"] if r in self.record_thread), None)
            th = th or heading_thread.get(c["heading"])
            self.letters_by_meeting[c["meeting_id"]][th] += c["letters_public"]
            if not th:
                if c["letters_public"]:
                    u = self.unassigned_letters[c["heading"] or "(no heading)"]
                    u[0] += c["letters_public"]
                    u[1].add(c["meeting_date"])
                continue
            r = self.rows[th][c["meeting_date"]]
            r["letters"] += c["letters_public"]
            r["form"] += c["form_letters"]
            r["meeting_ids"].add(c["meeting_id"])
        # Items a Council member authored, by thread, whether or not the Council heard them. Writing an item
        # and moving it through agenda review takes Council and staff time that no transcript measures.
        item_thread = {x["record_id"]: x["thread"] for x in rv.get("items", [])}
        self.authored = defaultdict(list)
        for it in d["items.json"]:
            if it["meeting_date"] < "2024-12-10" or not any(x["role"] in ("author", "co-author") for x in it["attribution"]):
                continue
            th = self.record_thread.get(it["record_id"]) or item_thread.get(it["record_id"])
            if th and th != "routine":
                self.authored[th].append((it, it["record_id"] in self.record_thread))
        self.consent = defaultdict(lambda: defaultdict(list))
        for c in d.get("consent.json", []):
            if c["meeting_date"] < "2024-12-10":
                continue
            th = item_thread.get(c["record_id"], "other")
            if th != "routine":
                self.consent[th][c["meeting_date"]].append(c)
        self.max_minutes = max((r["disc"] + r["pc"] for t in self.rows.values() for r in t.values()), default=1)

    def label(self, s):
        c = self.seg_class[s["segment_id"]]
        if c.get("label"):
            return c["label"]
        heads = [self.items[r]["heading"] for r in s["record_ids"] if r in self.items]
        if heads:
            if (s["item_as_recorded"] or "").lower() in ("urgent", "urgency"):
                return f"Urgency item: {heads[0]}"
            return f"Item {s['item_as_recorded']}: {heads[0]}"
        body = BODY_LABELS.get(s["meeting_body"], "")
        if s["item_as_recorded"]:
            return f"{body}Item {s['item_as_recorded']}"
        return body + KIND_LABELS.get(s["kind"], s["kind"].replace("_", " ").capitalize())

    def thread_ids(self):
        """City finances first, in their own order; then the rest by total time; then Other."""
        ids = [t["id"] for t in self.thread_info.values() if t["id"] != "routine"
               and (t["id"] in self.rows or t["id"] in self.authored or t["id"] in self.consent)]
        fin = [t for t in ids if self.thread_info[t]["group"] == FINANCES]
        rest = sorted((t for t in ids if t not in fin and t != "other"), key=lambda t: -self.total(t))
        return fin + rest + (["other"] if "other" in ids else [])

    def total(self, t, k=None):
        rs = self.rows[t].values()
        return sum(r["disc"] + r["pc"] for r in rs) if k is None else sum(r[k] for r in rs)

    def decision_rows(self, t):
        out = []
        for x in self.decisions.get(t, []):
            rid = f"{x['meeting_id']}--item-{x['item']}"
            it = self.items.get(rid)
            out.append((it["meeting_date"] if it else None, x, it))
        return sorted(out, key=lambda r: r[0] or "")


def vote_text(it):
    fm = (it or {}).get("final_motion")
    if not fm or not fm["vote"]:
        return ""
    v = fm["vote"]
    if v["all_ayes"]:
        return "All ayes"
    s = f"{v['ayes']}–{v['noes']}"
    if v["abstain"]:
        s += f", {v['abstain']} abstaining"
    if fm["disposition"] == "failed":
        s += ", failed"
    return s


def x_of(date):
    d = datetime.date.fromisoformat(date)
    return (d - START).days / (END - START).days


DEFS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="1.5" height="4" fill="var(--bg)" opacity=".55"/></pattern></defs></svg>"""


def axis_svg(width=900):
    ticks = []
    d = datetime.date(START.year, START.month, 1)
    while d < END:
        if d.month in (1, 4, 7, 10):
            x = x_of(d.isoformat()) * width
            lab = d.strftime("%b") + (f" {d.year}" if d.month == 1 else "")
            ticks.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="6" stroke="var(--line)"/>'
                         f'<text x="{x:.1f}" y="18" font-size="11" text-anchor="middle" fill="var(--muted)">{lab}</text>')
        d = datetime.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (f'<svg class="axis" viewBox="0 0 {width} 22" role="presentation" aria-hidden="true">'
            f'{"".join(ticks)}</svg>')


def row_svg(a, t, height=56, width=900, esc=None, href=""):
    """One topic's row. Each meeting's bar links to that meeting's row in the topic page's table
    (`href` is the page, empty on the topic page itself)."""
    k = (height - 4) / a.max_minutes
    parts = []
    for date, r in sorted(a.rows[t].items()):
        x = x_of(date) * width - 2.5
        hd, hp = r["disc"] * k, r["pc"] * k
        y0 = height
        label = (f"{date}: {r['disc']:.0f} min staff and Council, {r['pc']:.0f} min public comment, "
                 f"{r['letters']} letters. Go to this meeting in the table.")
        d = datetime.date.fromisoformat(date)
        read = (f"{d.strftime('%B')} {d.day}, {d.year}: {r['disc']:.0f} min staff and Council, "
                f"{r['pc']:.0f} min public comment, {r['letters']} letter{'' if r['letters'] == 1 else 's'}."
                + (" Minutes are estimated." if r["est"] else ""))
        parts.append(f'<a class="bar" href="{href}#d-{date}" aria-label="{esc(label)}" data-read="{esc(read)}"><title>{esc(label)}</title>'
                     f'<rect x="{x - 1:.1f}" y="0" width="7" height="{height + 20}" fill="transparent"/>')
        if hd > 0:
            parts.append(f'<rect x="{x:.1f}" y="{y0 - hd:.1f}" width="5" height="{hd:.1f}" fill="var(--c-staff)"/>')
        if hp > 0:
            parts.append(f'<rect x="{x:.1f}" y="{y0 - hd - hp:.1f}" width="5" height="{hp:.1f}" fill="var(--c-pc)"/>')
        if r["est"] and hd + hp > 0:
            parts.append(f'<rect x="{x:.1f}" y="{y0 - hd - hp:.1f}" width="5" height="{hd + hp:.1f}" fill="url(#hatch)"/>')
        if r["letters"]:
            rad = min(9, 1.2 + math.sqrt(r["letters"]) * 0.45)
            parts.append(f'<circle cx="{x + 2.5:.1f}" cy="{height + 11}" r="{rad:.1f}" fill="none" stroke="var(--c-letters)" stroke-width="1.2"/>')
        parts.append("</a>")
    CH, base = 16, height + 24
    for date, cs in sorted(a.consent[t].items()):
        x = x_of(date) * width
        amt = max((c["amount"] or 0 for c in cs if c["policy_bearing"]), default=0)
        hgt = 4 + (CH - 4) * min(1, max(0, (math.log10(amt) - 3) / 6)) if amt else 4
        solid = any(c["policy_bearing"] for c in cs)
        parts.append(f'<rect x="{x - 1.5:.1f}" y="{base + CH - hgt:.1f}" width="3" height="{hgt:.1f}" '
                     + (f'fill="var(--c-consent)"/>' if solid else f'fill="none" stroke="var(--c-consent)" stroke-width="1"/>'))
        if len(cs) > 1:
            parts.append(f'<text x="{x + 3:.1f}" y="{base + CH}" font-size="8" text-anchor="start" fill="var(--c-consent)">{len(cs)}</text>')
    for date, x_, it in a.decision_rows(t):
        if date:
            x = x_of(date) * width
            parts.append(f'<path d="M{x - 4:.1f},1 L{x + 4:.1f},1 L{x:.1f},7 Z" fill="var(--fg)"/>')
    staff, pc = a.total(t, "disc"), a.total(t, "pc")
    desc = (f"{a.thread_info[t]['label']}: {hours(staff)} hours of staff and Council time and {hours(pc)} hours of "
            f"spoken public comment across {len(a.rows[t])} meetings, and {a.total(t, 'letters'):,} letters.")
    nc = sum(len(v) for v in a.consent[t].values())
    desc += f" {nc} consent calendar items." if nc else ""
    return (f'<svg class="row" viewBox="0 0 {width} {height + 24 + (CH + 2 if a.consent[t] else 0)}" role="img" aria-label="{esc(desc)}">'
            f'<line x1="0" x2="{width}" y1="{height}" y2="{height}" stroke="var(--line)"/>{"".join(parts)}</svg>')



# On a touch screen a chart bar's <title> tooltip never appears, and a tap would jump straight to the
# table. This script makes the first tap on a chart show the figures for the nearest bar under the
# chart, with a link to the meeting's row; a second tap on the same bar follows the link. Bars are a
# few pixels wide on a phone, so a tap picks the nearest bar within 24 pixels. Mouse and keyboard are unchanged, and
# without the script a tap goes to the table row, which holds the same figures.
READOUT_JS = """(function () {
  var touch = false, sel = null, box = null;
  document.addEventListener("pointerdown", function (e) { touch = e.pointerType !== "mouse"; }, true);
  function clear() {
    if (sel) sel.classList.remove("sel");
    if (box) box.remove();
    sel = box = null;
  }
  function nearest(svg, x) {
    var best = null, d = 24;
    svg.querySelectorAll("a.bar").forEach(function (b) {
      var r = b.getBoundingClientRect(), dx = Math.abs(r.left + r.width / 2 - x);
      if (dx < d) { d = dx; best = b; }
    });
    return best;
  }
  document.addEventListener("click", function (e) {
    var svg = touch && e.target.closest && e.target.closest("svg.row");
    var bar = svg && nearest(svg, e.clientX);
    if (!bar) { if (box && !box.contains(e.target)) clear(); return; }
    e.preventDefault();
    if (bar === sel) { location.href = new URL(bar.getAttribute("href"), location.href).href; return; }
    clear();
    sel = bar;
    bar.classList.add("sel");
    box = document.createElement("p");
    box.className = "readout";
    box.setAttribute("role", "status");
    box.textContent = bar.getAttribute("data-read") + " ";
    var a = document.createElement("a");
    a.href = bar.getAttribute("href");
    a.textContent = "Go to this meeting in the table";
    box.appendChild(a);
    svg.parentNode.insertBefore(box, svg.nextSibling);
  });
})();
"""


LEGEND = """<p class="legend"><span class="key staff"></span> Staff and Council time
<span class="key pc"></span> Spoken public comment <span class="key est"></span> Estimate
<span class="key letters"></span> Letters <span class="key dec">▼</span> Decision (listed below)
<span class="key consent"></span> Consent calendar items (filled: more than routine; taller: larger amount; a number beside the tick counts the items)</p>"""

ANALYSIS = """<aside class="analysis"><h2>Analysis elsewhere</h2>
<p>These pages show how the Council's attention is allocated. The Berkeley Decision Project argues that
Council and staff attention is a finite public resource, in <a href="{bdp}governance-by-exhaustion.html">Governance by
Exhaustion</a>, and that what goes on the consent calendar does not track the size of the commitment, in
<a href="{bdp}consent-drip.html">Two Calendars</a>.</p></aside>"""

METHOD_LINK = ('<p class="muted">Minutes are meeting time, from the Council\'s transcripts; hatched bars are estimates. '
               'Topics are this site\'s grouping. <a href="../method.html">How this data is derived</a></p>')

TIME_NOTE = ("Minutes measure meeting time only. Writing an item and moving it through agenda review, staff and legal "
             "review take Council and staff time before any meeting, and no record measures that in minutes; so these "
             "pages also count the items Council members wrote on each subject, including those adopted on the consent "
             "calendar without discussion. Minutes come from the Council's caption transcripts. Item boundaries were read from each transcript and "
             "have not been checked against video. Most 2025 transcripts have no timestamps, so their minutes are "
             "estimates from each item's share of the words, shown hatched. Each item's topic is this "
             "site's classification. Routine meeting business, including the consent calendar as a block, is "
             "not counted in minutes.")


def mlink(h, mid, text):
    """A link to a meeting page when the site has one; plain text otherwise."""
    if mid and mid in h["meeting_ids"]:
        return h["link"](f"../meetings/{mid}.html", text)
    return h["esc"](text)


def pick_example(a):
    """The topic and meeting whose bar shows the most of the chart's parts, for the how-to-read figure: one with a
    decision and consent items first, then the most parts, then a budget row, then the larger bar."""
    best = None
    for t in a.thread_ids():
        decs = {d for d, _, _ in a.decision_rows(t) if d}
        for date, r in a.rows[t].items():
            cs = a.consent[t].get(date, [])
            parts = sum([r["disc"] > 0, r["pc"] > 0, r["est"], r["letters"] > 0, date in decs, bool(cs),
                         any(c["policy_bearing"] for c in cs), len(cs) > 1])
            key = (date in decs, bool(cs), parts, t == "budget", r["disc"] + r["pc"])
            if best is None or key > best[0]:
                best = (key, t, date)
    return (best[1], best[2]) if best else (None, None)


def how_to_read(a, h, up=""):
    """One real column of a topic chart, enlarged, with numbered parts explained in a list beside it."""
    esc = h["esc"]
    t, date = pick_example(a)
    if not t:
        return ""
    r = a.rows[t][date]
    cs = a.consent[t].get(date, [])
    dec = next(((x, it) for d, x, it in a.decision_rows(t) if d == date), None)
    W, H, k = 230, 300, 200 / max(r["disc"] + r["pc"], 1)
    x0, base = 70, 230
    hd, hp = r["disc"] * k, r["pc"] * k
    parts, items, n = [], [], 0

    def mark(x, y, text):
        nonlocal n
        n += 1
        parts.append(f'<line x1="{x}" y1="{y}" x2="{x + 34}" y2="{y}" stroke="var(--muted)" stroke-width="1"/>'
                     f'<circle cx="{x + 46}" cy="{y}" r="11" fill="var(--bg)" stroke="var(--fg)"/>'
                     f'<text x="{x + 46}" y="{y + 4}" font-size="12" text-anchor="middle" fill="var(--fg)">{n}</text>')
        items.append(text)
    parts.append(f'<line x1="20" x2="{W - 10}" y1="{base}" y2="{base}" stroke="var(--line)"/>')
    if hd:
        parts.append(f'<rect x="{x0}" y="{base - hd:.1f}" width="34" height="{hd:.1f}" fill="var(--c-staff)"/>')
    if hp:
        parts.append(f'<rect x="{x0}" y="{base - hd - hp:.1f}" width="34" height="{hp:.1f}" fill="var(--c-pc)"/>')
    if r["est"]:
        parts.append(f'<rect x="{x0}" y="{base - hd - hp:.1f}" width="34" height="{hd + hp:.1f}" fill="url(#hatch)"/>')
    if dec:
        parts.append(f'<path d="M{x0 + 9},{base - hd - hp - 22} L{x0 + 25},{base - hd - hp - 22} L{x0 + 17},{base - hd - hp - 10} Z" fill="var(--fg)"/>')
    if r["letters"]:
        rad = min(18, 4 + math.sqrt(r["letters"]) * 1.2)
        parts.append(f'<circle cx="{x0 + 17}" cy="{base + 26}" r="{rad:.1f}" fill="none" stroke="var(--c-letters)" stroke-width="2"/>')
    if cs:
        solid = any(c["policy_bearing"] for c in cs)
        parts.append(f'<rect x="{x0 + 12}" y="{base + 50}" width="10" height="28" '
                     + ('fill="var(--c-consent)"/>' if solid else 'fill="none" stroke="var(--c-consent)" stroke-width="2"/>'))
        if len(cs) > 1:
            parts.append(f'<text x="{x0 + 26}" y="{base + 78}" font-size="13" fill="var(--c-consent)">{len(cs)}</text>')
    mx = x0 + 40
    if hp:
        mark(mx, base - hd - hp / 2, f"<strong>Spoken public comment</strong>, in minutes: {r['pc']:.0f} here.")
    if hd:
        mark(mx, base - hd / 2, f"<strong>Staff and Council time</strong>, in minutes: presentations, questions, deliberation and votes. {r['disc']:.0f} here.")
    if r["est"]:
        items[-1] += (" <strong>Hatching</strong> marks an estimate: this meeting's transcript has no timestamps, so minutes come "
                      "from each item's share of the words.")
    if dec:
        x, it = dec
        vt = vote_text(it)
        mark(mx, base - hd - hp - 16, f"<strong>A decision</strong>, listed under the chart: “{esc(x['label'])}”"
             + (f", final vote {esc(vt)}." if vt else "."))
    if r["letters"]:
        mark(mx, base + 26, f"<strong>Letters</strong> from the public on the topic: {r['letters']} here. A bigger circle means more letters.")
    if cs:
        mark(mx, base + 64, f"<strong>Consent calendar items</strong> on the topic, adopted without discussion: {len(cs)} here. "
             "Filled when one shows more than a routine item (an ordinance, member authorship, speakers, letters); taller "
             "for a larger amount; a number counts the items.")
    items.append("<strong>Click any bar</strong> to go to that meeting in the topic's table.")
    when = h["fmt_date"](date)
    svg = (f'<svg class="how" viewBox="0 0 {W} {H + 20}" role="img" aria-label="Enlarged example bar; its parts are listed beside it">'
           f'{"".join(parts)}</svg>')
    return (f'<figure class="how-to-read" id="how-to-read"><div class="how-grid">{svg}<div><h2>How to read these charts</h2>'
            f'<p class="muted">One real column, enlarged: {esc(a.thread_info[t]["label"])}, {esc(when)}.</p>'
            f'<ol>{"".join(f"<li>{x}</li>" for x in items)}</ol></div></div></figure>')


def thread_href(t, up=""):
    return f"{up}time/{t}.html"


def render_time_index(a, h):
    esc, link, page = h["esc"], h["link"], h["page"]
    body = [DEFS, "<h1>Council time</h1>",
            "<p>How much of the Council's meeting time, and how much of the public's written correspondence, went to "
            "each subject, meeting by meeting. Every row shares the same date axis and the same minutes scale, so "
            "rows can be compared directly.</p>",
            METHOD_LINK,
            '<p class="muted">Jump to: <a href="#how-to-read">how to read these charts</a> · <a href="#totals">totals by topic</a> · <a href="#ranking">items ranked by time</a> · '
            '<a href="#ranking-comment">items by public comment</a> · '
            '<a href="#auditor">City Auditor items</a> · <a href="#connections">connections between topics</a> · '
            '<a href="consent-money.html">money on the consent calendar</a></p>',
            ANALYSIS.format(bdp=h["bdp"]),
            how_to_read(a, h),

            axis_svg()]
    group = None
    for t in a.thread_ids():
        info = a.thread_info[t]
        if info["group"] != group:
            group = info["group"]
            if group:
                tot = sum(a.total(x) for x in a.thread_ids() if a.thread_info[x]["group"] == group)
                body.append(f'<h2 id="city-finances">{esc(group)} <span class="muted">· {hours(tot)} hours in all</span></h2>'
                            '<p class="muted">Five rows on the same scale, so no part of the City\'s finances is hidden '
                            'inside a total.</p>' + aao_note(a, h))
            else:
                body.append('<h2 id="other-topics">Other topics</h2>')
        decs = a.decision_rows(t)
        dl = "".join(f"<li>{esc(h['fmt_date'](d))}: {esc(x['label'])}{(' (' + esc(vote_text(it)) + ')') if vote_text(it) else ''}</li>"
                     for d, x, it in decs if d)
        body.append(f'<section class="thread" id="{t}"><h3>{link(t + ".html", info["label"])} '
                    f'<span class="muted">· {hours(a.total(t, "disc"))} h staff and Council, {hours(a.total(t, "pc"))} h public comment, '
                    f'{a.total(t, "letters"):,} letters</span></h3>{row_svg(a, t, esc=esc, href=t + ".html")}'
                    + (f'<ul class="decisions">{dl}</ul>' if dl else "") + "</section>")
    body.append(axis_svg())

    body.append('<h2 id="totals">Totals by topic</h2><p>Meeting time and letters, and the items Council members wrote on '
                'each subject. An item not timed separately has no separate transcript segment: it was adopted on the consent '
                'calendar, taken up within another part of the meeting, or has not '
                'yet come to a vote; it took no meeting time but did take the time of whoever wrote it and the staff who '
                'reviewed it.</p>')
    rows = []
    mx = max(a.total(t) for t in a.thread_ids()) or 1
    for t in a.thread_ids():
        w = a.total(t) / mx * 100
        rows.append(f"<tr><td>{link(t + '.html', a.thread_info[t]['label'])}</td><td class=\"num\">{hours(a.total(t, 'disc'))}</td>"
                    f"<td class=\"num\">{hours(a.total(t, 'pc'))}</td><td class=\"num\">{a.total(t, 'letters'):,}</td>"
                    f"<td class=\"num\">{len(a.rows[t])}</td><td class=\"num\">{len(a.authored[t])}</td>"
                    f"<td class=\"num\">{sum(1 for _, heard in a.authored[t] if not heard)}</td><td class=\"barcell\"><span class=\"bar\" style=\"width:{w:.1f}%\"></span></td></tr>")
    body.append('<div class="table-wrap"><table><caption>Hours and letters by topic, across the transcript record</caption>'
                '<thead><tr><th scope="col">Topic</th><th scope="col">Staff and Council (h)</th><th scope="col">Spoken public comment (h)</th>'
                '<th scope="col">Letters</th><th scope="col">Meetings</th><th scope="col">Items members wrote</th>'
                '<th scope="col">Of those, not timed separately</th><th scope="col"><span class="sr-only">Meeting time, as a bar</span></th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')

    body.append('<h2 id="ranking">Items ranked by time</h2>'
                '<p>Every heard item, by its total minutes, so any one item can be read against everything else the '
                'Council heard.</p>')
    ranked = sorted(a.ranking.items(), key=lambda kv: -(kv[1]["disc"] + kv[1]["pc"]))
    ranked = [(k, v) for k, v in ranked if v["disc"] + v["pc"] >= 1]
    def rank_rows(rs, start):
        out = []
        for i, ((date, mid, _, t), v) in enumerate(rs, start):
            when = mlink(h, mid, h["fmt_date"](date))
            est = " (estimated)" if v["est"] else ""
            out.append(f"<tr><td class=\"num\">{i}</td><td class=\"num\">{when}</td><td>{esc(v['label'])}</td>"
                       f"<td>{link(t + '.html', a.thread_info[t]['label'])}</td><td class=\"num\">{minutes(v['disc'])}</td>"
                       f"<td class=\"num\">{minutes(v['pc'])}</td><td class=\"num\">{minutes(v['disc'] + v['pc'])}{est}</td></tr>")
        return "".join(out)
    head = ('<thead><tr><th scope="col">Rank</th><th scope="col">Meeting</th><th scope="col">Item</th><th scope="col">Topic</th>'
            '<th scope="col">Staff and Council (min)</th><th scope="col">Public comment (min)</th><th scope="col">Total (min)</th></tr></thead>')
    med = sorted(v["disc"] + v["pc"] for _, v in ranked)[len(ranked) // 2] if ranked else 0
    body.append(f'<p class="muted">{len(ranked)} heard items of a minute or more; the median item took {med:.0f} minutes.</p>')
    body.append(f'<div class="table-wrap"><table><caption>The 30 longest items</caption>{head}<tbody>{rank_rows(ranked[:30], 1)}</tbody></table></div>')
    body.append(f'<details><summary>All {len(ranked)} items</summary><div class="table-wrap"><table><caption>Every heard item, by total minutes</caption>'
                f'{head}<tbody>{rank_rows(ranked, 1)}</tbody></table></div></details>')

    by_pc = sorted(ranked, key=lambda kv: -kv[1]["pc"])[:20]
    body.append('<h2 id="ranking-comment">Items by spoken public comment</h2><p>The twenty items with the most minutes of '
                'spoken public comment. Letters are counted separately, on each topic\'s page.</p>')
    body.append(f'<div class="table-wrap"><table><caption>The 20 items with the most spoken public comment</caption>{head}'
                f'<tbody>{rank_rows(by_pc, 1)}</tbody></table></div>')
    body.append('<h2 id="auditor">City Auditor items</h2><p>Items presented by or about the City Auditor, wherever their '
                'subject put them.</p><ul>')
    for s, t, lab in sorted(a.auditor, key=lambda x: x[0]["meeting_date"]):
        when = mlink(h, s["meeting_id"], h["fmt_date"](s["meeting_date"]))
        body.append(f"<li>{when}: {esc(lab)} · {link(t + '.html', a.thread_info[t]['label'])} · {minutes(s['minutes'])} min"
                    f"{' (estimated)' if s['estimated'] else ''}</li>")
    body.append(f"</ul><p class=\"muted\">In all, {hours(sum(s['minutes'] for s, _, _ in a.auditor))} hours.</p>")
    body.append(connections(a, h, ""))
    body.append(unassigned(a, h))
    return page("Council time", "\n".join(body), 1, h["meta"], extra=h["time_footer"])


def aao_note(a, h):
    """Amendments to the Annual Appropriations Ordinance adopted on consent, at their first reading."""
    esc, fd = h["esc"], h["fmt_date"]
    rows = [c for t in a.consent for v in a.consent[t].values() for c in v
            if c["aao"] and c["aao"]["kind"] == "amendment" and c["aao"]["reading"] == "first"]
    if not rows:
        return ""
    lis = "".join(f"<li>{mlink(h, c['meeting_id'], fd(c['meeting_date']))}: amendment to the FY {esc(c['aao']['fiscal_year'])} "
                  f"budget, Ordinance {esc(c['aao']['ordinance'] or '')}: "
                  + (f"${c['aao']['net']:,.0f} net, ${c['aao']['gross']:,.0f} gross" if c["aao"]["net"] else "amount not printed in the agenda")
                  + "</li>" for c in sorted(rows, key=lambda c: c["meeting_date"]))
    return (f'<div class="note"><strong>Budget amendments on consent.</strong> These amendments to the Annual Appropriations '
            f'Ordinance were adopted on the consent calendar at first reading, with no separate discussion:<ul>{lis}</ul>'
            f'Each is counted once, at its first reading. For an argument about this, see '
            f'<a href="{h["bdp"]}consent-drip.html">Two Calendars</a>.</div>')


def connections(a, h, up):
    esc = h["esc"]
    out = ['<h2 id="connections">Connections between topics</h2><p>Where a speaker or a recorded action tied two '
           'topics together, quoted from the record.</p><ul>']
    for ln in sorted(a.links, key=lambda x: x["d"]):
        ths = " → ".join(h["link"](f"{up}{x}.html", a.thread_info[x]["label"]) for x in dict.fromkeys((ln["from"], ln["to"])))
        out.append(f"<li><strong>{esc(ln['label'])}</strong> ({ths})<br>{esc(ln['evidence'])}</li>")
    out.append("</ul>")
    return "".join(out)


def unassigned(a, h):
    esc = h["esc"]
    top = sorted(a.unassigned_letters.items(), key=lambda kv: -kv[1][0])[:12]
    rows = "".join(f"<tr><td>{esc(k)}</td><td class=\"num\">{v[0]:,}</td><td class=\"num\">{len(v[1])}</td></tr>" for k, v in top)
    return ('<h2 id="unassigned">Letters not counted toward any topic</h2>'
            '<p>Correspondence filed under no heard item and under a Clerk heading this site has not assigned to a '
            'topic. The largest:</p><div class="table-wrap"><table><caption>Largest unassigned correspondence headings</caption>'
            '<thead><tr><th scope="col">Clerk\'s heading</th><th scope="col">Letters</th><th scope="col">Meetings</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def render_thread(a, t, h):
    esc, link, page, fd = h["esc"], h["link"], h["page"], h["fmt_date"]
    info = a.thread_info[t]
    body = [DEFS, f"<h1>{esc(info['label'])}</h1>",
            f"<p class=\"muted\">{esc(info['group'] + ' · ') if info['group'] else ''}{link('index.html', 'All topics')}</p>",
            f"<p>{hours(a.total(t, 'disc'))} hours of staff and Council time and {hours(a.total(t, 'pc'))} hours of spoken "
            f"public comment, at {len(a.rows[t])} meetings, with {a.total(t, 'letters'):,} letters from the public"
            + (f" ({a.total(t, 'form'):,} of them form letters)" if a.total(t, 'form') else "") + ".</p>",
            METHOD_LINK, LEGEND.replace("</p>", ' · <a href="index.html#how-to-read">How to read these charts</a></p>'),
            axis_svg(), row_svg(a, t, height=90, esc=esc)]
    decs = a.decision_rows(t)
    if decs:
        body.append("<h2>Decisions</h2><ul>")
        for d, x, it in decs:
            vt = vote_text(it)
            where = mlink(h, x["meeting_id"], f"{fd(d)}, Item {x['item']}") if d else esc(x["meeting_id"])
            body.append(f"<li>{where}: {esc(x['label'])}{(' · final vote ' + esc(vt)) if vt else ''}"
                        + (f"<br><span class=\"muted\">{esc(it['heading'])}</span>" if it else "") + "</li>")
        body.append("</ul>")
    body.append("<h2>Meeting by meeting</h2>")
    rows = []
    dec_by_date = defaultdict(list)
    for d, x, it in decs:
        if d:
            dec_by_date[d].append((x, it))
    for date, r in sorted(a.rows[t].items()):
        mids = sorted(r["meeting_ids"])
        when = " · ".join(mlink(h, m, fd(date)) for m in mids) or esc(fd(date))
        labs = "<br>".join(esc(x) for x in r["labels"]) or '<span class="muted">letters only</span>'
        for x, it in dec_by_date.get(date, []):
            vt = vote_text(it)
            labs = (f'<span class="decision">▼ Decision: {esc(x["label"])}{" · final vote " + esc(vt) if vt else ""}</span><br>'
                    + labs)
        rows.append(f"<tr id=\"d-{date}\"><td class=\"num\">{when}</td><td>{labs}</td><td class=\"num\">{minutes(r['disc'])}</td>"
                    f"<td class=\"num\">{minutes(r['pc'])}</td><td class=\"num\">{r['letters']:,}"
                    f"{' (' + format(r['form'], ',') + ' form)' if r['form'] else ''}</td>"
                    f"<td>{'Estimated' if r['est'] else ''}</td></tr>")
    body.append('<div class="table-wrap"><table><caption>Time and letters at each meeting</caption><thead><tr>'
                '<th scope="col">Meeting</th><th scope="col">What was heard</th><th scope="col">Staff and Council (min)</th>'
                '<th scope="col">Public comment (min)</th><th scope="col">Letters</th><th scope="col">Estimate?</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')
    if a.authored[t]:
        rows = []
        for it, heard in sorted(a.authored[t], key=lambda x: x[0]["meeting_date"]):
            authors = h["roles_html"](it["record_id"])
            rows.append(f"<tr><td class=\"num\">{mlink(h, it['meeting_id'], fd(it['meeting_date']))}</td>"
                        f"<td>Item {esc(it['item'])}: {esc(it['heading'])}<br><span class=\"roles\">{authors}</span></td>"
                        f"<td>{esc(it['section'] or '')}</td><td>{'Timed' if heard else 'Not timed separately'}</td></tr>")
        n_not = sum(1 for _, heard in a.authored[t] if not heard)
        body.append(f'<h2 id="authored">Items Council members wrote</h2><p>{len(a.authored[t])} items, {n_not} of them never timed separately: '
                    'adopted on the consent calendar, or taken up within another part of the meeting. Those took no meeting time, but each was written, placed on an agenda '
                    'and reviewed by staff.</p><div class="table-wrap"><table><caption>Member-authored items on this subject</caption>'
                    '<thead><tr><th scope="col">Meeting</th><th scope="col">Item, and who brought it</th>'
                    '<th scope="col">Agenda section</th><th scope="col">Meeting time</th></tr></thead>'
                    f'<tbody>{"".join(rows)}</tbody></table></div>')
    cs = [c for _, v in sorted(a.consent[t].items()) for c in v]
    if cs:
        rows = []
        for c in cs:
            amt = f"${c['amount']:,.0f}<br><span class=\"muted\">{esc(c['amount_source'])}</span>" if c["amount"] else '<span class="muted">none printed</span>'
            why = "; ".join(esc(r) for r in c["reasons"]) or '<span class="muted">nothing beyond the item</span>'
            rows.append(f"<tr><td class=\"num\">{mlink(h, c['meeting_id'], fd(c['meeting_date']))}</td>"
                        f"<td>Item {esc(c['item'])}: {esc(c['heading'])}<br><span class=\"muted\">{esc(c['from'] or '')}</span></td>"
                        f"<td class=\"num\">{amt}</td><td>{why}</td></tr>")
        n_pb = sum(1 for c in cs if c["policy_bearing"])
        body.append(f'<h2 id="consent">On the consent calendar</h2><p>{len(cs)} items on this subject were adopted on the consent '
                    f'calendar, in one motion with the rest of the calendar and no separate discussion; {n_pb} of them show, '
                    'in the annotated agenda, an ordinance, member authorship, a move from the action calendar, revision at '
                    'adoption, speakers or letters. An amount is as printed: the largest figure under Financial Implications, '
                    'otherwise the first in the Recommendation. Which items belong on which calendar is a Council choice; for an '
                    f'argument that the sorting does not track the size of the commitment, see the Berkeley Decision Project\'s '
                    f'<a href="{h["bdp"]}consent-drip.html">Two Calendars</a>.</p>'
                    '<div class="table-wrap"><table><caption>Consent calendar items on this subject</caption><thead><tr>'
                    '<th scope="col">Meeting</th><th scope="col">Item</th><th scope="col">Amount</th>'
                    f'<th scope="col">What the agenda shows</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    if t == "gaza":
        body.append("<h2>Public comment outside the agenda item</h2><p>Turns about Gaza, Israel or Palestine during "
                    "general and consent public comment are counted above when the turn was about that subject. "
                    f"{len(a.turns_partial)} turns that mainly concerned something else and raised it only in part are "
                    f"not counted; together they ran {sum(x['minutes'] or 0 for x in a.turns_partial):.0f} minutes.</p>")
    ls = [ln for ln in a.links if t in (ln["from"], ln["to"])]
    if ls:
        body.append("<h2>Connections to other topics</h2><ul>")
        for ln in ls:
            other = ln["to"] if ln["from"] == t else ln["from"]
            body.append(f"<li><strong>{esc(ln['label'])}</strong> ({link(other + '.html', a.thread_info[other]['label'])})<br>{esc(ln['evidence'])}</li>")
        body.append("</ul>")
    body.append(f"<p class=\"muted\">Data: {link('../data/council-time/segments.json', 'segments.json')}, "
                f"{link('../data/council-time/correspondence.json', 'correspondence.json')}, and the classification in "
                f"{link(h['repo'] + '/blob/main/data/review/council-time/threads.json', 'the topic classification')}.</p>")
    return page(info["label"], "\n".join(body), 1, h["meta"], extra=h["time_footer"])


def segments_table(segs, a, h, caption, up="../"):
    esc, link = h["esc"], h["link"]
    rows = []
    for s in segs:
        c = a.seg_class[s["segment_id"]]
        th = "" if c["thread"] == "routine" else link(f"{up}time/{c['thread']}.html", a.thread_info[c["thread"]]["label"])
        commit = a.meta["source"]["archive_commit"]
        src = link(f"{ARCHIVE_BLOB}/{commit}/L3/council-captions/{s['structure_archive_id']}.json", locator_text(s["locator"]))
        rows.append(f"<tr><td>{esc(a.label(s))}</td><td>{th or '<span class=\"muted\">routine</span>'}</td>"
                    f"<td class=\"num\">{minutes(s['minutes'])}</td><td class=\"num\">{minutes(s['public_comment_minutes'])}</td>"
                    f"<td class=\"num\">{src}{' (estimated)' if s['estimated'] else ''}</td></tr>")
    return (f'<div class="table-wrap"><table><caption>{esc(caption)}</caption><thead><tr><th scope="col">Part of the meeting</th>'
            '<th scope="col">Topic</th><th scope="col">Minutes</th><th scope="col">Public comment (min)</th>'
            f'<th scope="col">Transcript</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def meeting_block(a, m, h):
    """How the meeting's time and letters divided by topic, then every part of the meeting in order."""
    esc, link = h["esc"], h["link"]
    segs = a.by_meeting.get(m["meeting_id"], [])
    letters = a.letters_by_meeting.get(m["meeting_id"], Counter())
    if not segs and not letters and not any(h["item_roles"].get(it["record_id"]) for it in h["items_by_meeting"].get(m["meeting_id"], [])):
        return ""
    by = defaultdict(lambda: {"disc": 0.0, "pc": 0.0, "labels": [], "est": False})
    for s in segs:
        t = a.seg_class[s["segment_id"]]["thread"]
        r = by[t]
        r["disc"] += (s["minutes"] or 0) - (s["public_comment_minutes"] or 0)
        r["pc"] += s["public_comment_minutes"] or 0
        r["est"] |= s["estimated"]
        if t != "routine":
            lab = a.label(s)
            if lab not in r["labels"]:
                r["labels"].append(lab)
    topics = [t for t in a.thread_ids() if t in by or letters.get(t)]
    rows = []
    for t in topics:
        r = by.get(t, {"disc": 0, "pc": 0, "labels": [], "est": False})
        what = "<br>".join(esc(x) for x in r["labels"]) or '<span class="muted">letters only</span>'
        rows.append(f"<tr><th scope=\"row\">{link('../time/' + t + '.html', a.thread_info[t]['label'])}</th><td>{what}</td>"
                    f"<td class=\"num\">{minutes(r['disc']) if r['labels'] else ''}</td><td class=\"num\">{minutes(r['pc']) if r['labels'] else ''}</td>"
                    f"<td class=\"num\">{letters.get(t, 0) or ''}</td></tr>")
    if "routine" in by:
        r = by["routine"]
        n = sum(1 for s in segs if a.seg_class[s["segment_id"]]["thread"] == "routine")
        rows.append(f"<tr class=\"routine\"><th scope=\"row\">Routine business</th><td class=\"muted\">{n} parts: ceremonies, the consent "
                    f"calendar as a block, comments, general public comment, recesses, adjournment</td>"
                    f"<td class=\"num\">{minutes(r['disc'])}</td><td class=\"num\">{minutes(r['pc'])}</td><td class=\"num\"></td></tr>")
    if letters.get(None):
        rows.append(f"<tr class=\"routine\"><th scope=\"row\">Letters on no topic</th><td class=\"muted\">filed under headings this site "
                    f"has not assigned to a topic</td><td></td><td></td><td class=\"num\">{letters[None]}</td></tr>")
    total = sum(s["minutes"] or 0 for s in segs)
    est = any(s["estimated"] for s in segs)
    out = ["<h2 id=\"council-time\">This meeting at a glance</h2>",
           f"<p>{hours(total)} hours in the transcript{' (estimated)' if est else ''}, and "
           f"{sum(letters.values()):,} letters from the public, by topic.</p>" + METHOD_LINK,
           '<div class="table-wrap"><table><caption>Time and letters by topic</caption><thead><tr><th scope="col">Topic</th>'
           '<th scope="col">What was heard</th><th scope="col">Staff and Council (min)</th><th scope="col">Public comment (min)</th>'
           f'<th scope="col">Letters</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>']
    brought = [it for it in h["items_by_meeting"].get(m["meeting_id"], []) if h["item_roles"].get(it["record_id"])]
    if brought:
        rows = []
        for it in brought:
            t = a.record_thread.get(it["record_id"]) or h["item_thread"].get(it["record_id"])
            topic = ("Routine" if t == "routine" else link("../time/" + t + ".html", a.thread_info[t]["label"])) if t else ""
            heard = "Timed" if it["record_id"] in a.record_thread else esc(it["section"] or "")
            rows.append(f"<tr><td class=\"num\">{esc(it['item'])}</td><td>{esc(it['heading'])}<br>"
                        f"<span class=\"roles\">{h['roles_html'](it['record_id'])}</span></td><td>{topic}</td><td>{heard}</td></tr>")
        out.append('<h3 id="brought">Items Council members brought</h3>'
                   '<p class="muted">Every item on this agenda that names a Council member, with the role the agenda gives each. '
                   'The members\' pages show the same items from the member\'s side.</p>'
                   '<div class="table-wrap"><table><caption>Member items on this agenda</caption><thead><tr><th scope="col">Item</th>'
                   '<th scope="col">Item, and who brought it</th><th scope="col">Topic</th><th scope="col">Timed, or the agenda section</th>'
                   f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    rec = m.get("city_links", {}).get("video")
    if rec:
        out.append(f'<p>{link(rec, "Watch the City\'s recording")}. <span class="muted">Times in the table below are from the '
                   'Zoom captions; the City\'s video can run later, because it keeps recording through recesses.</span></p>')
    if segs:
        out.append(f"<details><summary>Every part of the meeting, in order ({len(segs)})</summary>"
                   + segments_table(segs, a, h, "Parts of the meeting, in order") + "</details>")
    return "".join(out)


def matter_block(a, m, h):
    segs = []
    for it in m["agenda_items"]:
        segs += a.by_record.get(f"{it['meeting_id']}--item-{it['item']}", [])
    if not segs:
        return ""
    total = sum(s["minutes"] or 0 for s in segs)
    pc = sum(s["public_comment_minutes"] or 0 for s in segs)
    return ("<h2 id=\"council-time\">Council time on this matter</h2>"
            f"<p>{minutes(total)} minutes when it was heard, {minutes(pc)} of them public comment.</p>"
            + segments_table(segs, a, h, "Where the Council heard it"))


STATUS_ORDER = ("in_progress_reported", "not_yet_due", "no_due_date_stated", "delayed", "unknown_no_update_located",
                "reported_complete", "reported_not_met", "completion_verified", "cancelled_or_superseded")
STATUS_NOTE = {
    "in_progress_reported": "The responsible party reports the work under way.",
    "not_yet_due": "A stated date or period has not passed.",
    "no_due_date_stated": "The source states no date for the work.",
    "delayed": "A stated date passed and the source says so.",
    "unknown_no_update_located": "No update was found; each matter page says what was searched. Work may still have occurred.",
    "reported_complete": "The responsible party reports the work done. That is its statement, unverified by anyone else.",
    "reported_not_met": "The responsible party, or a report it submitted, states the work was not done or the target not met.",
    "completion_verified": "A record independent of the responsible party shows the work done.",
    "cancelled_or_superseded": "The source records the commitment withdrawn or replaced.",
}


def status_counts(cs, labels):
    """'2 reported complete · 1 in progress, as reported' for a list of commitments, in status order."""
    n = Counter(tracked_mod.current_status(c)["status"] for c in cs)
    return " · ".join(f"{n[k]} {labels[k][0].lower() + labels[k][1:]}" for k in STATUS_ORDER if n.get(k))


def render_commitments(a, t, h):
    esc, link, page, fd = h["esc"], h["link"], h["page"], h["fmt_date"]
    matters = {m["id"]: m for m in t["matters.json"]}
    labels = dict(h["status_labels"])
    groups = defaultdict(list)
    for c in t["commitments.json"]:
        th = a.matter_thread.get(c["matter_id"], "other")
        g = a.thread_info[th]["group"] or a.thread_info[th]["label"]
        groups[g].append((c, th, tracked_mod.current_status(c)))
    order = sorted(groups, key=lambda g: (g != FINANCES, g == a.thread_info["other"]["label"], g))
    counts = defaultdict(int)
    for g in groups.values():
        for _, _, cur in g:
            counts[cur["status"]] += 1
    body = ["<h1>Commitments</h1>",
            "<p>Every specific, checkable commitment the tracker follows: what was undertaken, by whom, by when, and the "
            "status the record supports. Open commitments come first in each group. Each links to its matter, where "
            "every statement is cited.</p>",
            '<p class="note">A status describes the evidence located as of the date shown. "No update located" is a gap '
            'in the public record, and work may still have occurred. "Reported complete" and "reported not met" are the '
            'responsible party\'s statements; "completion verified" needs independent evidence.</p>',
            '<h2 id="status">By status</h2><ul>']
    for k in STATUS_ORDER:
        if counts.get(k):
            body.append(f'<li><a href="#status-{k}">{esc(labels[k])}</a>: {counts[k]}</li>')
    body.append("</ul><p class=\"muted\">Each status links to the list of its commitments, below the subject tables. "
                f"Subjects use the same topics as {link('../time/index.html', 'Council time')}.</p>")
    for g in order:
        anchor = "city-finances" if g == FINANCES else g.lower().replace(" ", "-").replace(",", "").replace("&", "and")
        rows = []
        for c, th, cur in sorted(groups[g], key=lambda x: (x[2]["status"] not in OPEN_STATUSES, x[0]["matter_id"], x[0]["id"])):
            m = matters[c["matter_id"]]
            due = esc(c["due"]["as_stated"]) if c["due"]["as_stated"] else '<span class="muted">not stated</span>'
            state = "Open" if cur["status"] in OPEN_STATUSES else "Closed"
            rows.append(f"<tr><td>{esc(c['label'])}<br><span class=\"muted\">{esc(c['actor'])}</span></td>"
                        f"<td>{link('../matters/' + m['id'] + '.html', m['title'])}</td><td>{due}</td>"
                        f"<td><strong>{esc(labels[cur['status']])}</strong><br><span class=\"muted\">as of {esc(fd(cur['as_of']))} · {state}</span></td></tr>")
        n_open = sum(1 for _, _, cur in groups[g] if cur["status"] in OPEN_STATUSES)
        body.append(f'<h2 id="{anchor}">{esc(g)} <span class="muted">· {n_open} open of {len(groups[g])}</span></h2>'
                    '<div class="table-wrap"><table><caption>' + esc(g) + ': commitments</caption><thead><tr>'
                    '<th scope="col">Commitment and who is responsible</th><th scope="col">Matter</th>'
                    '<th scope="col">Date, as stated</th><th scope="col">Status</th></tr></thead>'
                    f'<tbody>{"".join(rows)}</tbody></table></div>')
    body.append('<h2 id="by-status">Commitments by status</h2>')
    allc = [(c, th, cur) for g in groups.values() for c, th, cur in g]
    for k in STATUS_ORDER:
        cs = sorted((x for x in allc if x[2]["status"] == k), key=lambda x: (x[0]["matter_id"], x[0]["id"]))
        if not cs:
            continue
        lis = "".join(f"<li>{esc(c['label'])} <span class=\"muted\">· {esc(c['actor'])} · "
                      f"{link('../matters/' + c['matter_id'] + '.html', matters[c['matter_id']]['title'])} · as of {esc(fd(cur['as_of']))}</span></li>"
                      for c, th, cur in cs)
        body.append(f'<h3 id="status-{k}">{esc(labels[k])} <span class="muted">· {len(cs)}</span></h3>'
                    f'<p class="muted">{esc(STATUS_NOTE[k])}</p><ul>{lis}</ul>')
    return page("Commitments", "\n".join(body), 1, h["meta"])


def keyframes(n):
    """Each question holds for 1/n of the cycle, fading in and out over its first and last few percent."""
    slot = 100 / n
    return ("@keyframes cw-q{0%{opacity:0;visibility:visible}" f"{slot * .12:.2f}%{{opacity:1}}"
            f"{slot * .88:.2f}%{{opacity:1}}{slot:.2f}%{{opacity:0;visibility:hidden}}100%{{opacity:0;visibility:hidden}}}}")


# The questions the home page offers. Each is a factual question this site's records answer, and each links to
# the view that answers it. None states a conclusion.
QUESTIONS = [
    # Shown three at a time, in this order; keep each group to distinct kinds of question.
    ("What did the Council decide at its most recent meeting?", "{latest_meeting}"),
    ("How much time has the Council spent on the budget, and how much of it was public comment?", "time/budget.html"),
    ("Which commitments has the City reported complete?", "commitments/index.html#status-reported_complete"),
    ("Which items drew the most spoken public comment?", "time/index.html#ranking-comment"),
    ("How many items has Councilmember Bartlett, for example, authored, and on what subjects?", "members/bartlett.html#items"),
    ("Which commitments have no due date stated?", "commitments/index.html#status-no_due_date_stated"),
    ("How much time did the Council spend on housing and zoning?", "time/zoning.html"),
    ("Where has the Council split, and how did each member vote?", "members/index.html#divided"),
    ("What did City management commit to after the contracts audit, and what has been reported since?", "matters/contracts-audit-2026.html"),
    ("How much spoken and written public comment did Flock and surveillance technology draw?", "time/flock.html"),
    ("When did the Council hear Hopkins Street, and what did it decide?", "time/hopkins.html"),
    ("Which deliverables related to City finances are still open?", "commitments/index.html#city-finances"),
    ("How much meeting time went to Gaza, and how much of it was public comment?", "time/gaza.html"),
    ("How many positions on state, federal and international matters have Council members written?", "time/external.html#authored"),
    ("Which City finance audits came before the Council while it was shaping the 2026 tax measures?", "time/index.html#city-finances"),
]


GROUP = 3


def questions(h, available):
    """The questions whose answering page (and anchor) the site actually has, with their links resolved."""
    out = []
    for q, href in QUESTIONS:
        href = href.format(latest_meeting=h.get("latest_meeting") or "")
        if href and available(href):
            out.append((q, href))
    return out


def questions_block(h, available):
    """Three questions at a time, rotating by CSS alone; a reversible control shows them all. Every question is
    in the HTML as an ordinary list, so without CSS, with reduced motion, or in print the reader sees them all."""
    esc = h["esc"]
    qs = questions(h, available)
    if not qs:
        return ""
    groups = [qs[i:i + GROUP] for i in range(0, len(qs), GROUP)]
    lis = "".join(f'<li class="grp" style="--i:{g}"><ul>'
                  + "".join(f'<li><a href="{esc(href)}">{esc(q)}</a></li>' for q, href in grp) + "</ul></li>"
                  for g, grp in enumerate(groups))
    return f"""<section class="ask" aria-labelledby="ask-h">
<h2 id="ask-h">Questions the record can answer</h2>
<input type="checkbox" id="allq" class="sr-only">
<ul class="rotator" style="--n:{len(groups)}">{lis}</ul>
<label for="allq" class="allq"><span class="more">Show all {len(qs)} questions</span><span class="fewer">Show fewer</span></label>
</section>"""


CSS = """
:root{--c-staff:#3b6ea5;--c-pc:#d08a2c;--c-letters:#6b6b6b;--c-consent:#7a5aa6}
@media (prefers-color-scheme:dark){:root{--c-staff:#7fa8d8;--c-pc:#e6a85a;--c-letters:#a8a8a8;--c-consent:#b49ae0}}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
svg.row,svg.axis{display:block;width:100%;height:auto}
section.thread h3{margin:14px 0 2px;font-size:1rem}
h2 .muted,h3 .muted{font-weight:400}
ul.decisions{margin:0 0 6px;padding-left:20px;font-size:.9rem;color:var(--muted)}
.legend{font-size:.9rem;color:var(--muted)}
.key{display:inline-block;width:12px;height:12px;vertical-align:-1px;margin:0 4px 0 10px}
.key.staff{background:var(--c-staff)}.key.pc{background:var(--c-pc)}
.key.est{background:repeating-linear-gradient(45deg,var(--c-staff) 0 3px,var(--bg) 3px 5px)}
.key.letters{border:1.5px solid var(--c-letters);border-radius:50%}
.key.dec{width:auto;height:auto;font-size:.8rem}
.key.consent{width:4px;height:12px;background:var(--c-consent)}
td.barcell{width:30%}.bar{display:block;height:10px;background:var(--c-staff)}
svg.row a.bar:focus-visible rect:first-child{fill:var(--soft);stroke:var(--accent);stroke-width:2}
svg.row a.bar:hover rect:first-child{fill:var(--soft)}
svg.row a.bar.sel rect:first-child{fill:var(--soft);stroke:var(--accent);stroke-width:2}
.readout{margin:4px 0 10px;padding:8px 12px;border-left:4px solid var(--accent);background:var(--soft);font-size:.95rem}
.readout a{margin-left:.4em;white-space:nowrap}
tr:target td{background:var(--soft)}
tr.routine th,tr.routine td{color:var(--muted);font-weight:400}
tr:target td:first-child{box-shadow:inset 4px 0 0 var(--accent)}
.decision{font-weight:600}
.roles{font-size:.9rem}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
.how-to-read{margin:20px 0;padding:14px 16px;border:1px solid var(--line);border-radius:6px}
.how-to-read h2{margin:0 0 4px;font-size:1.05rem}
.how-grid{display:grid;grid-template-columns:230px 1fr;gap:16px;align-items:start}
.how-grid ol{padding-left:22px;margin:8px 0 0}.how-grid li{margin-bottom:6px}
svg.how{width:230px;height:auto}
@media (max-width:600px){.how-grid{grid-template-columns:1fr}svg.how{width:200px;margin:0 auto;display:block}}
.analysis{border:1px solid var(--line);border-radius:6px;padding:4px 14px;margin:14px 0;font-size:.95rem}
.analysis h2{font-size:.95rem;margin:8px 0 4px;color:var(--muted)}
.ask{background:var(--soft);padding:16px 18px;margin:20px 0 28px;border-radius:6px}
.ask h2{margin:0 0 10px;font-size:.95rem;color:var(--muted);font-weight:600}
.rotator,.rotator ul{list-style:none;margin:0;padding:0}
.rotator li li{font-size:1.15rem;line-height:1.35;margin:0 0 10px}
.rotator li li:last-child{margin-bottom:0}
.rotator > li + li{margin-top:10px}
.allq{display:none;font-size:.85rem;color:var(--muted);cursor:pointer;text-decoration:underline;margin-top:10px}
.allq .fewer{display:none}
#allq:checked~.allq .more{display:none}
#allq:checked~.allq .fewer{display:inline}
#allq:focus-visible~.allq{outline:3px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:no-preference){
 .allq{display:inline-block}
 #allq:not(:checked)~.rotator{display:grid}
 #allq:not(:checked)~.rotator > li{grid-area:1/1;margin:0;opacity:0;visibility:hidden;
   animation:cw-q calc(var(--n)*9s) linear infinite;animation-delay:calc(var(--i)*9s)}
 #allq:not(:checked)~.rotator:hover > li,#allq:not(:checked)~.rotator:focus-within > li{animation-play-state:paused}
}
@media print{.allq{display:none}.rotator > li{opacity:1!important;visibility:visible!important;animation:none!important}}
"""
CSS = CSS.replace("__KEYFRAMES__", "")


def css(n):
    return CSS + keyframes(max(n, 1))
