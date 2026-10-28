"""Checks the generated dataset must pass before it can merge (docs/AUTOMATION_SPEC.md §9).

Standard library only. The JSON Schemas in councilwatch/schema/ are the contract; this module
implements the subset of JSON Schema they use.
"""
import json
import os
import re

from .generate import OUT_DIR, STATUSES

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schema")
TYPES = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}

# Text that must never appear in published data: local paths, session links, credentials.
FORBIDDEN = re.compile(
    r"/Users/|/home/[a-z]|file://|claude\.ai/code/session|BEGIN [A-Z ]*PRIVATE KEY|"
    r"gh[pousr]_[A-Za-z0-9]{20}|github_pat_|AKIA[0-9A-Z]{16}|xox[bp]-", re.I)

# The only paths the unattended agenda-intake lane may change (docs/AUTOMATION_SPEC.md §5, Stage E).
ALLOWED_GENERATED = ("data/generated/agenda-intake/",)


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def check_schema(value, schema, where, errors):
    if "$ref" in schema:
        return check_schema(value, load_schema(schema["$ref"]), where, errors)
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        ok = any(isinstance(value, TYPES[t]) and not (t == "integer" and isinstance(value, bool)) for t in types)
        if not ok:
            errors.append(f"{where}: expected {'/'.join(types)}, got {type(value).__name__}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: shorter than {schema['minLength']}")
    if isinstance(value, int) and not isinstance(value, bool) and value < schema.get("minimum", value):
        errors.append(f"{where}: below minimum {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: more than {schema['maxItems']} items")
        for i, v in enumerate(value):
            if "items" in schema:
                check_schema(v, schema["items"], f"{where}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errors.append(f"{where}: missing {k}")
        for k, v in value.items():
            if k in props:
                check_schema(v, props[k], f"{where}.{k}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}: unexpected field {k}")


def load_dataset(data_dir=OUT_DIR):
    out = {}
    for name in ("meetings.json", "items.json", "meta.json"):
        with open(os.path.join(data_dir, name), encoding="utf-8") as f:
            out[name] = json.load(f)
    return out


def validate(data_dir=OUT_DIR):
    errors = []
    raw = ""
    for name in ("meetings.json", "items.json", "meta.json"):
        with open(os.path.join(data_dir, name), encoding="utf-8") as f:
            raw += f.read()
    for m in FORBIDDEN.finditer(raw):
        errors.append(f"forbidden text in generated data: {m.group(0)!r}")
    d = load_dataset(data_dir)
    meetings, items, meta = d["meetings.json"], d["items.json"], d["meta.json"]

    ms, its = load_schema("meeting.schema.json"), load_schema("item.schema.json")
    for m in meetings:
        check_schema(m, ms, f"meetings[{m.get('meeting_id')}]", errors)
    for it in items:
        check_schema(it, its, f"items[{it.get('record_id')}]", errors)

    ids = [m.get("meeting_id") for m in meetings]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate meeting_id {dup}")
    rids = [it.get("record_id") for it in items]
    for dup in sorted({i for i in rids if rids.count(i) > 1}):
        errors.append(f"duplicate record_id {dup}")

    by_id = {m.get("meeting_id"): m for m in meetings}
    commit = meta.get("source", {}).get("archive_commit")
    counts = {}
    for it in items:
        where = f"items[{it.get('record_id')}]"
        m = by_id.get(it.get("meeting_id"))
        if not m:
            errors.append(f"{where}: meeting {it.get('meeting_id')} is not in meetings.json")
            continue
        counts[m["meeting_id"]] = counts.get(m["meeting_id"], 0) + 1
        if it.get("meeting_date") != m["meeting_date"] or it.get("meeting_type") != m["meeting_type"]:
            errors.append(f"{where}: meeting_date or meeting_type disagrees with its meeting")
        if it.get("source_archive_commit") != commit:
            errors.append(f"{where}: source_archive_commit differs from meta.json")
        # An agenda item records that something was scheduled. Version 1 has no structured action
        # source, so no item may claim more than that its source is archived.
        if it.get("status") in ("awaiting_meeting_record", "action_recorded"):
            errors.append(f"{where}: status {it['status']} needs an authoritative action source, "
                          "which generator version 1 does not consume")
        pages = (it.get("source_locator") or {}).get("pages") or []
        if len(pages) == 2 and pages[0] > pages[1]:
            errors.append(f"{where}: page range runs backwards")
    for m in meetings:
        if m.get("item_count") != counts.get(m.get("meeting_id"), 0):
            errors.append(f"meetings[{m.get('meeting_id')}]: item_count {m.get('item_count')} "
                          f"!= {counts.get(m.get('meeting_id'), 0)} items")

    if meta.get("status_vocabulary") != list(STATUSES):
        errors.append("meta.json: status_vocabulary differs from the generator's")
    want = {"meetings": len(meetings), "items": len(items)}
    for k, v in want.items():
        if meta.get("counts", {}).get(k) != v:
            errors.append(f"meta.json: counts.{k} is {meta.get('counts', {}).get(k)}, data has {v}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        errors.append("meta.json: source.archive_commit must be a full commit SHA")
    return errors


def check_paths(paths):
    """Paths outside the agenda-intake allowlist, for the unattended lane's PRs."""
    return [p for p in paths if not p.startswith(ALLOWED_GENERATED)]
