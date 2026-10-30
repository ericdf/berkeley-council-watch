"""Turn review decisions on backfill candidates into tracked records.

A reviewer writes data/review/decisions-<year>.json: for each candidate in a Pass 2 bundle, confirm or
reject (with a reason), and for a confirmed direction, the matter, a label, the responsible actor and,
for each proposed follow-up, confirm (with a status) or reject. Everything else (source records,
citations, quotes, dates, the due date, events) comes mechanically from the bundle and the archive, so a
reviewer makes judgments and never types record text. docs/REVIEW.md.
"""
import json
import os

from . import tracked
from .archive import Archive, ArchiveError
from .validate import check_schema, load_schema

LINK_STATUSES = {"in_progress_reported", "reported_complete", "reported_not_met", "delayed",
                 "cancelled_or_superseded"}
COMMITMENT_KINDS = {"report_back", "deliverable", "deadline", "spending_condition", "outcome_measure"}


class DecisionError(Exception):
    pass


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def source_for(archive, aa_id):
    e = archive.entry(aa_id)
    return {
        "id": f"src-{aa_id}", "kind": "annotated_agenda",
        "issuer": "City of Berkeley, City Clerk Department",
        "title": e.get("title") or f"Annotated Agenda {aa_id}",
        "document_date": e.get("meeting_date") or e.get("document_date"),
        "note": None, "official_url": e.get("source_url"),
        "archive_id": aa_id, "archive_url": archive.archive_url(e),
        "sha256": e["sha256"], "retrieved": e.get("retrieved"),
    }


def _pages(p):
    return f"p. {p[0]}" if p[0] == p[1] else f"pp. {p[0]}–{p[1]}"


def _locator(item, field, pages):
    return f"Item {item}, {field.title()} ({_pages(pages)})"


def build(bundle, decisions, archive):
    """Records to add to data/tracked/, keyed by file name. Raises DecisionError on any bad decision."""
    if decisions.get("archive_commit") != bundle["report"]["archive_commit"]:
        raise DecisionError("decisions name a different archive commit than the bundle")
    if archive.commit != bundle["report"]["archive_commit"]:
        raise DecisionError(f"archive checkout is at {archive.commit[:12]}, bundle was built from "
                            f"{bundle['report']['archive_commit'][:12]}")
    cands = {c["candidate_id"]: c for c in bundle["candidates"]}
    out = {name: [] for name in tracked.FILES}
    seen_sources, errors = set(), []

    def add_source(aa_id):
        if aa_id not in seen_sources:
            seen_sources.add(aa_id)
            out["sources.json"].append(source_for(archive, aa_id))
        return f"src-{aa_id}"

    for d in decisions["decisions"]:
        cid = d.get("candidate_id")
        where = f"decision {cid}"
        c = cands.get(cid)
        if not c:
            errors.append(f"{where}: not in the bundle")
            continue
        if d.get("decision") == "reject":
            if not d.get("reason"):
                errors.append(f"{where}: a rejection needs a reason")
            continue
        if d.get("decision") != "confirm":
            errors.append(f"{where}: decision must be confirm or reject")
            continue
        if c["kind"] != "direction":
            errors.append(f"{where}: only a direction can be confirmed as a commitment; confirm a follow-up "
                          "report as a link on its direction")
            continue
        com = d.get("commitment") or {}
        missing = [k for k in ("label", "actor", "kind") if not com.get(k)]
        if missing:
            errors.append(f"{where}: commitment needs {', '.join(missing)}")
            continue
        if com["kind"] not in COMMITMENT_KINDS:
            errors.append(f"{where}: commitment kind must be one of {sorted(COMMITMENT_KINDS)}")
            continue
        field = com.get("quote_field", "action" if c.get("action") else "recommendation")
        # The sentence carrying the direction, as matched; the whole Action only if no rule matched there.
        quote = next((m["quote"] for m in c["matches"] if m["field"] == field), None)
        if quote is None and field == "action":
            quote = c.get("action")
        if not quote:
            errors.append(f"{where}: no {field} text in the candidate to quote")
            continue

        matter_id = d.get("matter_id") or (d.get("matter") or {}).get("id")
        if not matter_id:
            errors.append(f"{where}: needs matter_id (existing) or matter (new)")
            continue
        src = add_source(c["source"]["annotated_agenda"])
        loc = _locator(c["item"], field, c["source"]["pages"])
        action_cite = {"source_id": src, "locator": _locator(c["item"], "action", c["source"]["pages"]),
                       "quote": c["action"]} if c.get("action") else None
        if d.get("matter"):
            m = d["matter"]
            out["matters.json"].append({
                "id": matter_id, "title": m["title"], "kind": m.get("kind", "council_referral"),
                "opened": c["meeting_date"], "description": m["description"],
                "agenda_items": [{"meeting_id": c["meeting_id"], "item": c["item"]}],
                "qualifications": [], "last_reviewed": decisions["reviewed_on"],
            })
        eff = c.get("effective_deadline")
        cid_short = cid.replace("city-council-", "")
        commitment = {
            "id": f"{matter_id}--{cid_short}", "matter_id": matter_id, "recommendation_id": None,
            "kind": com["kind"], "label": com["label"], "statement": quote, "actor": com["actor"],
            "due": {"as_stated": eff["text"].split(" ", 1)[1] if eff else None, "is_date": bool(eff)},
            "success_measure": None,
            "citation": {"source_id": src, "locator": loc, "quote": quote},
            "status_history": [{
                "as_of": c["meeting_date"],
                "status": "not_yet_due" if eff else "no_due_date_stated",
                "basis": f"The City Council took the recorded action on Item {c['item']}."
                         + (f" The deadline used is from the {eff['field']}: \"{eff['text']}\"." if eff else ""),
                "citations": [action_cite] if action_cite else [{"source_id": src, "locator": loc}],
            }],
        }
        out["events.json"].append({
            "id": f"{commitment['id']}--action", "matter_id": matter_id, "date": c["meeting_date"],
            "actor": "City Council", "kind": "council_action",
            "description": f"Item {c['item']}, \"{c['title']}\", was on the agenda, with the recorded action quoted.",
            "citations": [action_cite] if action_cite else [{"source_id": src, "locator": loc}],
            "commitment_ids": [commitment["id"]], "recommendation_ids": [],
        })
        links = {f"{x['meeting_id']}--item-{x['item']}": x for x in c.get("links") or []}
        for ld in d.get("links") or []:
            lw = f"{where} link {ld.get('to')}"
            x = links.get(ld.get("to"))
            if not x:
                errors.append(f"{lw}: not a proposed link of this candidate")
                continue
            if ld.get("decision") == "reject":
                if not ld.get("reason"):
                    errors.append(f"{lw}: a rejection needs a reason")
                continue
            if ld.get("decision") != "confirm" or ld.get("status") not in LINK_STATUSES or not ld.get("basis"):
                errors.append(f"{lw}: confirm needs a status ({', '.join(sorted(LINK_STATUSES))}) and a basis")
                continue
            target = next((t for t in bundle["candidates"]
                           if t["meeting_id"] == x["meeting_id"] and t["item"] == x["item"]), None)
            if not target:
                errors.append(f"{lw}: the follow-up item is not in this bundle; review it with its own year")
                continue
            lsrc = add_source(target["source"]["annotated_agenda"])
            lcite = {"source_id": lsrc, "locator": _locator(target["item"], "action", target["source"]["pages"])}
            if target.get("action"):
                lcite["quote"] = target["action"]
            commitment["status_history"].append({"as_of": x["meeting_date"], "status": ld["status"],
                                                 "basis": ld["basis"], "citations": [lcite]})
            out["events.json"].append({
                "id": f"{commitment['id']}--follow-up-{x['meeting_date']}-item-{x['item']}",
                "matter_id": matter_id, "date": x["meeting_date"], "actor": ld.get("actor", "City staff"),
                "kind": "staff_report",
                "description": f"Item {x['item']}, \"{x['title']}\", was on the agenda, with the recorded action quoted.",
                "citations": [lcite], "commitment_ids": [commitment["id"]], "recommendation_ids": [],
            })
        commitment["status_history"].sort(key=lambda h: h["as_of"])
        out["commitments.json"].append(commitment)
    if errors:
        raise DecisionError("\n".join(errors))
    return out


def merge(tracked_dir, additions):
    """Append additions to data/tracked/. An id already present must be identical (a re-import is a
    no-op); a different record under an existing id is an error, never an overwrite."""
    existing = tracked.load(tracked_dir)
    conflicts, added = [], 0
    for name, recs in additions.items():
        by_id = {r["id"]: r for r in existing[name]}
        for r in recs:
            if r["id"] in by_id:
                if by_id[r["id"]] != r and name != "sources.json":
                    conflicts.append(f"{name}: {r['id']} already exists with different content")
                continue
            existing[name].append(r)
            by_id[r["id"]] = r
            added += 1
    if conflicts:
        raise DecisionError("\n".join(conflicts))
    for name in additions:
        _dump(os.path.join(tracked_dir, name), existing[name])
    return added


def check_decisions_file(decisions):
    errors = []
    check_schema(decisions, load_schema("decisions.schema.json"), "decisions", errors)
    return errors


def run(bundle_path, decisions_path, archive_root, tracked_dir=tracked.TRACKED_DIR):
    bundle, decisions = _load(bundle_path), _load(decisions_path)
    errors = check_decisions_file(decisions)
    if errors:
        raise DecisionError("\n".join(errors))
    try:
        archive = Archive(archive_root)
    except ArchiveError as x:
        raise DecisionError(str(x))
    additions = build(bundle, decisions, archive)
    added = merge(tracked_dir, additions)
    undecided = sorted({c["candidate_id"] for c in bundle["candidates"]}
                       - {d["candidate_id"] for d in decisions["decisions"]})
    return added, undecided
