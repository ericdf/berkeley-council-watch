"""Render the static site from the generated dataset.

Every link is relative, so the site works under any GitHub Pages base path, including direct
navigation to a detail page. No client-side JavaScript; facts, citations and dates are in the HTML.
"""
import datetime
import html
import os
import shutil

from . import tracked as tracked_mod
from .generate import OUT_DIR
from .validate import load_dataset

SITE_DIR = "_site"
TITLE = "Berkeley Council Watch"
TAGLINE = "Tracking Council commitments and City follow-through."
SUBSTACK = "https://berkeleydecisionproject.substack.com"
BDP = "https://ericdf.github.io/berkeley-decision-project/index.html"
REPO = "https://github.com/ericdf/berkeley-council-watch"
ARCHIVE = "https://github.com/ericdf/berkeley-public-records"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"

STATUS_LABELS = {
    "scheduled": "Scheduled",
    "source_archived": "Agenda source archived",
    "awaiting_meeting_record": "Awaiting meeting record",
    "action_recorded": "Action recorded",
}
TYPE_LABELS = {"regular": "Regular", "special": "Special", "closed session": "Closed session",
               "canceled": "Canceled"}
ROLE_LABELS = {"agenda_packet": "Agenda packet", "annotated_agenda": "Annotated agenda",
               "captions": "Caption transcript"}

CSS = """\
:root{--fg:#1b1b1b;--muted:#4a4a4a;--bg:#fff;--line:#d6d6d6;--accent:#0b5394;--soft:#f3f6f9}
@media (prefers-color-scheme:dark){:root{--fg:#ececec;--muted:#b9b9b9;--bg:#121417;--line:#3a3f45;--accent:#8ab8f0;--soft:#1c2026}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--fg);background:var(--bg)}
a{color:var(--accent)}
a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.skip{position:absolute;left:-999px}.skip:focus{left:16px;top:8px;background:var(--bg);padding:4px 8px}
header,main,footer{max-width:960px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--line);padding-top:16px;padding-bottom:12px}
header .name{font-size:1.25rem;font-weight:700;text-decoration:none;color:var(--fg)}
header .tagline{margin:2px 0 8px;color:var(--muted)}
nav ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:16px}
h1{font-size:1.6rem;line-height:1.25;margin:24px 0 8px}
h2{font-size:1.2rem;margin:28px 0 8px}
.note{background:var(--soft);border-left:4px solid var(--accent);padding:10px 14px;margin:16px 0}
.muted{color:var(--muted)}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}
caption{text-align:left;font-weight:600;padding:4px 0}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-weight:600}
td.num{white-space:nowrap}
ul.links{margin:4px 0;padding-left:20px}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px}dt{font-weight:600}dd{margin:0}
footer{border-top:1px solid var(--line);margin-top:40px;padding-top:12px;padding-bottom:32px;font-size:.92rem;color:var(--muted)}
code{font-size:.9em;overflow-wrap:anywhere}
blockquote{margin:4px 0 6px;padding-left:10px;border-left:3px solid var(--line)}
details{margin-top:4px}summary{cursor:pointer}
h3{font-size:1.05rem;margin:20px 0 4px}h4{font-size:1rem;margin:16px 0 4px}
"""


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def link(href, text):
    return f'<a href="{esc(href)}">{esc(text)}</a>'


def page(title, body, depth, meta):
    up = "../" * depth
    src = meta["source"]
    commit = src["archive_commit"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {TITLE}</title>
<link rel="stylesheet" href="{up}assets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header>
<a class="name" href="{up}index.html">{TITLE}</a>
<p class="tagline">{TAGLINE}</p>
<nav aria-label="Site"><ul>
<li><a href="{up}index.html">Home</a></li>
<li><a href="{up}matters/index.html">Tracked matters</a></li>
<li><a href="{up}meetings/index.html">Meetings</a></li>
<li><a href="{up}about.html">About the records</a></li>
<li><a href="{up}data/index.html">Data</a></li>
</ul></nav>
</header>
<main id="main">
{body}
</main>
<footer>
<p>Agenda records generated from the public-records archive at commit
<a href="{ARCHIVE}/tree/{esc(commit)}"><code>{esc(commit[:12])}</code></a>, using the City meeting listing
retrieved {esc(fmt_date(src['catalog_retrieved']))}.</p>
<p>For analysis of the issues behind tracked matters, read the <a href="{BDP}">Berkeley Decision Project</a>
and subscribe on <a href="{SUBSTACK}">Substack</a>.</p>
<p>Original written content by Berkeley Council Watch is licensed under <a href="{CC_BY}">CC BY 4.0</a>.
Please credit Berkeley Council Watch, link to this page and the license, and indicate changes.
Official records, source documents and quoted third-party material keep their own terms and are not
relicensed by this notice.</p>
<p><a href="{REPO}">Source code and data</a> ·
<a href="{REPO}/issues">Report a correction</a></p>
</footer>
</body>
</html>
"""


def city_links(m):
    labels = [("agenda_html", "Agenda"), ("agenda_packet", "Agenda packet"),
              ("annotated_agenda", "Annotated agenda"), ("video", "Video")]
    out = [link(m["city_links"][k], t) for k, t in labels if m["city_links"].get(k)]
    return " · ".join(out) if out else '<span class="muted">none listed</span>'


def archived_summary(m):
    parts = [ROLE_LABELS[r] for r in ("agenda_packet", "annotated_agenda", "captions") if m["archived"].get(r)]
    return ", ".join(parts) if parts else '<span class="muted">none archived</span>'


def meetings_table(meetings, depth, caption):
    up = "../" * depth
    rows = []
    for m in meetings:
        items = str(m["item_count"]) if m["item_count"] else '<span class="muted">—</span>'
        rows.append(
            f"<tr><td class=\"num\">{link(f'{up}meetings/{m['meeting_id']}.html', fmt_date(m['meeting_date']))}</td>"
            f"<td>{esc(TYPE_LABELS.get(m['meeting_type'], m['meeting_type']))}</td>"
            f"<td>{archived_summary(m)}</td><td>{items}</td></tr>")
    return (f'<div class="table-wrap"><table><caption>{esc(caption)}</caption>'
            '<thead><tr><th scope="col">Date</th><th scope="col">Meeting</th>'
            '<th scope="col">Archived records</th><th scope="col">Indexed items</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


SCOPE_NOTE = ("These are agenda records: what the City scheduled, with links to the City's documents and "
              "the archived copies. An agenda entry shows that an item was scheduled. It does not show "
              "that the item was heard, adopted, amended, continued or completed.")


def render_index(d):
    meetings, meta = d["meetings.json"], d["meta.json"]
    c = meta["counts"]
    with_items = [m for m in meetings if m["item_count"]]
    recent = [m for m in meetings if m["meeting_type"] != "canceled"][:12]
    body = f"""<h1>{TITLE}</h1>
<p>A public, source-linked record of what Berkeley's City Council and City government said would happen,
what they directed, and what the public record shows afterward.</p>
<p>{link("matters/index.html", "Tracked matters")} follow specific commitments: who made them, what was
due, and what the record shows since, with every statement linked to its source.</p>
<p class="note">The meeting pages hold agenda records. {SCOPE_NOTE}</p>
<h2>What is here now</h2>
<ul>
<li>{c['meetings']} City Council meetings listed by the City, {c['meetings_with_archived_documents']} with archived
records.</li>
<li>{c['items']} agenda items from {c['meetings_with_indexed_items']} indexed agenda
packet{'s' if c['meetings_with_indexed_items'] != 1 else ''}.</li>
</ul>
"""
    if with_items:
        body += meetings_table(with_items, 0, "Meetings with indexed agenda items")
    body += meetings_table(recent, 0, "Most recent meetings")
    body += f'<p>{link("meetings/index.html", "All meetings")}</p>'
    return page("Home", body, 0, meta)


def render_meetings(d):
    meetings, meta = d["meetings.json"], d["meta.json"]
    body = ["<h1>City Council meetings</h1>",
            f"<p>Every meeting on the City's agenda listing, newest first. {esc(SCOPE_NOTE)}</p>"]
    years = sorted({m["meeting_date"][:4] for m in meetings}, reverse=True)
    body.append("<p>Jump to: " + " · ".join(f'<a href="#y{y}">{y}</a>' for y in years) + "</p>")
    for y in years:
        body.append(f'<h2 id="y{y}">{y}</h2>')
        body.append(meetings_table([m for m in meetings if m["meeting_date"].startswith(y)], 1, f"Meetings in {y}"))
    return page("Meetings", "\n".join(body), 1, meta)


def docref_list(refs):
    out = []
    for r in refs:
        bits = []
        if r.get("archive_url"):
            bits.append(link(r["archive_url"], "archived copy"))
        if r.get("city_source_url"):
            bits.append(link(r["city_source_url"], "City link"))
        bits.append(link(r["manifest_url"], "archive record"))
        flags = []
        if r.get("version_label"):
            flags.append(esc(r["version_label"]))
        if r.get("listed_by_city") is False:
            flags.append("no longer the version the City links")
        flag = f' <span class="muted">({"; ".join(flags)})</span>' if flags else ""
        out.append(f"<li>{esc(r['title'] or r['archive_id'])}{flag}<br>"
                   f"{' · '.join(bits)}<br><span class=\"muted\">Retrieved {esc(fmt_date(r['retrieved']) if r.get('retrieved') else 'date not recorded')};"
                   f" sha256 <code>{esc(r['sha256'][:16])}…</code></span></li>")
    return f'<ul class="links">{"".join(out)}</ul>'


def render_meeting(m, items, meta):
    title = f"{TYPE_LABELS.get(m['meeting_type'], m['meeting_type'])} meeting, {fmt_date(m['meeting_date'])}"
    body = [f"<h1>{esc(title)}</h1>",
            f"<p class=\"muted\">{esc(m['name'])} · last checked {esc(fmt_date(m['last_checked_at']))}</p>",
            "<h2>City records</h2>",
            f"<p>{link(m['city_page_url'], 'City meeting page')} · {city_links(m)}</p>",
            "<h2>Archived records</h2>"]
    if m["archived"]:
        for role in ("agenda_packet", "annotated_agenda", "captions"):
            if m["archived"].get(role):
                body.append(f"<h3>{ROLE_LABELS[role]}</h3>{docref_list(m['archived'][role])}")
    else:
        body.append("<p>No records for this meeting are archived yet.</p>")
    body.append("<h2>Agenda items</h2>")
    if items:
        body.append(f'<p class="note">{esc(SCOPE_NOTE)}</p>')
        rows = []
        for it in items:
            p0, p1 = it["source_locator"]["pages"]
            pages = f"p. {p0}" if p0 == p1 else f"pp. {p0}–{p1}"
            rows.append(
                f"<tr><td class=\"num\" id=\"item-{esc(it['agenda_item_number'])}\">{esc(it['agenda_item_number'])}</td>"
                f"<td>{esc(it['official_title'])}<br><span class=\"muted\">{esc(it['section'] or '')}</span></td>"
                f"<td>{esc(STATUS_LABELS[it['status']])}</td>"
                f"<td>{link(it['archive_url'], 'Archived packet')}, {pages}<br>"
                f"{link(it['city_source_url'], 'City packet')}</td></tr>")
        body.append('<div class="table-wrap"><table><caption>Items in the archived agenda packet</caption>'
                    '<thead><tr><th scope="col">Item</th><th scope="col">Title as printed</th>'
                    '<th scope="col">Status</th><th scope="col">Source</th></tr></thead>'
                    f'<tbody>{"".join(rows)}</tbody></table></div>')
        body.append('<p class="muted">Page numbers count the pages of the archived packet\'s text, from 1.</p>')
    else:
        body.append("<p>No agenda items are indexed for this meeting yet. Use the City and archived "
                    "records above.</p>")
    return page(title, "\n".join(body), 1, meta)


def render_about(d):
    meta = d["meta.json"]
    src = meta["source"]
    body = f"""<h1>About the records</h1>
<p>Berkeley Council Watch puts public commitments and follow-through back in view, with links to the
underlying record. This first part of the site holds agenda records. It is generated by code from the
public-records archive, without human editing or AI, and holds only facts copied from official records.</p>
<h2>Where the records come from</h2>
<p>The source is the <a href="{ARCHIVE}">Berkeley public-records archive</a>, which keeps the City's documents
with their fingerprints and provenance. Each meeting comes from the City's
<a href="{esc(src['catalog_url'])}">City Council agenda listing</a>. Each agenda item comes from the archive's
index of an agenda packet: its number, section and title as printed, and the pages that hold its material.</p>
<h2>What the statuses mean</h2>
<dl>
<dt>{STATUS_LABELS['scheduled']}</dt><dd>The City listed the item on an agenda. The agenda source is not yet archived.</dd>
<dt>{STATUS_LABELS['source_archived']}</dt><dd>The agenda packet that lists the item is archived. This shows the item
was scheduled, and nothing about what happened to it.</dd>
<dt>{STATUS_LABELS['awaiting_meeting_record']}</dt><dd>Reserved for an item whose meeting record is expected but
not yet available.</dd>
<dt>{STATUS_LABELS['action_recorded']}</dt><dd>Reserved for an item whose action an authoritative structured
record states. Not yet assigned to any item.</dd>
</dl>
<p>A status never advances because time has passed. Unknown or conflicting information stays unknown.</p>
<h2>What this part of the site does not do</h2>
<p>It does not say what a Councilmember meant, why an item was handled as it was, whether a promise was
made or kept, or whether a policy worked. Those records need review, and will appear as reviewed tracker
entries with their sources.</p>
<h2>Corrections</h2>
<p>Report an error or a missing record as an <a href="{REPO}/issues">issue</a>, with the source and the page or
timestamp that supports it.</p>
"""
    return page("About the records", body, 0, meta)


def render_data(d):
    meta = d["meta.json"]
    c = meta["counts"]
    body = f"""<h1>Data</h1>
<p>The records on this site, as JSON. The schemas and the generator are in the
<a href="{REPO}">source repository</a>.</p>
<ul>
<li>{link('agenda-intake/meetings.json', 'meetings.json')}: {c['meetings']} meeting records</li>
<li>{link('agenda-intake/items.json', 'items.json')}: {c['items']} agenda item records</li>
<li>{link('agenda-intake/meta.json', 'meta.json')}: the archive commit used, counts and exceptions</li>
</ul>
"""
    return page("Data", body, 1, meta)


COMMITMENT_STATUS = {
    "not_yet_due": "Not yet due",
    "no_due_date_stated": "No due date stated",
    "in_progress_reported": "In progress, as reported",
    "delayed": "Delayed",
    "reported_complete": "Reported complete",
    "completion_verified": "Completion verified",
    "cancelled_or_superseded": "Cancelled or superseded",
    "unknown_no_update_located": "No update located",
}


def source_link(src, loc):
    """A citation rendered beside its claim: archived copy first, then the City's copy."""
    target = src.get("archive_url") or src.get("official_url")
    label = f"{src['title']}, {loc}"
    extra = ""
    if src.get("archive_url") and src.get("official_url"):
        extra = f" ({link(src['official_url'], 'City copy')})"
    return f"{link(target, label)}{extra}"


def cites(citations, sources, with_quotes=True):
    out = []
    for c in citations:
        s = sources[c["source_id"]]
        q = f"<blockquote>{esc(c['quote'])}</blockquote>" if with_quotes and c.get("quote") else ""
        out.append(f"{q}<span class=\"muted\">Source: {source_link(s, c['locator'])}</span>")
    return "<br>".join(out)


def render_matters_index(t, meta):
    rows = []
    for m in t["matters.json"]:
        cs = [c for c in t["commitments.json"] if c["matter_id"] == m["id"]]
        rows.append(f"<tr><td>{link(m['id'] + '.html', m['title'])}</td><td>{esc(fmt_date(m['opened']))}</td>"
                    f"<td>{len(cs)}</td><td>{esc(fmt_date(m['last_reviewed']))}</td></tr>")
    body = ("<h1>Tracked matters</h1>"
            "<p>Public commitments and what the record shows afterward. Each entry is reviewed before it is "
            "published, and every statement links to its source.</p>"
            '<div class="table-wrap"><table><caption>Tracked matters</caption><thead><tr>'
            '<th scope="col">Matter</th><th scope="col">Opened</th><th scope="col">Commitments</th>'
            f'<th scope="col">Last reviewed</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return page("Tracked matters", body, 1, meta)


def render_matter(m, t, meta, meetings):
    sources = {s["id"]: s for s in t["sources.json"]}
    recs = {r["id"]: r for r in t["recommendations.json"]}
    cs = [c for c in t["commitments.json"] if c["matter_id"] == m["id"]]
    evs = sorted((e for e in t["events.json"] if e["matter_id"] == m["id"]), key=lambda e: (e["date"], e["id"]))
    finds = [f for f in t["findings.json"] if f["matter_id"] == m["id"]]
    body = [f"<h1>{esc(m['title'])}</h1>",
            f"<p>{esc(m['description'])}</p>",
            f"<p class=\"muted\">Last reviewed {esc(fmt_date(m['last_reviewed']))}. Statuses describe the "
            "evidence located as of the date shown. A missing update is a gap in the public record, not proof "
            "that no work occurred.</p>"]
    if m["agenda_items"]:
        links_ = []
        for a in m["agenda_items"]:
            mt = meetings.get(a["meeting_id"])
            when = fmt_date(mt["meeting_date"]) if mt else a["meeting_id"]
            links_.append(link(f"../meetings/{a['meeting_id']}.html", f"Council meeting, {when}, Item {a['item']}"))
        body.append("<p>On the agenda: " + " · ".join(links_) + "</p>")
    if m["qualifications"]:
        body.append(f'<div class="note"><strong>Qualification in the source.</strong> {cites(m["qualifications"], sources)}</div>')

    body.append("<h2>Commitments and status</h2>")
    rows = []
    for c in cs:
        cur = tracked_mod.current_status(c)
        rec = recs.get(c["recommendation_id"]) if c["recommendation_id"] else None
        what = f'<a href="#rec-{esc(rec["number"])}">{esc(c["label"])}</a>' if rec else esc(c["label"])
        due = esc(c["due"]["as_stated"]) if c["due"]["as_stated"] else '<span class="muted">not stated</span>'
        hist = []
        for h in c["status_history"]:
            src = cites(h["citations"], sources, with_quotes=False)
            searched = f"<br><span class=\"muted\">Searched: {esc(h['searched'])}</span>" if h.get("searched") else ""
            hist.append(f"<li><strong>{esc(COMMITMENT_STATUS[h['status']])}</strong> as of {esc(fmt_date(h['as_of']))}. "
                        f"{esc(h['basis'])}{searched}{'<br>' + src if src else ''}</li>")
        rows.append(f"<tr><td>{what}<br><span class=\"muted\">{esc(c['actor'])}</span></td><td>{due}</td>"
                    f"<td><strong>{esc(COMMITMENT_STATUS[cur['status']])}</strong><br>"
                    f"<span class=\"muted\">as of {esc(fmt_date(cur['as_of']))}</span></td>"
                    f"<td><blockquote>{esc(c['statement'])}</blockquote>"
                    f"<span class=\"muted\">Source: {source_link(sources[c['citation']['source_id']], c['citation']['locator'])}</span>"
                    f"<details><summary>Status history</summary><ul>{''.join(hist)}</ul></details></td></tr>")
    body.append('<div class="table-wrap"><table><caption>Commitments</caption><thead><tr>'
                '<th scope="col">Commitment and who is responsible</th><th scope="col">Date, as stated</th>'
                '<th scope="col">Current status</th><th scope="col">What the record says</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')

    if evs:
        body.append("<h2>Timeline</h2><ul>")
        for e in evs:
            body.append(f"<li><strong>{esc(fmt_date(e['date']))}</strong>: {esc(e['description'])}<br>{cites(e['citations'], sources)}</li>")
        body.append("</ul>")

    if finds:
        body.append("<h2>Findings and recommendations</h2>")
        for f in finds:
            body.append(f"<h3>Finding {esc(f['number'])}</h3><p>{esc(f['heading'])}<br>"
                        f"<span class=\"muted\">Source: {source_link(sources[f['citation']['source_id']], f['citation']['locator'])}</span></p>")
            for r in (x for x in t["recommendations.json"] if x["finding_id"] == f["id"]):
                mr = r["management_response"]
                body.append(f'<h4 id="rec-{esc(r["number"])}">Recommendation {esc(r["number"])}</h4>'
                            f"<blockquote>{esc(r['text'])}</blockquote><dl>"
                            f"<dt>Addressed to</dt><dd>{esc(', '.join(r['addressed_to']))}</dd>"
                            f"<dt>Management response</dt><dd>{esc(mr['position'])}</dd>"
                            f"<dt>Implementation date</dt><dd>{esc(mr['implementation_date'])}</dd>"
                            f"<dt>Corrective action plan</dt><dd>{esc(mr['corrective_action_plan'])}</dd></dl>"
                            f"<p class=\"muted\">Source: {source_link(sources[r['citation']['source_id']], r['citation']['locator'])}</p>")

    body.append("<h2>Sources</h2><ul>")
    used = sorted({c["source_id"] for rec in [m, *cs, *evs, *finds, *t["recommendations.json"]]
                   for c in tracked_mod.citations_of(rec)} & set(sources))
    for sid in used:
        s = sources[sid]
        bits = [link(s["archive_url"], "archived copy")] if s.get("archive_url") else []
        if s.get("official_url"):
            bits.append(link(s["official_url"], "City copy"))
        fp = f" sha256 <code>{esc(s['sha256'][:16])}…</code>." if s.get("sha256") else ""
        note = f" {esc(s['note'])}" if s.get("note") else ""
        date = fmt_date(s["document_date"]) if s.get("document_date") else "undated"
        body.append(f"<li>{esc(s['issuer'])}, <em>{esc(s['title'])}</em>, {esc(date)}. {' · '.join(bits)}."
                    f"<span class=\"muted\">{fp}{note}</span></li>")
    body.append("</ul><p class=\"muted\">Quoted official records keep their own terms and are not relicensed "
                "by this site's content notice.</p>")
    return page(m["title"], "\n".join(body), 1, meta)


def build(data_dir=OUT_DIR, out=SITE_DIR, tracked_dir=None):
    d = load_dataset(data_dir)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "meetings"))
    os.makedirs(os.path.join(out, "matters"))
    os.makedirs(os.path.join(out, "assets"))
    shutil.copytree(data_dir, os.path.join(out, "data", "agenda-intake"))
    files = {
        "index.html": render_index(d),
        "about.html": render_about(d),
        "meetings/index.html": render_meetings(d),
        "data/index.html": render_data(d),
        "assets/site.css": CSS,
        ".nojekyll": "",
    }
    by_meeting = {}
    for it in d["items.json"]:
        by_meeting.setdefault(it["meeting_id"], []).append(it)
    for m in d["meetings.json"]:
        files[f"meetings/{m['meeting_id']}.html"] = render_meeting(m, by_meeting.get(m["meeting_id"], []), d["meta.json"])
    t = tracked_mod.load(tracked_dir or tracked_mod.TRACKED_DIR)
    meetings = {m["meeting_id"]: m for m in d["meetings.json"]}
    files["matters/index.html"] = render_matters_index(t, d["meta.json"])
    for m in t["matters.json"]:
        files[f"matters/{m['id']}.html"] = render_matter(m, t, d["meta.json"], meetings)
    shutil.copytree(tracked_dir or tracked_mod.TRACKED_DIR, os.path.join(out, "data", "tracked"))
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    return sorted(files)
