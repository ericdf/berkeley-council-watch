"""Reviewed accountability records: matters, findings, recommendations, commitments, events.

Unlike the agenda-intake dataset, these files are written by people and reviewed in pull requests
(docs/IMPLEMENTATION.md). This module loads and checks them; it never writes them.
"""
import json
import os
import re

from .validate import FORBIDDEN, check_schema, load_schema

TRACKED_DIR = os.path.join("data", "tracked")
FILES = {
    "sources.json": "source.schema.json",
    "matters.json": "matter.schema.json",
    "findings.json": "finding.schema.json",
    "recommendations.json": "recommendation.schema.json",
    "commitments.json": "commitment.schema.json",
    "events.json": "event.schema.json",
}

# A City statement that work is complete supports "reported_complete" only. "completion_verified"
# needs a record independent of that statement (docs/IMPLEMENTATION.md, Status and history).
INDEPENDENT_KINDS = {"auditor_follow_up", "executed_contract", "adopted_legislation", "published_deliverable"}
NEEDS_DUE = {"not_yet_due", "delayed"}


def load(tracked_dir=TRACKED_DIR):
    out = {}
    for name in FILES:
        with open(os.path.join(tracked_dir, name), encoding="utf-8") as f:
            out[name] = json.load(f)
    return out


def citations_of(record):
    for k in ("citation",):
        if record.get(k):
            yield record[k]
    for k in ("citations", "qualifications"):
        yield from record.get(k) or []
    for entry in record.get("status_history") or []:
        yield from entry.get("citations") or []


def validate(tracked_dir=TRACKED_DIR, meeting_ids=None):
    errors = []
    raw = ""
    for name in FILES:
        with open(os.path.join(tracked_dir, name), encoding="utf-8") as f:
            raw += f.read()
    for m in FORBIDDEN.finditer(raw):
        errors.append(f"forbidden text in tracked data: {m.group(0)!r}")
    d = load(tracked_dir)

    ids = {}
    for name, schema_name in FILES.items():
        schema = load_schema(schema_name)
        for rec in d[name]:
            where = f"{name}[{rec.get('id')}]"
            check_schema(rec, schema, where, errors)
            if rec.get("id") in ids:
                errors.append(f"{where}: id also used in {ids[rec['id']]}")
            ids[rec.get("id")] = name

    sources = {s["id"]: s for s in d["sources.json"]}
    matters = {m["id"] for m in d["matters.json"]}
    findings = {f["id"] for f in d["findings.json"]}
    recs = {r["id"] for r in d["recommendations.json"]}
    commitments = {c["id"] for c in d["commitments.json"]}

    def ref(where, value, pool, what):
        if value is not None and value not in pool:
            errors.append(f"{where}: {what} {value!r} does not exist")

    for name in FILES:
        for rec in d[name]:
            where = f"{name}[{rec.get('id')}]"
            for c in citations_of(rec):
                ref(where, c.get("source_id"), sources, "source")
            if "matter_id" in rec:
                ref(where, rec["matter_id"], matters, "matter")
    for s in d["sources.json"]:
        if not (s.get("official_url") or s.get("archive_id")):
            errors.append(f"sources.json[{s['id']}]: needs an archive_id or an official_url")
        if bool(s.get("archive_id")) != bool(s.get("archive_url")):
            errors.append(f"sources.json[{s['id']}]: archive_id and archive_url go together")
    for m in d["matters.json"]:
        for a in m.get("agenda_items") or []:
            if meeting_ids is not None and a["meeting_id"] not in meeting_ids:
                errors.append(f"matters.json[{m['id']}]: agenda meeting {a['meeting_id']} is not in the agenda-intake data")
    for r in d["recommendations.json"]:
        ref(f"recommendations.json[{r['id']}]", r.get("finding_id"), findings, "finding")
    for e in d["events.json"]:
        where = f"events.json[{e['id']}]"
        for c in e.get("commitment_ids") or []:
            ref(where, c, commitments, "commitment")
        for r in e.get("recommendation_ids") or []:
            ref(where, r, recs, "recommendation")

    for c in d["commitments.json"]:
        where = f"commitments.json[{c['id']}]"
        ref(where, c.get("recommendation_id"), recs, "recommendation")
        hist = c.get("status_history") or []
        dates = [h.get("as_of") for h in hist]
        if dates != sorted(dates):
            errors.append(f"{where}: status_history is not in date order")
        for h in hist:
            hw = f"{where} status {h.get('as_of')}"
            st = h.get("status")
            if st in NEEDS_DUE and not (c.get("due") or {}).get("is_date"):
                errors.append(f"{hw}: {st} needs a stated due date or period")
            if st == "no_due_date_stated" and (c.get("due") or {}).get("is_date"):
                errors.append(f"{hw}: no_due_date_stated, but the commitment has a stated date")
            if st == "unknown_no_update_located" and not h.get("searched"):
                errors.append(f"{hw}: unknown_no_update_located must say what was searched")
            if st not in ("unknown_no_update_located",) and not h.get("citations") and not h.get("searched"):
                errors.append(f"{hw}: {st} needs a citation")
            if st == "completion_verified":
                kinds = {sources.get(x.get("source_id"), {}).get("kind") for x in h.get("citations") or []}
                if not kinds & INDEPENDENT_KINDS:
                    errors.append(f"{hw}: completion_verified needs a citation to an independent record "
                                  f"({', '.join(sorted(INDEPENDENT_KINDS))}); a City statement supports "
                                  "reported_complete only")
    for name in FILES:
        for rec in d[name]:
            for c in citations_of(rec):
                if c.get("quote") and re.search(r"\s{2,}|(?<=\w)- \w", c["quote"]):
                    errors.append(f"{name}[{rec.get('id')}]: quote has spacing or a broken hyphen; copy it exactly")
    return errors


def current_status(commitment):
    return commitment["status_history"][-1]
