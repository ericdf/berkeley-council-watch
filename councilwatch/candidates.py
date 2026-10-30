"""Backfill Pass 2: find accountability candidates in archived annotated agendas.

docs/AUTOMATION_SPEC.md §7. Deterministic only: versioned phrase rules (candidate_rules.json), stable
item ids, shared title terms and date windows. Every candidate is unconfirmed until a person reviews it;
this module writes review bundles, never tracked records or agenda-intake data.
"""
import calendar
import datetime
import math
import json
import os
import re
import subprocess
from collections import Counter

from .archive import Archive

RULES_PATH = os.path.join(os.path.dirname(__file__), "candidate_rules.json")
MONTHS = {m: i for i, m in enumerate(calendar.month_name) if m}
SEASON_END = {"Winter": (3, 20), "Spring": (6, 20), "Summer": (9, 22), "Fall": (12, 21)}

ITEM_RE = re.compile(r"^\s{0,4}(\d{1,3}[a-z]?)\.\s+(\S.*?)\s*$")
FIELD_RE = re.compile(r"^\s+(From|Recommendation|Financial Implications|Contact|Action|Vote|"
                      r"Policy Committee Recommendation):\s*(.*?)\s*$")
PAGE_HEADER_RE = re.compile(r"ANNOTATED AGENDA\s+Page \d+|^\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
                            r"\w+ \d{1,2}, \d{4}\s*$")
# Items are read only inside agenda calendars. Any other heading (Ceremonial Matters, City Manager
# Comments, Public Comment, Roll Call ...) starts a section whose numbered lines are not agenda items.
ITEM_SECTIONS = ("Consent Calendar", "Action Calendar", "Information Reports", "Information Calendar",
                 "Council Action Items", "Council Consent Items", "Worksession", "Work Session")
OTHER_HEADING_RE = re.compile(r"^\s{0,2}[A-Z][A-Za-z ,&/'’–-]{2,60}:(\s.*)?$")
STOP_SECTIONS = ("Communications", "Adjournment")
TITLE_NOTE_RE = re.compile(r"\((?:Reviewed by|Continued from|Item contains|Referred from)[^)]*\)", re.I)


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    # A compound word broken across lines ("off-" / "street") keeps its hyphen and loses the line break.
    s = re.sub(r"(?<=\w)-[ \t]*\n\s*(?=\w)", "-", s)
    return re.sub(r"\s+", " ", s).strip()


# ---- text -------------------------------------------------------------------------------------

def pdftotext_version():
    r = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    return (r.stderr or r.stdout).splitlines()[0].strip()


def l1_index(archive):
    """Annotated agenda id -> its archived L1 text entry."""
    out = {}
    for name in os.listdir(archive.path("manifest")):
        if name.endswith("-annotated-agenda-text.json") or "-annotated-agenda-v" in name and name.endswith("-text.json"):
            e = archive.entry(name[:-5])
            src = e.get("derived_from") or {}
            if isinstance(src, dict) and src.get("id") and e.get("file"):
                out[src["id"]] = e
    return out


def agenda_text(archive, aa_id, l1):
    """The pages of an annotated agenda, and the basis: the archive's L1 text when it has one, otherwise
    the archive's extraction command (pdftotext -layout) run on the archived PDF."""
    if aa_id in l1 and os.path.isfile(archive.path(l1[aa_id]["file"])):
        e = l1[aa_id]
        with open(archive.path(e["file"]), encoding="utf-8") as f:
            text = f.read()
        basis = {"kind": "archive_l1", "archive_id": e["id"], "sha256": e["sha256"]}
    else:
        e = archive.entry(aa_id)
        if not e.get("file") or not os.path.isfile(archive.path(e["file"])):
            return None, {"kind": "missing", "archive_id": aa_id}
        r = subprocess.run(["pdftotext", "-layout", archive.path(e["file"]), "-"], capture_output=True, text=True)
        if r.returncode != 0:
            return None, {"kind": "extraction_failed", "archive_id": aa_id}
        text = r.stdout
        basis = {"kind": "pdftotext_at_run_time", "archive_id": aa_id, "sha256": e["sha256"],
                 "command": "pdftotext -layout <L0> -", "tool": pdftotext_version()}
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages, basis


# ---- parsing ----------------------------------------------------------------------------------

def parse_items(pages):
    """Items of an annotated agenda: number, title, section, fields, and the pages they span."""
    items, cur, field, section = [], None, None, None
    stopped = False
    for pno, page in enumerate(pages, start=1):
        for line in page.splitlines():
            if stopped or not line.strip() or PAGE_HEADER_RE.search(line):
                continue
            head = line.strip()
            if not line.startswith("   ") and head.startswith(STOP_SECTIONS):
                stopped = True
                cur = None
                continue
            if not line.startswith("    ") and head.startswith(ITEM_SECTIONS) and not ITEM_RE.match(line):
                section, cur, field = head, None, None
                continue
            if OTHER_HEADING_RE.match(line) and not FIELD_RE.match(line) and not ITEM_RE.match(line):
                section, cur, field = None, None, None
                continue
            m = ITEM_RE.match(line)
            if m and not FIELD_RE.match(line) and section:
                cur = {"number": m.group(1), "title": m.group(2), "section": section, "fields": {},
                       "pages": [pno, pno], "_title_open": True}
                items.append(cur)
                field = None
                continue
            if cur is None:
                continue
            cur["pages"][1] = pno
            f = FIELD_RE.match(line)
            if f:
                field = f.group(1).lower()
                cur["fields"][field] = f.group(2)
                cur["_title_open"] = False
            elif cur["_title_open"]:
                cur["title"] += "\n" + head
            elif field:
                cur["fields"][field] += "\n" + head
    for it in items:
        it.pop("_title_open", None)
        it["title"] = norm(it["title"])
        it["fields"] = {k: norm(v) for k, v in it["fields"].items()}
    return items


# ---- matching ---------------------------------------------------------------------------------

def sentence_with(text, start, end):
    """The sentence of `text` containing [start, end), as printed."""
    bounds = [0] + [m.end() for m in re.finditer(r"(?<=[.;])\s+(?=[A-Z0-9(])", text)] + [len(text)]
    for a, b in zip(bounds, bounds[1:]):
        if a <= start < b:
            return text[a:b].strip()
    return text.strip()


def deadline_end(month_or_season, year):
    y = int(year)
    if month_or_season in SEASON_END:
        mth, day = SEASON_END[month_or_season]
        return datetime.date(y + (1 if month_or_season == "Winter" else 0), mth, day)
    mth = MONTHS[month_or_season]
    return datetime.date(y, mth, calendar.monthrange(y, mth)[1])


def find_matches(item, rules):
    matches, deadlines = [], []
    for fld in rules["direction_fields"]:
        text = item["fields"].get(fld)
        if not text:
            continue
        for r in rules["direction_rules"]:
            for m in re.finditer(r["pattern"], text, re.I):
                matches.append({"rule": r["id"], "field": fld, "matched": m.group(0),
                                "quote": sentence_with(text, m.start(), m.end())})
        for m in re.finditer(rules["deadline_pattern"], text, re.I):
            word = m.group(1).capitalize()
            deadlines.append({"field": fld, "text": m.group(0), "ends": deadline_end(word, m.group(2)).isoformat(),
                              "quote": sentence_with(text, m.start(), m.end())})
    seen, unique = set(), []
    for x in matches:
        k = (x["rule"], x["field"], x["quote"])
        if k not in seen:
            seen.add(k)
            unique.append(x)
    return unique, deadlines


def is_follow_up_title(title, rules):
    """A title that reports back (status report, update ...), and is not itself a referral, contract,
    ordinance or resolution that merely mentions an update."""
    return bool(re.search(rules["follow_up_title_pattern"], title, re.I)
                and not re.match(rules["follow_up_exclude_pattern"], title, re.I))


def terms(title, generic):
    out = set()
    for w in re.findall(r"[a-z]+", TITLE_NOTE_RE.sub(" ", title).lower()):
        if len(w) < 4 or w in generic:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


# ---- run --------------------------------------------------------------------------------------

def meetings_in_range(archive, start, end):
    joined = archive.meeting_map()["meetings"]
    out, missing = [], []
    for m in sorted(joined, key=lambda x: (x["date"], x["meeting"])):
        if not (start <= m["date"] <= end):
            continue
        ids = m["archived"].get("annotated_agenda") or []
        listed = m["listed"].get("annotated_agenda")
        pick = listed if listed in ids else (ids[0] if len(ids) == 1 else None)
        if pick:
            out.append((m, pick))
        elif ids:
            missing.append({"meeting_id": m["meeting"], "kind": "annotated_agenda_ambiguous", "archive_ids": ids})
        elif m["city"].get("annotated_agenda"):
            missing.append({"meeting_id": m["meeting"], "kind": "annotated_agenda_not_archived", "archive_ids": [],
                            "city_url": m["city"]["annotated_agenda"]})
    return out, missing


def run(archive_root, start, end, rules=None, allow_dirty=False):
    rules = rules or load_rules()
    archive = Archive(archive_root, allow_dirty=allow_dirty)
    l1 = l1_index(archive)
    # The whole archived corpus is parsed, so word rarity and follow-up search do not depend on the
    # requested range; only candidates are limited to it.
    meetings, exceptions = meetings_in_range(archive, "0000-00-00", "9999-99-99")
    exceptions = [e for e in exceptions if start <= e["meeting_id"][len("city-council-"):][:10] <= end]
    generic = set(rules["link"]["generic_terms"])
    all_items, candidates, bases = [], [], Counter()
    scanned = 0
    for m, aa_id in meetings:
        in_range = start <= m["date"] <= end
        scanned += in_range
        pages, basis = agenda_text(archive, aa_id, l1)
        if in_range:
            bases[basis["kind"]] += 1
        if pages is None:
            if in_range:
                exceptions.append({"meeting_id": m["meeting"], "kind": basis["kind"], "archive_ids": [aa_id]})
            continue
        items = parse_items(pages)
        if not items:
            if in_range:
                exceptions.append({"meeting_id": m["meeting"], "kind": "no_items_parsed", "archive_ids": [aa_id]})
            continue
        for it in items:
            rec = {"meeting_id": m["meeting"], "meeting_date": m["date"], "meeting_type": m["label"],
                   "item": it["number"], "title": it["title"], "section": it["section"],
                   "source": {"annotated_agenda": aa_id, "text_basis": basis, "pages": it["pages"]},
                   "action": it["fields"].get("action"), "vote": it["fields"].get("vote"),
                   "_text": " ".join(it["fields"].values()), "_terms": terms(it["title"], generic)}
            all_items.append(rec)
            if not in_range:
                continue
            matches, deadlines = find_matches(it, rules)
            follow_up = is_follow_up_title(it["title"], rules)
            if not matches and not follow_up:
                continue
            action_deadlines = [d for d in deadlines if d["field"] == "action"]
            effective = (action_deadlines or deadlines or [None])[0]
            cand = {k: v for k, v in rec.items() if not k.startswith("_")}
            cand.update({
                "candidate_id": f"{m['meeting']}--item-{it['number']}",
                "kind": "direction" if matches else "follow_up_report",
                "matches": matches,
                "deadlines": deadlines,
                "effective_deadline": effective,
                "action_recorded": bool(it["fields"].get("action")),
                "links": [],
                "review_status": "unconfirmed",
                "gaps": [] if it["fields"].get("action") else ["no recorded action found for this item"],
            })
            cand["_terms"], cand["_date"] = rec["_terms"], m["date"]
            candidates.append(cand)
    link(candidates, all_items, rules)
    for c in candidates:
        c.pop("_terms", None)
        c.pop("_date", None)
    candidates.sort(key=lambda c: (c["meeting_date"], c["meeting_id"], _num(c["item"])))
    report = {
        "pass": 2, "rules_version": rules["version"], "start": start, "end": end,
        "archive_commit": archive.commit,
        "meetings_scanned": scanned,
        "corpus_items": len(all_items),
        "text_basis": dict(sorted(bases.items())),
        "items_parsed": sum(1 for i in all_items if start <= i["meeting_date"] <= end),
        "candidates": dict(sorted(Counter(c["kind"] for c in candidates).items())),
        "matches_by_rule": dict(sorted(Counter(x["rule"] for c in candidates for x in c["matches"]).items())),
        "linked_directions": sum(1 for c in candidates if c["links"]),
        "exceptions": exceptions,
    }
    return candidates, report


def link(candidates, items, rules):
    """Propose later follow-up items for each direction: a follow-up title, at least N shared title
    terms, inside the window set by the effective deadline. Evidence is recorded; nothing is confirmed."""
    cfg = rules["link"]
    later = [i for i in items if is_follow_up_title(i["title"], rules)]
    # Shared words are weighted by rarity across the run's titles, log(titles / titles with the word), and
    # a link needs a total above min_link_score. "restaurant" + "inspection" clears it; "ordinance" +
    # "code" does not. Words in more than max_term_share of titles never count.
    df = Counter(t for i in items for t in i["_terms"])
    n = max(len(items), 1)
    weight = {t: math.log(n / k) for t, k in df.items() if k <= cfg["max_term_share"] * n}
    for c in candidates:
        if c["kind"] != "direction":
            continue
        start = datetime.date.fromisoformat(c["_date"])
        if c["effective_deadline"]:
            end = datetime.date.fromisoformat(c["effective_deadline"]["ends"]) + datetime.timedelta(days=cfg["grace_days_after_deadline"])
            window = f"through {end.isoformat()}: deadline {c['effective_deadline']['text']!r} plus {cfg['grace_days_after_deadline']} days"
        else:
            end = start + datetime.timedelta(days=cfg["window_days_without_deadline"])
            window = f"through {end.isoformat()}: no deadline captured; {cfg['window_days_without_deadline']} days"
        for i in later:
            d = datetime.date.fromisoformat(i["meeting_date"])
            if not (start < d <= end):
                continue
            shared = sorted(t for t in c["_terms"] & i["_terms"] if t in weight)
            score = sum(weight[t] for t in shared)
            if len(shared) < cfg["min_shared_terms"] or score < cfg["min_link_score"]:
                continue
            evidence = [f"shared title terms, score {score:.1f}: "
                        + ", ".join(f"{t} (in {df[t]} of {n} titles)" for t in shared),
                        f"follow-up title: {i['title']!r}",
                        f"date window {window}"]
            long_date = f"{calendar.month_name[start.month]} {start.day}, {start.year}"
            if long_date in i["_text"] or long_date in i["title"]:
                evidence.append(f"cites the direction's date, {long_date}")
            if any(x["meeting_id"] == i["meeting_id"] and x["item"] == i["item"] for x in c["links"]):
                continue
            c["links"].append({"meeting_id": i["meeting_id"], "meeting_date": i["meeting_date"], "item": i["item"],
                               "title": i["title"], "action": i["action"], "evidence": evidence,
                               "status": "unconfirmed"})


def _num(n):
    d = "".join(ch for ch in n if ch.isdigit())
    return (int(d) if d else 10**6, n)


# ---- verification -----------------------------------------------------------------------------

def verify(candidate, pages):
    """Every quote in a candidate must appear, whitespace-normalized, on the pages it cites. This is the
    check that would reject an invented quote from any finder, deterministic or not."""
    a, b = candidate["source"]["pages"]
    kept = [ln for p in pages[a - 1:b] for ln in p.splitlines() if not PAGE_HEADER_RE.search(ln)]
    text = norm("\n".join(kept))
    problems = []
    for x in candidate.get("matches", []) + candidate.get("deadlines", []):
        if norm(x["quote"]) not in text:
            problems.append(f"{candidate['candidate_id']}: quote not on pp. {a}-{b}: {x['quote'][:80]!r}")
    if candidate.get("action") and norm(candidate["action"]) not in text:
        problems.append(f"{candidate['candidate_id']}: action text not on pp. {a}-{b}")
    return problems


def verify_all(archive_root, candidates, allow_dirty=False):
    archive = Archive(archive_root, allow_dirty=allow_dirty)
    l1, cache, problems = l1_index(archive), {}, []
    for c in candidates:
        aa = c["source"]["annotated_agenda"]
        if aa not in cache:
            cache[aa] = agenda_text(archive, aa, l1)[0]
        problems += verify(c, cache[aa])
    return problems


def replay_check(archive_root):
    """docs/AUTOMATION_SPEC.md §12: the Restaurant Inspections direction of July 30, 2024 (Item 18) links
    to the December 10, 2024 status report (Item 22) as an unconfirmed candidate, and the deadline used
    is December 2024 from Council's recorded action, not the Auditor's January 2025."""
    cs, report = run(archive_root, "2024-07-30", "2024-12-31")
    problems = verify_all(archive_root, cs)
    d = next((c for c in cs if c["meeting_id"] == "city-council-2024-07-30" and c["item"] == "18"), None)
    if not d:
        return problems + ["no candidate for July 30, 2024 Item 18"]
    eff = d["effective_deadline"] or {}
    if eff.get("field") != "action" or "December 2024" not in eff.get("text", ""):
        problems.append(f"deadline used is {eff!r}, not December 2024 from the recorded action")
    if not any(x["field"] == "recommendation" and "January 2025" in x["text"] for x in d["deadlines"]):
        problems.append("the Auditor's January 2025 recommendation is not kept as a secondary deadline")
    link = [x for x in d["links"] if x["meeting_id"] == "city-council-2024-12-10" and x["item"] == "22"]
    if not link:
        problems.append("no proposed link to December 10, 2024 Item 22")
    elif link[0]["status"] != "unconfirmed" or d["review_status"] != "unconfirmed":
        problems.append("the link must stay unconfirmed")
    return problems


# ---- bundles ----------------------------------------------------------------------------------

def write_bundles(candidates, report, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    years = sorted({c["meeting_date"][:4] for c in candidates})
    for y in years:
        cs = [c for c in candidates if c["meeting_date"].startswith(y)]
        with open(os.path.join(out_dir, f"candidates-{y}.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"report": report, "candidates": cs}, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
        with open(os.path.join(out_dir, f"candidates-{y}.md"), "w", encoding="utf-8") as f:
            f.write(markdown(y, cs, report))
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    return years


def markdown(year, cs, report):
    out = [f"# Accountability candidates, {year}", "",
           f"Unconfirmed. Generated by rules version {report['rules_version']} from archive commit "
           f"`{report['archive_commit'][:12]}`. Confirm, correct or reject each; confirmed records go to "
           "`data/tracked/` by a reviewed PR.", ""]
    for c in cs:
        a, b = c["source"]["pages"]
        out += [f"## {c['meeting_date']} · Item {c['item']}: {c['title']}", "",
                f"- **Kind:** {c['kind']} · **Section:** {c['section'] or 'unknown'} · "
                f"**Source:** `{c['source']['annotated_agenda']}` pp. {a}–{b} ({c['source']['text_basis']['kind']})"]
        for x in c["matches"]:
            out.append(f"- **{x['rule']}** in {x['field']}: “{x['quote']}”")
        if c["effective_deadline"]:
            d = c["effective_deadline"]
            out.append(f"- **Deadline used:** {d['text']} (from {d['field']}, ends {d['ends']})")
            others = [x for x in c["deadlines"] if x is not d and x["text"] != d["text"]]
            for x in others:
                out.append(f"- Other deadline in {x['field']}: {x['text']}")
        out.append(f"- **Recorded action:** {c['action'] or '_none found_'}")
        if c["vote"]:
            out.append(f"- **Vote:** {c['vote']}")
        for ln in c["links"]:
            out.append(f"- **Possible follow-up (unconfirmed):** {ln['meeting_date']} Item {ln['item']}, "
                       f"{ln['title']}. Action: {ln['action'] or 'none found'}. Evidence: {'; '.join(ln['evidence'])}")
        for g in c["gaps"]:
            out.append(f"- Gap: {g}")
        out.append("")
    return "\n".join(out)
