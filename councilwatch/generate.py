"""Generate the agenda-intake dataset from the archive.

Output, under data/generated/agenda-intake/:
  meetings.json  one record per City Council meeting the City lists
  items.json     one record per agenda item in an archived, indexed agenda packet
  meta.json      the pinned archive commit, counts, and exceptions

Every field is copied from an archive record or assigned by a rule in docs/DATA.md. Nothing is
inferred from titles or text. The same archive commit and code always produce the same bytes.
"""
import json
import os

from .archive import ARCHIVE_REPO, Archive

GENERATOR_VERSION = 1
OUT_DIR = os.path.join("data", "generated", "agenda-intake")

# Item status vocabulary (docs/DATA.md). Version 1 assigns only "source_archived": every item comes
# from an archived packet, and no structured, item-level action record is consumed yet.
STATUSES = ("scheduled", "source_archived", "awaiting_meeting_record", "action_recorded")
DOC_ROLES = ("agenda_packet", "annotated_agenda", "captions")


def docref(archive, archive_id, listed_id=None):
    e = archive.entry(archive_id)
    ref = {
        "archive_id": archive_id,
        "title": e.get("title"),
        "sha256": e["sha256"],
        "retrieved": e.get("retrieved"),
        "city_source_url": e.get("source_url"),
        "archive_url": archive.archive_url(e),
        "manifest_url": archive.manifest_url(archive_id),
    }
    if listed_id is not None:
        ref["listed_by_city"] = archive_id == listed_id
    for k in ("version_label", "revision_of"):
        if e.get(k):
            ref[k] = e[k]
    return ref


def meeting_record(archive, cat, joined, checked):
    archived = {}
    for role in DOC_ROLES:
        ids = sorted(joined["archived"].get(role) or [])
        if ids:
            listed = joined["listed"].get(role) if role != "captions" else None
            archived[role] = [docref(archive, i, listed) for i in ids]
    city = {k: cat["city"].get(k) for k in ("agenda_html", "agenda_packet", "annotated_agenda", "video")}
    return {
        "meeting_id": cat["meeting"],
        "meeting_date": cat["date"],
        "meeting_type": cat["label"],
        "name": cat["name"],
        "start_utc": cat.get("start_utc"),
        "city_page_url": cat["page_url"],
        "city_links": city,
        "archived": archived,
        "item_count": 0,
        "last_checked_at": checked,
    }


def pick_index(archive, joined, exceptions):
    """The packet item index for a meeting: the only one, or the one built from the packet the City
    currently links. Anything else is ambiguous and becomes an exception."""
    ids = sorted(joined["archived"].get("packet_index") or [])
    if len(ids) <= 1:
        return ids[0] if ids else None
    listed = joined["listed"].get("agenda_packet")
    hits = [i for i in ids if listed and archive.load(archive.entry(i)["file"]).get("packet") == listed]
    if len(hits) == 1:
        return hits[0]
    exceptions.append({"meeting_id": joined["meeting"], "kind": "ambiguous_packet_index", "archive_ids": ids})
    return None


def item_records(archive, meeting, index_id, checked, exceptions):
    index_entry = archive.entry(index_id)
    index = archive.load(index_entry["file"])
    packet = archive.entry(index["packet"])
    numbers = [it["item"] for it in index["items"]]
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    if dupes:
        exceptions.append({"meeting_id": meeting["meeting_id"], "kind": "duplicate_item_numbers",
                           "archive_ids": [index_id], "items": dupes})
    out = []
    for it in index["items"]:
        n = (it.get("item") or "").strip()
        if not n or n in dupes:
            if not n:
                exceptions.append({"meeting_id": meeting["meeting_id"], "kind": "missing_item_number",
                                   "archive_ids": [index_id]})
            continue
        out.append({
            "record_id": f"{meeting['meeting_id']}--item-{n}",
            "meeting_id": meeting["meeting_id"],
            "meeting_date": meeting["meeting_date"],
            "meeting_type": meeting["meeting_type"],
            "agenda_item_number": n,
            "section": it.get("section"),
            "official_title": it["heading"],
            "status": "source_archived",
            "city_source_url": packet["source_url"],
            "archive_id": packet["id"],
            "archive_url": archive.archive_url(packet),
            "source_sha256": packet["sha256"],
            "source_retrieved_at": packet.get("retrieved"),
            "source_locator": {"pages": it["pages"], "page_basis": index["page_basis"],
                               "index_archive_id": index_id},
            "source_archive_commit": archive.commit,
            "last_checked_at": checked,
        })
    return out


def generate(archive):
    catalog = archive.catalog()
    checked = catalog["retrieved"]
    joined = {m["meeting"]: m for m in archive.meeting_map()["meetings"]}
    meetings, items, exceptions = [], [], []
    for cat in catalog["entries"]:
        m = meeting_record(archive, cat, joined[cat["meeting"]], checked)
        index_id = pick_index(archive, joined[cat["meeting"]], exceptions)
        if index_id:
            its = item_records(archive, m, index_id, checked, exceptions)
            m["item_count"] = len(its)
            items.extend(its)
        meetings.append(m)
    meetings.sort(key=lambda m: (m["meeting_date"], m["meeting_id"]), reverse=True)
    items.sort(key=lambda i: (i["meeting_date"], i["meeting_id"], _item_key(i["agenda_item_number"])))
    unmatched = archive.meeting_map()["unmatched"]
    meta = {
        "dataset": "agenda-intake",
        "generator_version": GENERATOR_VERSION,
        "source": {
            "archive_repository": ARCHIVE_REPO,
            "archive_commit": archive.commit,
            "catalog_url": catalog["source"]["url"],
            "catalog_listing_sha256": catalog["source"].get("listing_sha256"),
            "catalog_retrieved": checked,
        },
        "status_vocabulary": list(STATUSES),
        "counts": {
            "meetings": len(meetings),
            "meetings_with_archived_documents": sum(1 for m in meetings if m["archived"]),
            "meetings_with_indexed_items": sum(1 for m in meetings if m["item_count"]),
            "items": len(items),
            "archived_council_documents_without_catalog_meeting": len(unmatched),
        },
        "exceptions": exceptions,
    }
    return {"meetings.json": meetings, "items.json": items, "meta.json": meta}


def _item_key(n):
    digits = "".join(ch for ch in n if ch.isdigit())
    return (int(digits) if digits else 10**6, n)


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def write(dataset, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    for name, obj in dataset.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(dump(obj))


def run(archive_root, out_dir=OUT_DIR, allow_dirty=False):
    dataset = generate(Archive(archive_root, allow_dirty=allow_dirty))
    write(dataset, out_dir)
    return dataset
