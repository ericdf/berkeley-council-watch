"""Render the static site from the generated datasets and the reviewed records.

Every link is relative, so the site works under any GitHub Pages base path, including direct
navigation to a detail page. No client-side JavaScript; facts, citations and dates are in the HTML.
The home page's questions appear one at a time by CSS alone, and show as a plain list wherever
motion is reduced, CSS is off, or the reader asks to see them all.
"""
import datetime
import hashlib
import html
import os
import shutil

from . import member_site, ordinance_site, time_site
from . import tracked as tracked_mod
from .generate import OUT_DIR
from .validate import load_dataset

SITE_DIR = "_site"
TITLE = "Berkeley Council Watch"
TAGLINE = "What Berkeley's City Council spends its time on, and what it commits to do."
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
.lede{font-size:1.1rem}
ol.toc{columns:2;padding-left:20px;font-size:.95rem}
nav ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.95rem}
@media (max-width:600px){nav ul{gap:4px 12px;font-size:.88rem}header .tagline{font-size:.9rem;margin-bottom:6px}}
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


CSS_VERSION = "__css_version__"
# Set by build(): a sentence saying which meetings the record covers, shown on every page.
RECORD_THROUGH = ""


def page(title, body, depth, meta, extra=""):
    up = "../" * depth
    src = meta["source"]
    commit = src["archive_commit"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {TITLE}</title>
<link rel="stylesheet" href="{up}assets/site.css?v={CSS_VERSION}">
<script src="{up}assets/readout.js?v={CSS_VERSION}" defer></script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header>
<a class="name" href="{up}index.html">{TITLE}</a>
<p class="tagline">{TAGLINE}</p>
<nav aria-label="Site"><ul>
<li><a href="{up}index.html">Home</a></li>
<li><a href="{up}time/index.html">Council time</a></li>
<li><a href="{up}commitments/index.html">Commitments</a></li>
<li><a href="{up}members/index.html">Members</a></li>
<li><a href="{up}ordinances/index.html">Ordinances</a></li>
<li><a href="{up}matters/index.html">Tracked matters</a></li>
<li><a href="{up}meetings/index.html">Meetings</a></li>
<li><a href="{up}about.html">About the records</a></li>
<li><a href="{up}method.html">How this data is derived</a></li>
<li><a href="{up}data/index.html">Data</a></li>
</ul></nav>
</header>
<main id="main">
{body}
</main>
<footer>
<p>{RECORD_THROUGH}</p>
<p>Agenda records generated from the public-records archive at commit
<a href="{ARCHIVE}/tree/{esc(commit)}"><code>{esc(commit[:12])}</code></a>, using the City meeting listing
retrieved {esc(fmt_date(src['catalog_retrieved']))}.{extra}</p>
<p>For analysis of the issues behind tracked matters, read the <a href="{BDP}">Berkeley Decision Project</a>
and subscribe on <a href="{SUBSTACK}">Substack</a>.</p>
<p>Original written content by Berkeley Council Watch is licensed under <a href="{CC_BY}">CC BY 4.0</a>.
Please credit Berkeley Council Watch, link to this page and the license, and indicate changes.
Official records, source documents and quoted third-party material keep the terms they were published under
and are not relicensed by this notice.</p>
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


def record_through(timed, agendas):
    """The sentence naming the last meeting in the record. Meeting time comes from transcripts and
    votes and items from annotated agendas, which arrive separately, so each is named when they differ."""
    if not (timed or agendas):
        return ""
    if timed == agendas or not timed or not agendas:
        return (f"Record through the meeting of {fmt_date(timed or agendas)}. Later meetings are added as their "
                "annotated agendas and transcripts are processed.")
    return (f"Votes and items through the meeting of {fmt_date(agendas)}; meeting time through "
            f"{fmt_date(timed)}. Later meetings are added as their annotated agendas and transcripts are processed.")


def render_index(d, a, t, h):
    meetings, meta = d["meetings.json"], d["meta.json"]
    recent = [m for m in meetings if m["meeting_type"] in ("regular", "special")][:8]
    cm = a.meta["counts"]
    total = sum(a.total(x) for x in a.thread_ids())
    top = sorted(a.thread_ids(), key=lambda x: -a.total(x))[:5]
    cur = [tracked_mod.current_status(c)["status"] for c in t["commitments.json"]]
    n_open = sum(1 for x in cur if x in time_site.OPEN_STATUSES)
    body = f"""<h1>{TITLE}</h1>
<p class="lede">Berkeley's City Council decides how the City spends its money and its attention. Council Watch keeps a
plain record of both: what the Council spends its meeting time on, what it and City management commit to do, and what
each member brings, moves and votes. Everything comes from the City's records, linked at every step, so you can check it and
draw your conclusions.</p>
<p class="muted">{RECORD_THROUGH}</p>
{h["questions"]}
<h2>What is the Council spending its time on?</h2>
<p>{link("time/index.html", "Council time")} measures meeting time on every non-routine item in {cm['transcripts']} meeting
transcripts, from December 2024 on: staff and Council time, spoken public comment, and the letters the public sent, side
by side by subject, {hours_text(total)} in all. It also counts the items members wrote on each subject, including the
many adopted on consent without discussion: those take no meeting time, but someone wrote each one and staff reviewed it.
The subjects with the most meeting time:</p>
<ul>{"".join(f'<li>{link(time_site.thread_href(x), a.thread_info[x]["label"])}: {hours_text(a.total(x))}</li>' for x in top)}</ul>
<h2>What has it committed to do?</h2>
<p>{link("commitments/index.html", "Commitments")} lists {len(t['commitments.json'])} specific, checkable undertakings from
{len(t['matters.json'])} {link("matters/index.html", "tracked matters")}, {n_open} of them still open: what was promised, by whom,
by when, and what the record shows since.</p>
<h2>What has each member brought, moved and voted?</h2>
<p>Each {link("members/index.html", "member page")} lists the items the member brought to the Council, by role (lead author,
joint author, co-sponsor, or added later as a co-sponsor), their vote on every item's final motion, the motions they made,
and their roll-call attendance, each beside the range across the Council. The {link("members/index.html#divided", "divided votes")}
show every motion on which the Council split, member by member.</p>
<h2>Who brings the laws it adopts?</h2>
<p>{link("ordinances/index.html", "Ordinances")} lists every ordinance the annotated agendas number: who brought it, and
whether each reading was taken on the consent calendar or the action calendar.</p>
<h2>What happened at a meeting?</h2>
<p>Each {link("meetings/index.html", "meeting page")} links the City's agenda and the archived records, and shows how the
meeting's time was spent.</p>
"""
    body += meetings_table(recent, 0, "Most recent regular and special meetings")
    return page("Home", body, 0, meta)


def hours_text(m):
    return f"{m / 60:,.0f} hours"


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


def render_meeting(m, items, meta, a=None, h=None):
    title = f"{TYPE_LABELS.get(m['meeting_type'], m['meeting_type'])} meeting, {fmt_date(m['meeting_date'])}"
    body = [f"<h1>{esc(title)}</h1>",
            f"<p class=\"muted\">{esc(m['name'])} · last checked {esc(fmt_date(m['last_checked_at']))}</p>",
            time_site.meeting_block(a, m, h) if a is not None else "",
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
    return page(title, "\n".join(body), 1, meta, extra=(h or {}).get("time_footer", "") if a is not None and a.by_meeting.get(m["meeting_id"]) else "")


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
<h2 id="council-time">Council time, votes and authorship</h2>
<p>How the minutes, letters, topics, votes and authorship on this site are derived, and what they do not
measure, is set out in {link("method.html", "How this data is derived")}.</p>
<h2>Corrections</h2>
<p>Report an error or a missing record as an <a href="{REPO}/issues">issue</a>, with the source and the page or
timestamp that supports it.</p>
"""
    return page("About the records", body, 0, meta)


def render_method(d, a, h):
    cal = a.meta["calibration"]
    c = a.meta["counts"]
    toc = [("glance", "At a glance"), ("meeting-time", "Meeting time, and what it leaves out"),
           ("minutes", "Where the minutes come from"), ("boundaries", "Where an item begins and ends"),
           ("topics", "Topics"), ("letters", "Letters"), ("consent", "The consent calendar"),
           ("authorship", "Who brought an item"), ("votes", "Votes, motions and attendance"),
           ("corrections", "Data and corrections")]
    body = f"""<h1>How this data is derived</h1>
<p class="lede">Every figure on Council Watch is computed from the City's records, as kept in the
<a href="{ARCHIVE}">Berkeley public-records archive</a>. This page explains how, and where each figure stops.</p>
<nav aria-label="On this page"><ol class="toc">{"".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in toc)}</ol></nav>

<h2 id="glance">At a glance</h2>
<div class="table-wrap"><table><caption>Each measure and its source</caption>
<thead><tr><th scope="col">Measure</th><th scope="col">Source</th><th scope="col">Keep in mind</th></tr></thead><tbody>
<tr><td>Minutes of staff and Council time</td><td>Caption transcripts</td><td>Meeting time only; {c['transcripts_estimated']} of {c['transcripts']} transcripts give estimates</td></tr>
<tr><td>Minutes of spoken public comment</td><td>Caption transcripts</td><td>The public-comment span of each item</td></tr>
<tr><td>Letters</td><td>Annotated agendas</td><td>The Clerk's count; officials' submissions left out</td></tr>
<tr><td>Items members wrote, by role</td><td>Annotated agendas (the From line)</td><td>Roles as printed; routine items compared apart</td></tr>
<tr><td>Votes, motions, attendance</td><td>Annotated agendas</td><td>As the Clerk recorded them</td></tr>
<tr><td>Consent calendar items and amounts</td><td>Annotated agendas</td><td>Amounts as printed: authorized, with spending not shown</td></tr>
<tr><td>Topic of an item</td><td>This site</td><td>This site's grouping, reviewed and published</td></tr>
</tbody></table></div>

<h2 id="meeting-time">Meeting time, and what it leaves out</h2>
<p>Minutes measure time in Council meetings. They do not measure the rest of the Council's and staff's time. An item
a member writes takes work before any meeting: drafting, agenda review, staff and legal review. That is true whether the
Council discusses it or adopts it on the consent calendar in a single vote. No record measures that work in minutes, so
the topic pages also count the items members wrote on each subject, heard or not.</p>
<p>Routine meeting business is not counted in minutes: ceremonies, the consent calendar as a block, Council and City
Manager comments, general public comment, and adjournment.</p>

<h2 id="minutes">Where the minutes come from</h2>
<ul>
<li><strong>Timestamped transcripts</strong> (Zoom captions, most of 2026 and late 2025) give caption time: when an item
begins and ends.</li>
<li><strong>Court-reporter transcripts</strong> (most of 2025) have no timestamps. An item's minutes are its share of the
transcript's words times the meeting's length: adjournment, less call to order, less recesses. These are estimates, drawn
hatched.</li>
<li><strong>How good the estimate is.</strong> Tested on the timestamped transcripts, across {cal['segments']} items of
{cal['min_minutes']} minutes or more, the estimate's median ratio to true time is {cal['median_ratio']}; the middle half
fall between {cal['middle_half'][0]} and {cal['middle_half'][1]}, and the extremes are {cal['range'][0]} and
{cal['range'][1]}.</li>
</ul>

<h2 id="boundaries">Where an item begins and ends</h2>
<p>Each transcript was divided into agenda items and procedural blocks by reading it. The boundaries have not yet
been checked against the meeting video, so they are marked as inferred. Each records the words where it begins and
its place in the transcript, so anyone can check it; the structure is published in the archive.</p>

<p>On a topic's chart, each bar links to its meeting's row in the table below it; on the Council time page, to that row
on the topic's page. A bar adds up every item on the topic at that meeting, so it goes to the meeting's row.</p>

<h2 id="topics">Topics</h2>
<ul>
<li><strong>A topic groups items by subject</strong> so their time can be read side by side. Topics are this site's grouping
and say nothing about an item's merit.</li>
<li><strong>City finances</strong> is shown as five separate topics on one scale, so no part is hidden inside a total.</li>
<li><strong>Audits</strong> go to their subject. Items presented by or about the City Auditor are also listed together.</li>
<li><strong>State, federal and international positions</strong>, such as resolutions and letters on bills, are a
separate topic.</li>
<li><strong>Gaza</strong> had one agenda item. Speaker turns about it during general and consent public comment are also
counted, when the turn was about it; turns that only touched on it are not.</li>
<li><strong>The classification is published</strong> in the source repository and changes only by reviewed pull request.</li>
</ul>

<h2 id="letters">Letters</h2>
<p>The count the Clerk gives in each annotated agenda: one per listed entry, the number printed after a name, or the
number of "similarly worded form letters". Submissions from Councilmembers, the Mayor, staff and commissions are left
out. Letters filed under an item take that item's topic; letters under a subject heading take the heading's.</p>

<h2 id="consent">The consent calendar</h2>
<ul>
<li>Items adopted on the consent calendar pass in one vote with the rest of the calendar, with no separate discussion.</li>
<li>A <strong>filled</strong> tick marks a meeting where at least one such item on the topic shows, in the annotated agenda,
more than a routine item: an ordinance, member authorship, a move from the action calendar, revision at adoption,
speakers, or letters. A <strong>taller</strong> tick means a larger amount, on a log scale from $1,000 to $1 billion. A number beside a tick
counts the consent items on that topic at that meeting, when there is more than one.</li>
<li>An amount is as printed: the largest figure under Financial Implications, otherwise the first in the
Recommendation. It is the amount authorized; spending is not shown.</li>
<li>An amendment to the annual budget counts once, at its first reading, on its net appropriation. Amendments are not
cumulative. The full budget is adopted on the action calendar.</li>
</ul>

<h2 id="authorship">Who brought an item</h2>
<p>The annotated agenda names an item's sponsors and, usually, their role. Six roles are kept apart and never added
together: lead author (the only author, or the one the agenda's Contact line names), joint author (any other
author or co-author), co-sponsor on the
agenda as posted, co-sponsor added at the meeting (the transcript shows it), co-sponsor added later where the record
does not say when, and named with no role. Comparisons between members count items on City business, leaving out
routine items (relinquishments, donations, commemorations, appointments, excused absences) and counting state,
federal and international positions separately.</p>

<h2 id="votes">Votes, motions and attendance</h2>
<ul>
<li>The vote counted for an item is the vote on its final motion, as printed.</li>
<li>Where the Clerk printed "All Ayes" without names, that vote is shown as "All Ayes", because the record does
not show who was present at that moment.</li>
<li>A failed motion followed by the one that decided the item is shown as competing, unless the transcript confirms it
was a substitute.</li>
<li>Attendance is absence at roll call and later arrival, as recorded. It says nothing about reasons, and early
departures are not recorded.</li>
</ul>

<h2 id="corrections">Data and corrections</h2>
<p>All the data behind these pages is on the {link("data/index.html", "Data")} page, and the code and the full method are in
the <a href="{REPO}">source repository</a> (<a href="{REPO}/blob/main/docs/COUNCIL_TIME.md">council time</a>,
<a href="{REPO}/blob/main/docs/MEMBERS.md">members</a>). To report an error, open an <a href="{REPO}/issues">issue</a> with the source
and the page or timestamp that supports it.</p>
"""
    return page("How this data is derived", body, 0, d["meta.json"], extra=h["time_footer"])


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
<h2>Council time</h2>
<ul>
<li>{link('council-time/segments.json', 'segments.json')}: minutes for every part of every transcribed meeting</li>
<li>{link('council-time/correspondence.json', 'correspondence.json')}: letters by Clerk heading</li>
<li>{link('council-time/items.json', 'items.json')}: agenda items from the annotated agendas, with final votes</li>
<li>{link('council-time/turns.json', 'turns.json')}: public-comment turns on a topic outside its agenda item</li>
<li>{link('council-time/consent.json', 'consent.json')}: items adopted on the consent calendar, with amounts as printed</li>
<li>{link('council-time/meta.json', 'meta.json')}: the archive commit used, counts and exceptions</li>
<li>The reviewed classification: <a href="{REPO}/tree/main/data/review/council-time">data/review/council-time</a></li>
</ul>
"""
    return page("Data", body, 1, meta)


COMMITMENT_STATUS = {
    "not_yet_due": "Not yet due",
    "no_due_date_stated": "No due date stated",
    "in_progress_reported": "In progress, as reported",
    "delayed": "Delayed",
    "reported_complete": "Reported complete",
    "reported_not_met": "Reported not met",
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
        summary = time_site.status_counts(cs, COMMITMENT_STATUS) or '<span class="muted">none</span>'
        rows.append(f"<tr><td>{link(m['id'] + '.html', m['title'])}</td><td>{esc(fmt_date(m['opened']))}</td>"
                    f"<td class=\"num\">{len(cs)}</td><td>{summary}</td><td>{esc(fmt_date(m['last_reviewed']))}</td></tr>")
    body = ("<h1>Tracked matters</h1>"
            "<p>Public commitments and what the record shows afterward. Each entry is reviewed before it is "
            "published, and every statement links to its source.</p>"
            '<p class="muted">Where things stand counts each matter\'s commitments by the status the evidence supports '
            'as of the last review. "Reported" means the responsible party says so; "verified" needs independent '
            'evidence; "no update located" marks a gap in the public record, and work may still have occurred. See '
            '<a href="../commitments/index.html#by-status">commitments by status</a>.</p>'
            '<div class="table-wrap"><table><caption>Tracked matters</caption><thead><tr>'
            '<th scope="col">Matter</th><th scope="col">Opened</th><th scope="col">Commitments</th>'
            '<th scope="col">Where things stand</th>'
            f'<th scope="col">Last reviewed</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return page("Tracked matters", body, 1, meta)


def render_matter(m, t, meta, meetings, att=None, h=None):
    sources = {s["id"]: s for s in t["sources.json"]}
    recs = {r["id"]: r for r in t["recommendations.json"]}
    cs = [c for c in t["commitments.json"] if c["matter_id"] == m["id"]]
    evs = sorted((e for e in t["events.json"] if e["matter_id"] == m["id"]), key=lambda e: (e["date"], e["id"]))
    finds = [f for f in t["findings.json"] if f["matter_id"] == m["id"]]
    body = [f"<h1>{esc(m['title'])}</h1>",
            f"<p>{esc(m['description'])}</p>",
            f"<p class=\"muted\">Last reviewed {esc(fmt_date(m['last_reviewed']))}. Statuses describe the "
            "evidence located as of the date shown. A missing update marks a gap in the public record, and work may "
            "still have occurred.</p>"]
    if m["agenda_items"]:
        links_ = []
        for a in m["agenda_items"]:
            mt = meetings.get(a["meeting_id"])
            when = fmt_date(mt["meeting_date"]) if mt else a["meeting_id"]
            links_.append(link(f"../meetings/{a['meeting_id']}.html", f"Council meeting, {when}, Item {a['item']}"))
        body.append("<p>On the agenda: " + " · ".join(links_) + "</p>")
    if m["qualifications"]:
        # A qualification may carry an "unresolved" note (project words): what the record cannot yet
        # establish and which record would resolve it.
        quals = "<br>".join(cites([q], sources) + (f"<br><strong>Unresolved.</strong> {esc(q['unresolved'])}"
                                                   if q.get("unresolved") else "")
                            for q in m["qualifications"])
        body.append(f'<div class="note"><strong>Qualification in the source.</strong> {quals}</div>')

    if att is not None:
        body.append(time_site.matter_block(att, m, h))
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
                    + (f"<p class=\"muted\">Measure of success, as stated:</p><blockquote>{esc(c['success_measure'])}</blockquote>"
                       if c.get("success_measure") else "") +
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
                mr = {k: esc(v) if v is not None else '<span class="muted">not in the sources cited</span>'
                      for k, v in r["management_response"].items()}
                body.append(f'<h4 id="rec-{esc(r["number"])}">Recommendation {esc(r["number"])}</h4>'
                            f"<blockquote>{esc(r['text'])}</blockquote><dl>"
                            f"<dt>Addressed to</dt><dd>{esc(', '.join(r['addressed_to']))}</dd>"
                            f"<dt>Management response</dt><dd>{mr['position']}</dd>"
                            f"<dt>Implementation date</dt><dd>{mr['implementation_date']}</dd>"
                            f"<dt>Corrective action plan</dt><dd>{mr['corrective_action_plan']}</dd></dl>"
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
    body.append("</ul><p class=\"muted\">Quoted official records keep the terms they were published under and are not relicensed "
                "by this site's content notice.</p>")
    return page(m["title"], "\n".join(body), 1, meta)


def build(data_dir=OUT_DIR, out=SITE_DIR, tracked_dir=None, time_dir=None, review_dir=None):
    d = load_dataset(data_dir)
    time_dir = time_dir or time_site.ct.OUT_DIR
    td = time_site.load(time_dir, review_dir or time_site.ct.REVIEW_DIR)
    a = time_site.Attention(td)
    mem = member_site.Members(a, td)
    item_roles = mem.item_roles()
    timed = sorted((x["meeting_date"], x["meeting_id"]) for x in td["segments.json"] if x["meeting_id"])
    latest_meeting = f"meetings/{timed[-1][1]}.html#council-time" if timed else None
    global RECORD_THROUGH
    RECORD_THROUGH = record_through(timed[-1][0] if timed else None,
                                    max((x["meeting_date"] for x in td["items.json"]), default=None))
    contacts = {it["record_id"]: it.get("contact") for it in td["items.json"]}
    items_by_meeting = {}
    for it in td["items.json"]:
        items_by_meeting.setdefault(it["meeting_id"], []).append(it)
    t = tracked_mod.load(tracked_dir or tracked_mod.TRACKED_DIR)
    commit = a.meta["source"]["archive_commit"]
    h = {"esc": esc, "link": link, "page": page, "fmt_date": fmt_date, "meta": d["meta.json"], "repo": REPO,
         "status_labels": COMMITMENT_STATUS, "meeting_ids": {m["meeting_id"] for m in d["meetings.json"]},
         "mlink": time_site.mlink, "latest_meeting": latest_meeting, "item_roles": item_roles, "items_by_meeting": items_by_meeting,
         "item_thread": mem.item_thread,
         "roles_html": lambda rid: member_site.roles_html(item_roles.get(rid, []), mem.name, link,
                                                          contact=contacts.get(rid)), "bdp": BDP.rsplit("/", 1)[0] + "/",
         "time_footer": f' Council time computed from the archive at commit <a href="{ARCHIVE}/tree/{esc(commit)}">'
                        f'<code>{esc(commit[:12])}</code></a>.'}
    if os.path.isdir(out):
        shutil.rmtree(out)
    for sub in ("meetings", "matters", "assets", "time", "commitments", "members", "ordinances"):
        os.makedirs(os.path.join(out, sub))
    shutil.copytree(data_dir, os.path.join(out, "data", "agenda-intake"))
    shutil.copytree(time_dir, os.path.join(out, "data", "council-time"))
    files = {
        "about.html": render_about(d),
        "method.html": render_method(d, a, h),
        "meetings/index.html": render_meetings(d),
        "data/index.html": render_data(d),
        "time/index.html": time_site.render_time_index(a, h),
        "commitments/index.html": time_site.render_commitments(a, t, h),
        "members/index.html": member_site.index_page(mem, h),
        "ordinances/index.html": page("Ordinances", ordinance_site.page(td["items.json"], {
            **h, "record_through": RECORD_THROUGH, "member_name": mem.name, "member_slug": member_site.slug,
            "item_thread_label": lambda it: (lambda th: link(f"../time/{th}.html", a.thread_info[th]["label"])
                                             if th in a.thread_info and th not in ("other", "routine") else "")(mem.thread_of(it)),
        }, item_roles), 1, d["meta.json"]),
        ".nojekyll": "",
    }
    for th in a.thread_ids():
        files[f"time/{th}.html"] = time_site.render_thread(a, th, h)
    for x in mem.ids():
        files[f"members/{member_site.slug(x)}.html"] = member_site.member_page(mem, x, h)
    by_meeting = {}
    for it in d["items.json"]:
        by_meeting.setdefault(it["meeting_id"], []).append(it)
    for m in d["meetings.json"]:
        files[f"meetings/{m['meeting_id']}.html"] = render_meeting(m, by_meeting.get(m["meeting_id"], []), d["meta.json"], a, h)
    meetings = {m["meeting_id"]: m for m in d["meetings.json"]}
    files["matters/index.html"] = render_matters_index(t, d["meta.json"])
    for m in t["matters.json"]:
        files[f"matters/{m['id']}.html"] = render_matter(m, t, d["meta.json"], meetings, a, h)
    shutil.copytree(tracked_dir or tracked_mod.TRACKED_DIR, os.path.join(out, "data", "tracked"))

    def available(href):
        path, _, anchor = href.partition("#")
        return path in files and (not anchor or f'id="{anchor}"' in files[path])
    h["questions"] = time_site.questions_block(h, available)
    files["index.html"] = render_index(d, a, t, h)
    nq = len(time_site.questions(h, available))
    files["assets/site.css"] = CSS + member_site.CSS + time_site.css(-(-nq // time_site.GROUP))
    files["assets/readout.js"] = time_site.READOUT_JS
    # Version the stylesheet and script URLs by their content, so a browser holding the
    # previous versions never pairs them with new markup after a deploy.
    version = hashlib.sha256((files["assets/site.css"] + files["assets/readout.js"]).encode()).hexdigest()[:10]
    for name in files:
        if name.endswith(".html"):
            files[name] = files[name].replace(CSS_VERSION, version)
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    return sorted(files)
