# Agenda-intake dataset and site build

The first lane of Council Watch is agenda intake, as specified in
[AUTOMATION_SPEC.md](AUTOMATION_SPEC.md). It holds facts copied from official records and nothing
interpreted. Commitments, follow-up events and status judgments come later, as reviewed records kept
apart from this data.

## Commands

Python 3.11 or later, standard library only.

| Command | Does |
|---|---|
| `python3 -m councilwatch generate --archive PATH` | Regenerates `data/generated/agenda-intake/` from a clean checkout of `ericdf/berkeley-public-records` |
| `python3 -m councilwatch validate` | Checks the dataset: schemas, unique ids, status rules, item counts, forbidden text |
| `python3 -m councilwatch reproduce --archive PATH` | Regenerates into a scratch directory and fails unless the output is byte-identical |
| `python3 -m councilwatch build` | Renders the site into `_site/` (not committed) |
| `python3 -m councilwatch check-links` | Fails on any broken internal link or root-relative link in `_site/` |
| `python3 -m councilwatch paths FILE...` | Fails if any path is outside `data/generated/agenda-intake/`, for the unattended lane's PRs |
| `python3 -m unittest discover -s tests` | Unit tests, against a small fixture archive |

The generator needs only four folders of the archive: `catalog`, `manifest`, `L2` and `tools`. CI
uses a sparse, blob-filtered clone at the commit recorded in `meta.json`.

## Source

The archive at one pinned commit is the only input.

- **Meetings** come from the City's agenda listing, as catalogued in the archive at
  `catalog/city-council-agendas/meetings.json`.
- **Archived records for a meeting** (agenda packet, annotated agenda, caption transcripts) come from
  the archive's own join, `tools/meeting_map.py`. The rules for which document belongs to which
  meeting therefore live in one place.
- **Agenda items** come from the archive's packet item indexes (`L2/agenda-packets/`): the item
  number, section and heading as printed, and the page range in the packet's text.

## Files

All three are written with sorted keys, so the same archive commit and code always give the same
bytes. The schemas are in `councilwatch/schema/`.

| File | Contents |
|---|---|
| `meetings.json` | One record per meeting the City lists, newest first: date, type, City links, archived records with their fingerprints and archive links, and the number of indexed items |
| `items.json` | One record per agenda item in an archived, indexed packet. The fields are those required by AUTOMATION_SPEC.md §5 Stage D, plus `section`, `archive_id` and a `source_locator` giving the packet pages |
| `meta.json` | The pinned archive commit, the catalog's retrieval date and fingerprint, counts, and exceptions |

**IDs:** a meeting's `meeting_id` is the City's meeting slug, such as `city-council-2026-10-27`. An
item's `record_id` is the meeting id plus its item number, such as
`city-council-2026-10-27--item-2`. An item is never identified by its title.

**Archive links:** an external blob, such as an agenda packet, links to its Internet Archive item.
A file held in git links to the archive repository at the pinned commit, so the link always shows
the exact bytes the record describes.

## Item statuses

| Status | Rule |
|---|---|
| `scheduled` | The City listed the item and its agenda source is not yet archived. Not assigned yet: version 1 reads items only from archived packets |
| `source_archived` | The archived packet lists the item. This is every item in version 1 |
| `awaiting_meeting_record` | Reserved. Needs a rule that does not rest on elapsed time |
| `action_recorded` | Reserved for an item whose action a structured, authoritative record states. The validator rejects it until a generator version consumes such a source |

A status never advances because time has passed. The site states, wherever items appear, that an
agenda entry shows only that an item was scheduled.

## Exceptions

The generator records what it cannot resolve in `meta.json` → `exceptions` and publishes no record
for it:
- `duplicate_item_numbers`: two items in one packet index share a number;
- `missing_item_number`: an item has no number;
- `ambiguous_packet_index`: a meeting has several packet indexes and none matches the packet the
  City links.

`counts.archived_council_documents_without_catalog_meeting` counts archived Council documents with
no meeting in the City listing. They are mostly from before the listing's January 2021 start.

## Not yet built

- The unattended workflows: daily discovery in the archive, and sync and auto-merge here. Both wait on
  the records-archive policy change described in AUTOMATION_SPEC.md §2.
- The Pages deploy workflow. Enabling Pages is a separate maintainer step.
