"""Generate the council-time dataset: how long the Council spent on each part of each meeting, and
the correspondence it received, from the archive at a pinned commit.

Output, under data/generated/council-time/:
  segments.json        one record per segment of each caption transcript's L3 structure, with its
                       minutes and the minutes of public comment within it
  correspondence.json  one record per correspondence heading in each annotated agenda's L2 record
  turns.json           minutes of each reviewed speaker turn on a thread during general or consent
                       public comment (data/review/council-time/turns.json)
  meta.json            the pinned archive commit, counts, method constants, and exceptions

Minutes are computed, never typed. A timestamped (Zoom) transcript gives caption time. A
court-reporter transcript has no timestamps: a segment's minutes are its share of the transcript's
words times the meeting's length, from the reviewed clock in data/review/council-time/clock.json.
Those are estimates and are marked so. Which thread a segment belongs to is a reviewed
classification and is not here: docs/COUNCIL_TIME.md.
"""
import json
import os
import re

from .archive import ARCHIVE_REPO, Archive

GENERATOR_VERSION = 1
OUT_DIR = os.path.join("data", "generated", "council-time")
REVIEW_DIR = os.path.join("data", "review", "council-time")
STRUCTURE = "council_captions_structure"
CUE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.\d{3} --> ")
CLOCK = re.compile(r"^(\d{1,2}):(\d{2}) ([ap])\.m\.$")
# Calibration of the word-share estimate against timestamped transcripts (docs/COUNCIL_TIME.md).
CALIBRATION = {"segments": 89, "min_minutes": 10, "median_ratio": 1.01, "middle_half": [0.98, 1.05],
               "range": [0.78, 1.13]}
# Correspondence a Councilmember, the Mayor, City staff or a commission submitted, as the Clerk lists
# it, is counted apart from the public's (docs/COUNCIL_TIME.md).
OFFICIAL = re.compile(r"(submitted by|revised (agenda )?material|presentation|supplemental (material|report)|city manager|"
                      r"city attorney|city clerk|city auditor|councilmember|mayor ishii|office of|commission\b|"
                      r"department|staff)", re.I)
FORM = re.compile(r"similarly[- ]worded|form", re.I)


def secs(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def clock_minutes(t):
    m = CLOCK.match(t or "")
    if not m:
        raise ValueError(f"clock time {t!r} is not like '6:05 p.m.'")
    h = int(m.group(1)) % 12 + (12 if m.group(3) == "p" else 0)
    return (h + 24 if h < 4 else h) * 60 + int(m.group(2))   # before 4 a.m. is past midnight


def expand_items(item):
    """'18/19/20' -> ['18','19','20']; '22-29' -> 22..29; '1a-1d' -> 1a..1d; '43a-c' -> 43a..43c."""
    if not item:
        return []
    out = []
    for part in re.split(r"\s*(?:/|\+|,|\band\b)\s*", item):
        part = part.strip()
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m and int(m.group(1)) < int(m.group(2)):
            out += [str(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)]
            continue
        m = re.fullmatch(r"(\d+)([a-z])-(?:\1)?([a-z])", part)
        if m:
            out += [m.group(1) + chr(c) for c in range(ord(m.group(2)), ord(m.group(3)) + 1)]
            continue
        if re.fullmatch(r"\d+[a-z]?|[A-Z]", part):
            out.append(part)
    return out


def load_review(review_dir=REVIEW_DIR):
    out = {}
    for name in ("clock.json", "threads.json", "turns.json", "links.json"):
        with open(os.path.join(review_dir, name), encoding="utf-8") as f:
            out[name] = json.load(f)
    return out


def transcript_minutes(text, segments, clock):
    """(format, [(minutes, public_comment_minutes)] per segment, transcript minutes or None)."""
    lines = text.split("\n")
    if any(ln.strip() == "WEBVTT" for ln in lines[:60]):
        def span(a, b):
            return (secs(b) - secs(a)) / 60
        out = []
        for s in segments:
            t = span(s["start"], s["end"])
            pc = sum(span(p["start"], p["end"]) for p in s.get("public_comment") or [])
            out.append((t, min(pc, t)))
        cues = [secs(":".join(CUE.match(ln).groups())) for ln in lines if CUE.match(ln)]
        return "vtt", out, (cues[-1] - cues[0]) / 60 if cues else None
    words = [len(ln.split()) for ln in lines]
    total = sum(words)
    if not clock:
        return "cart", [(None, None) for _ in segments], None
    length = clock_minutes(clock["adjourned"]) - clock_minutes(clock["called_to_order"]) - clock["recess_minutes"]

    def est(a, b):
        return sum(words[a - 1:b]) / total * length
    out = []
    for s in segments:
        t = est(s["start_line"], s["end_line"])
        pc = sum(est(p["start_line"], p["end_line"]) for p in s.get("public_comment") or [])
        out.append((t, min(pc, t)))
    return "cart", out, length


def catalog_meetings(archive):
    return {(e["date"], e["label"]): e["meeting"] for e in archive.catalog()["entries"]
            if e["label"] in ("regular", "special")}


def structures(archive):
    ids = []
    for name in sorted(os.listdir(archive.path("manifest"))):
        if name.endswith("-structure.json"):
            e = archive.entry(name[:-5])
            if e.get("doc_type") == STRUCTURE:
                ids.append(e["id"])
    return ids


def segment_records(archive, review, exceptions):
    meetings = catalog_meetings(archive)
    clocks = review["clock.json"]["transcripts"]
    out = []
    for sid in structures(archive):
        e = archive.entry(sid)
        doc = archive.load(e["file"])
        tid = doc["transcript_id"]
        t = archive.entry(tid)
        with open(archive.path(t["file"]), encoding="utf-8") as f:
            text = f.read()
        fmt, mins, length = transcript_minutes(text, doc["segments"], clocks.get(tid))
        if fmt == "cart" and tid not in clocks:
            exceptions.append({"kind": "no_meeting_clock", "archive_ids": [tid]})
        for k, (s, (m, pc)) in enumerate(zip(doc["segments"], mins)):
            date, label = s["meeting"].split(" ", 1)
            mid = meetings.get((date, label))
            items = expand_items(s["item"])
            locator = {x: s[x] for x in ("start", "end", "start_line", "end_line") if x in s}
            out.append({
                "segment_id": f"{sid}#{k}",
                "structure_archive_id": sid,
                "transcript_archive_id": tid,
                "meeting_date": date,
                "meeting_body": label,
                "meeting_id": mid,
                "kind": s["kind"],
                "item_as_recorded": s["item"],
                "record_ids": [f"{mid}--item-{n}" for n in items] if mid else [],
                "minutes": None if m is None else round(m, 2),
                "public_comment_minutes": None if pc is None else round(pc, 2),
                "estimated": fmt == "cart",
                "locator": locator,
                "public_comment_locators": s.get("public_comment") or [],
                "evidence_start": s["evidence_start"],
                "boundary_level": s["level"],
                "archive_url": archive.archive_url(e),
            })
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


LABEL = re.compile(r"^(>>\s*)?[^:\n]{1,40}:\s")
NOTICE = re.compile(r"^(This information provided by |cannot certify the following text|following text since we did)")


def quote_found(quote, text, span):
    """True when the quotation's words occur, in order, in the transcript text within the span
    (an ellipsis marks words left out). Speaker labels and the City's page notice are ignored."""
    lines = text.split("\n")
    clean = lambda ln: "" if NOTICE.match(ln.strip()) else LABEL.sub("", ln)
    if "start" in span:
        a, b, keep, cur = secs(span["start"]), secs(span["end"]), [], None
        for ln in lines:
            m = CUE.match(ln)
            if m:
                cur = secs(":".join(m.groups()))
            elif cur is not None and a - 30 <= cur <= b and ln.strip() and not ln.strip().isdigit():
                keep.append(clean(ln))
    else:
        keep = [clean(ln) for ln in lines[max(0, span["start_line"] - 31):span["end_line"]]]
    window, pos = _norm(" ".join(keep)), 0
    for part in re.split(r"…|\.\.\.", quote):
        q = _norm(part)
        if q:
            i = window.find(q, pos)
            if i < 0:
                return False
            pos = i + len(q)
    return bool(_norm(quote))


def turn_records(archive, review, exceptions):
    """Minutes for each reviewed turn, computed as its transcript's segments are."""
    clocks = review["clock.json"]["transcripts"]
    texts, out = {}, []
    for k, t in enumerate(review["turns.json"]["turns"]):
        tid = t["transcript"]
        if tid not in texts:
            with open(archive.path(archive.entry(tid)["file"]), encoding="utf-8") as f:
                texts[tid] = f.read()
        span = {x: t[x] for x in ("start", "end", "start_line", "end_line") if x in t}
        fmt, mins, _ = transcript_minutes(texts[tid], [span], clocks.get(tid))
        if not quote_found(t["quote"], texts[tid], span):
            exceptions.append({"kind": "turn_quote_not_found", "turn_id": f"{tid}#turn-{k}"})
        out.append({"turn_id": f"{tid}#turn-{k}", "transcript_archive_id": tid, "meeting_date": archive.entry(tid).get("meeting_date"),
                    "thread": t["thread"], "extent": t["extent"], "locator": span, "estimated": fmt == "cart",
                    "minutes": None if mins[0][0] is None else round(mins[0][0], 2)})
    return out


def pick_records(archive):
    """The L2 record of each meeting's annotated agenda: the one the City lists, else the latest version."""
    by_aa = {}
    for name in sorted(os.listdir(archive.path("manifest"))):
        if name.endswith("-record.json"):
            e = archive.entry(name[:-5])
            if e.get("doc_type") == "annotated_agenda_record":
                by_aa[archive.load(e["file"])["annotated_agenda"]] = e["id"]
    out = {}
    for m in archive.meeting_map()["meetings"]:
        aas = sorted(m["archived"].get("annotated_agenda") or [])
        listed = m["listed"].get("annotated_agenda")
        superseded = {archive.entry(a).get("revision_of") for a in aas}
        pick = listed if listed in aas else next((a for a in reversed(aas) if a not in superseded), None)
        if pick and pick in by_aa:
            out[m["meeting"]] = by_aa[pick]
    return out


def correspondence_records(archive):
    out = []
    for mid, rid in sorted(pick_records(archive).items()):
        e = archive.entry(rid)
        rec = archive.load(e["file"])
        date = archive.entry(rec["annotated_agenda"]).get("meeting_date")
        for g in rec["communications"]:
            public = [x for x in g["entries"] if not (OFFICIAL.search(x["as_printed"]) and not FORM.search(x["as_printed"]))]
            out.append({
                "meeting_id": mid, "meeting_date": date, "record_archive_id": rid,
                "section": g["section"], "heading": g["heading"], "line": g["line"],
                "record_ids": [f"{mid}--item-{n}" for n in g["items"]],
                "entries": len(g["entries"]),
                "letters_public": sum(x["count"] for x in public),
                "form_letters": sum(x["count"] for x in public if x["count_basis"] == "similarly worded or form letters"),
                "letters_official": sum(x["count"] for x in g["entries"] if x not in public),
                "archive_url": archive.archive_url(e),
            })
    return out


def generate(archive, review):
    exceptions = []
    segs = segment_records(archive, review, exceptions)
    corr = correspondence_records(archive)
    turns = turn_records(archive, review, exceptions)
    known = {s["segment_id"] for s in segs}
    for a in review["threads.json"]["segments"]:
        if a["segment"] not in known:
            exceptions.append({"kind": "classified_segment_not_in_archive", "segment_id": a["segment"]})
    classified = {a["segment"] for a in review["threads.json"]["segments"]}
    for s in segs:
        if s["segment_id"] not in classified:
            exceptions.append({"kind": "unclassified_segment", "segment_id": s["segment_id"]})
    meta = {
        "dataset": "council-time",
        "generator_version": GENERATOR_VERSION,
        "source": {"archive_repository": ARCHIVE_REPO, "archive_commit": archive.commit},
        "calibration": CALIBRATION,
        "counts": {
            "transcripts": len({s["transcript_archive_id"] for s in segs}),
            "transcripts_estimated": len({s["transcript_archive_id"] for s in segs if s["estimated"]}),
            "segments": len(segs),
            "correspondence_headings": len(corr),
            "turns": len(turns),
            "meetings_with_correspondence": len({c["meeting_id"] for c in corr}),
        },
        "exceptions": exceptions,
    }
    segs.sort(key=lambda s: (s["meeting_date"], s["structure_archive_id"], int(s["segment_id"].rsplit("#", 1)[1])))
    corr.sort(key=lambda c: (c["meeting_date"], c["meeting_id"], c["section"], c["line"]))
    return {"segments.json": segs, "correspondence.json": corr, "turns.json": turns, "meta.json": meta}


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def write(dataset, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    for name, obj in dataset.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(dump(obj))


def run(archive_root, out_dir=OUT_DIR, review_dir=REVIEW_DIR, allow_dirty=False):
    dataset = generate(Archive(archive_root, allow_dirty=allow_dirty), load_review(review_dir))
    write(dataset, out_dir)
    return dataset


# Exceptions the generator records that must be resolved before the data can merge.
BLOCKING = ("no_meeting_clock", "unclassified_segment", "classified_segment_not_in_archive", "turn_quote_not_found")
NAMES = ("segments.json", "correspondence.json", "turns.json", "meta.json")


def validate(data_dir=OUT_DIR, review_dir=REVIEW_DIR, meeting_ids=None):
    """Errors in the generated council-time data and its reviewed inputs, as a list of messages."""
    from .validate import FORBIDDEN, check_schema, load_schema
    errors = []
    data, raw = {}, ""
    for name in NAMES:
        with open(os.path.join(data_dir, name), encoding="utf-8") as f:
            text = f.read()
        raw += text
        data[name] = json.loads(text)
    review = load_review(review_dir)
    for name in ("threads.json", "turns.json", "links.json"):
        with open(os.path.join(review_dir, name), encoding="utf-8") as f:
            raw += f.read()
    for m in FORBIDDEN.finditer(raw):
        errors.append(f"forbidden text in council-time data: {m.group(0)!r}")
    for name, schema, key in (("segments.json", "council_time_segment.schema.json", "segment_id"),
                              ("correspondence.json", "council_time_correspondence.schema.json", "heading"),
                              ("turns.json", "council_time_turn.schema.json", "turn_id")):
        sc = load_schema(schema)
        for r in data[name]:
            check_schema(r, sc, f"council-time/{name}[{r.get(key)}]", errors)
    rs = load_schema("council_time_review.schema.json")
    for name in ("threads.json", "turns.json", "links.json"):
        check_schema(review[name], rs, f"review/council-time/{name}", errors)
    cs = load_schema("council_time_clock.schema.json")
    for tid, c in review["clock.json"]["transcripts"].items():
        check_schema(c, cs, f"review/council-time/clock.json[{tid}]", errors)
        try:
            if clock_minutes(c["adjourned"]) - clock_minutes(c["called_to_order"]) - c["recess_minutes"] <= 0:
                errors.append(f"review/council-time/clock.json[{tid}]: meeting length is not positive")
        except (KeyError, ValueError) as x:
            errors.append(f"review/council-time/clock.json[{tid}]: {x}")

    threads = [t["id"] for t in review["threads.json"]["threads"]]
    for dup in sorted({t for t in threads if threads.count(t) > 1}):
        errors.append(f"review/council-time/threads.json: duplicate thread {dup}")
    known = set(threads)
    seen = []
    for a in review["threads.json"]["segments"]:
        seen.append(a["segment"])
        if a["thread"] not in known:
            errors.append(f"review/council-time/threads.json: segment {a['segment']} has unknown thread {a['thread']}")
    for dup in sorted({s for s in seen if seen.count(s) > 1}):
        errors.append(f"review/council-time/threads.json: segment {dup} is classified twice")
    for h in review["threads.json"]["correspondence_headings"]:
        if h["thread"] not in known:
            errors.append(f"review/council-time/threads.json: heading {h['heading']!r} has unknown thread {h['thread']}")
    for t in review["turns.json"]["turns"]:
        if t["thread"] not in known or t["thread"] == "routine":
            errors.append(f"review/council-time/turns.json: turn in {t['transcript']} has thread {t['thread']}")
        if ("start" in t) == ("start_line" in t):
            errors.append(f"review/council-time/turns.json: turn in {t['transcript']} needs start/end or start_line/end_line")
    for ln in review["links.json"]["links"]:
        for k in ("from", "to"):
            if ln[k] not in known:
                errors.append(f"review/council-time/links.json: link {ln['n']} {k} unknown thread {ln[k]}")

    ids = [s["segment_id"] for s in data["segments.json"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"council-time/segments.json: duplicate segment_id {dup}")
    if meeting_ids is not None:
        for s in data["segments.json"]:
            if s["meeting_id"] and s["meeting_id"] not in meeting_ids:
                errors.append(f"council-time/segments.json[{s['segment_id']}]: meeting {s['meeting_id']} is not in meetings.json")
    for s in data["segments.json"]:
        if s["minutes"] is not None and not 0 <= s["public_comment_minutes"] <= s["minutes"]:
            errors.append(f"council-time/segments.json[{s['segment_id']}]: public comment exceeds the segment")
    meta = data["meta.json"]
    for x in meta.get("exceptions", []):
        if x["kind"] in BLOCKING:
            errors.append(f"council-time/meta.json: unresolved exception {x}")
    for k, v in (("segments", len(data["segments.json"])), ("correspondence_headings", len(data["correspondence.json"])),
                 ("turns", len(data["turns.json"]))):
        if meta.get("counts", {}).get(k) != v:
            errors.append(f"council-time/meta.json: counts.{k} is {meta.get('counts', {}).get(k)}, data has {v}")
    if not re.fullmatch(r"[0-9a-f]{40}", meta.get("source", {}).get("archive_commit") or ""):
        errors.append("council-time/meta.json: source.archive_commit must be a full commit SHA")
    return errors
