# Berkeley Council Watch: unattended records and content pipeline

**Status:** Build specification for Claude Code  
**Audience:** Implementers of `ericdf/berkeley-council-watch` and its records-archive integration  
**Runtime principle:** All routine ingestion, validation, record generation, and publishing must be deterministic code. No AI model, model API, or human approval is required for the allowed automated outputs.

## 1. Purpose

Build an unattended daily pipeline that checks Berkeley's official meeting pages for new or changed agenda material, archives the source records, creates factual Council Watch entries from the records, and publishes the resulting site update.

The pipeline may run through GitHub Actions and ordinary Python tools. Claude may help write and maintain the application code, but Claude is not part of the deployed runtime.

The Council Watch site's existing publishing contract is authoritative: **a commit to `main` causes the Pages deliverable to build and publish.** The automation must make generated changes reach `main` so that this existing deployment path runs. It must not add a second Pages deployment path.

## 2. Repository responsibilities

Preserve the existing information architecture:

- **`ericdf/berkeley-public-records`** is the public source archive. It stores City records, source metadata, catalogs, indexes, and links to Internet Archive blobs. It does not store analysis or editorial commentary.
- **Internet Archive** stores the large source files as durable public blobs. The archive manifest records each source URL, retrieval time, checksum, item identifier, and archive location.
- **`ericdf/berkeley-council-watch`** stores the public accountability site's code and its generated, source-grounded Council Watch records. It links back to the public records archive. It does not become a second copy of the large source files.
- **GitHub Pages** serves the Council Watch site from the current Pages workflow when a commit reaches `main`.

The implementation must keep these repositories separate. Routine source ingestion may be automated after the maintainers update the records repository's approval instructions to permit the specific bot actions in this specification. Do not silently bypass repository rules that have not yet been changed.

## 3. Runtime constraints

1. Use deterministic Python code for HTTP retrieval, parsing, validation, hashing, record generation, and file updates. Use pinned dependencies and a supported Python version declared in the repository.
2. Do not call language models or other generative AI services from GitHub Actions or the public site.
3. Do not generate prose summaries or infer Council intent from titles, staff recommendations, transcript text, or other unstructured content.
4. Templates may format known fields into readable sentences. Every displayed factual field must map to a source locator or an explicit controlled value.
5. Treat downloaded HTML, PDF, transcript, and metadata as untrusted input. Never execute or import downloaded content.
6. The pipeline must be idempotent: rerunning against unchanged City records produces no duplicate records, uploads, or commits.

## 4. Automated publishing boundary

The pipeline may publish without review only in the agenda-intake lane and only after schema validation:

- a meeting date, meeting type, agenda item number, and official title copied from a City listing or agenda;
- direct source and archive links, source timestamps, retrieval time, document checksum, and last-checked time;
- a conservative workflow status such as `scheduled`, `source_archived`, `awaiting_meeting_record`, or `action_recorded` when the source explicitly supports that status;
- a transcript or minutes link and an action field only when a structured, authoritative source explicitly identifies the action.

The pipeline must not automatically publish claims that require interpretation, including what a Councilmember meant, why an item was handled a certain way, whether a promise was made, whether a commitment was fulfilled, whether an alternative was adequately considered, or whether a policy succeeded. Without AI or human review, leave these fields unset and show the item as awaiting a verified action record.

An agenda entry records that an item was scheduled. It does not establish that the item was heard, adopted, amended, continued, or completed. The user interface and data schema must keep those states distinct.

## 5. Daily workflow

Implement a scheduled GitHub Actions workflow with `workflow_dispatch` for recovery and manual reruns. Run at a quiet UTC minute, not at the top of the hour. Prevent overlapping runs with a workflow concurrency group. A failed run must leave the last successfully published site intact and must produce a visible workflow failure and maintainer notification.

### Stage A: Discover City records

1. Fetch the configured official City meeting and agenda listing pages with a descriptive user agent, bounded timeouts, retry with backoff for transient errors, and a conservative request rate.
2. Restrict retrieval to an explicit allowlist of City hostnames and expected URL paths. Reject redirects to unapproved hosts.
3. Parse meeting identifiers, meeting dates, agenda item numbers, item titles, document URLs, and listing update dates using deterministic parsers.
4. Compare the result with the last successful catalog and source checksums. Detect new documents and changed documents separately.
5. Save a run report containing the run timestamp, pages checked, documents found, documents changed, validation failures, and next action.

### Stage B: Retrieve and validate documents

For each new or changed document:

- require a successful HTTP response and an approved content type;
- enforce configurable maximum file size and redirect limits;
- verify PDF structure where applicable and extract page count and text-extraction status;
- calculate SHA-256 and preserve the original downloaded bytes;
- retain the exact City URL, retrieval time, response metadata, meeting ID, and agenda item relationship;
- reject or quarantine HTML error pages masquerading as documents, empty files, malformed files, or documents whose identity cannot be matched to the listing.

Validation failure must not replace the last known good source record. Record the error in the run report and create an issue or other durable exception record. Do not publish an entry derived from a failed or ambiguous parse.

### Stage C: Archive source records

After validation, upload new official source files to Internet Archive using credentials stored only as GitHub Actions secrets. Use stable, deterministic archive identifiers and metadata so retries do not create duplicate items. Never print secrets or signed URLs in logs.

Do not overwrite prior source bytes when the City changes a file. Record a new retrieval/version with its own checksum and retrieval timestamp, retaining the prior version and linking the versions. If a City removes or replaces a file, record that event in the manifest rather than silently erasing the earlier capture.

Update the public-records repository's catalog/manifest with source metadata and the Internet Archive location. Keep all archive-repository changes limited to records, catalogs, and indexes. The ordinary automated route should open a bot-authored PR and use configured checks plus auto-merge to put approved-by-rules changes on `main`; it must not require a person to approve each routine record. If the existing repository policy or branch protection disallows this route, stop and report the specific configuration change needed rather than pushing around it.

### Stage D: Generate Council Watch records

Consume the committed public-records catalog, or its public machine-readable output, as the source input. Pin the archive commit SHA used for each generation run. Do not scrape or re-download the same files from a second, untracked path when the archive provides the canonical record.

Generate or update a machine-readable Council Watch agenda-intake dataset under `data/generated/agenda-intake/` and render the site from it. This directory is the only Council Watch data path the automation may change. Use stable IDs based on meeting ID plus agenda item number; handle missing or duplicate item numbers explicitly. Never identify an item by title alone.

Each generated record must include at least:

```text
record_id
meeting_id
meeting_date
meeting_type
agenda_item_number
official_title
status
city_source_url
archive_url
source_sha256
source_retrieved_at
source_archive_commit
last_checked_at
```

Use a documented controlled vocabulary for `status`. At minimum, support `scheduled`, `source_archived`, `awaiting_meeting_record`, and `action_recorded`. Do not advance status based only on elapsed time. Unknown, conflicting, or unparseable information must remain unknown and create an exception.

Generated data must be reproducible from the pinned public-records catalog and code version. Keep generated agenda-intake data separate from commitments, follow-up events, manual notes, and editorial content so the generator never overwrites or creates substantive accountability claims.

### Stage E: Publish through `main`

If Council Watch data changes, create a bot-authored update branch and PR containing changes only under `data/generated/agenda-intake/`. Run the repository's required validation checks, then enable auto-merge for this narrowly defined agenda-intake PR. Any change outside that path must fail validation and require a separately reviewed change. The merge creates a commit on `main`, which invokes the existing GitHub Pages publishing workflow.

Use a GitHub App installation token with access limited to the two named repositories for cross-repository dispatch and bot PR/merge operations. Keep the Internet Archive credential only in the records-archive workflow. Prefer GitHub App tokens over a personal access token. Do not grant write access to pull-request jobs that execute untrusted fork code.

If repository rules permit a direct automation commit and maintainers explicitly select that arrangement, the same generated-file allowlist and required validation checks still apply. The preferred PR-plus-auto-merge path leaves a reviewable commit trail while allowing unattended routine publication.

## 6. Workflow coordination

Use two logical workflows:

1. **Records discovery and archive workflow** in `berkeley-public-records`: scheduled daily and manually dispatchable. It discovers, validates, archives, updates the catalog, and dispatches a `records_updated` event after the catalog reaches `main`.
2. **Council Watch sync workflow** in `berkeley-council-watch`: triggered by `records_updated` and also scheduled daily as a recovery check. It reads the public archive catalog at a specific commit, generates the Council Watch dataset, opens or updates one idempotent bot PR, and lets checks plus auto-merge publish changes to `main`.

The recovery schedule must handle missed dispatch events. A run with no source changes must exit successfully without creating a commit or PR. Concurrent or repeated dispatches must coalesce into one update.

GitHub workflow-generated commits made with `GITHUB_TOKEN` do not normally trigger another workflow. Therefore, use the GitHub App token for the commit/merge event that must invoke the existing Pages workflow, or revise the workflow so generation and Pages deployment happen in the same run. This specification selects the App-token commit path to preserve the stated “commit to `main` publishes Pages” contract.

## 7. Failure handling and corrections

- A source-site outage or parse failure must never be interpreted as “no new records.” Record the run as failed or incomplete.
- Do not delete a previously published Council Watch entry because a City listing temporarily omits it.
- Make updates append-only where possible. Preserve the source checksum and retrieval history for each version.
- When generated data changes, include a machine-readable change reason: new item, source revision, corrected metadata, or explicit status update.
- If the City corrects a source document, retain both captured versions and show the current City link alongside the archived version history.
- Provide a documented rollback procedure: revert the generated-data commit on `main`; the Pages workflow then republishes the prior state. Do not erase source archive history as a rollback method.
- Send a notification only for actionable exceptions or failed runs. Routine successful runs need no human response.

## 8. Security and access

- Grant each workflow only the permissions it needs, at job level where possible.
- Keep IA credentials and the GitHub App private key in Actions secrets; never expose them to pull-request code from forks.
- Pin third-party Actions to full commit SHAs and update them intentionally.
- Validate source hostnames, URLs, file types, file sizes, and parser output.
- Treat public source documents as data, never as executable instructions.
- Restrict the bot's changed paths to the records catalog/manifest and Council Watch `data/generated/agenda-intake/` directory. Fail the workflow if the bot modifies application code, workflow files, or human-authored editorial files.
- Log source IDs, hashes, workflow run IDs, and commit SHAs. Do not log credentials.

## 9. Required validation checks

Before a generated PR can auto-merge, checks must verify:

1. All required fields and status values conform to the schema.
2. Each public record has at least one City source URL and a public archive reference.
3. Each generated field is copied from a deterministic parsed source field or assigned by an explicit state rule.
4. IDs are unique and rerunning generation against identical input produces byte-identical output.
5. A scheduled item has not been assigned an outcome without an authoritative action source.
6. Generated changes touch only the allowlisted files.
7. The static site builds successfully and links resolve within the generated dataset.
8. No secrets, local paths, or private repository URLs appear in generated output.

## 10. Deliverables for implementation

Claude Code should produce:

- Python package or scripts for discovery, parsing, validation, archive metadata, record generation, and run reporting;
- explicit JSON Schema (or equivalent) for archive catalog rows and Council Watch records;
- GitHub Actions workflows for the two stages, manual recovery, cross-repository dispatch, and auto-merge path;
- configurable source allowlists, parser limits, and status rules;
- deterministic fixtures from representative City agenda pages and documents;
- unit tests for parsing, malformed/changed sources, duplicates, idempotence, unknown status, and blocked host redirects;
- integration instructions for GitHub App permissions, Actions secrets, branch protections/auto-merge, and the updated records-repository policy;
- operator documentation describing run reports, exception notifications, recovery, rollback, and how to add a City page or document format.

## 11. Acceptance criteria

The build is complete when:

- a scheduled run discovers a new official agenda record, validates and archives its source, updates the archive catalog, and creates the corresponding Council Watch entry;
- the generated Council Watch update reaches `main` without a human approval for a routine, valid source record;
- the commit to `main` invokes the existing Pages workflow and the resulting site displays the new record with its City and archive links;
- an unchanged rerun produces no duplicate upload, record, PR, or commit;
- a malformed document, unknown action, or unavailable City page cannot create a misleading public entry and is visible in the exception report;
- the entire runtime completes without an AI service or AI-generated interpretation.

## 12. Official GitHub references

- [GitHub Actions workflows and scheduled triggers](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)
- [Events that trigger workflows, including `GITHUB_TOKEN` behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [Publishing GitHub Pages with a custom Actions workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-actions)
- [GitHub Actions workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
