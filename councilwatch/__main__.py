"""Command line: python3 -m councilwatch <command>

  generate --archive PATH   regenerate data/generated/agenda-intake/ from an archive checkout
  validate                  check the generated dataset and the reviewed records in data/tracked/
  reproduce --archive PATH  regenerate into a scratch directory and require byte-identical output
  council-time --archive PATH
                            regenerate data/generated/council-time/ from an archive checkout and the
                            reviewed inputs in data/review/council-time/ (docs/COUNCIL_TIME.md)
  reproduce-council-time --archive PATH
                            regenerate council-time into a scratch directory; require identical bytes
  build                     render the static site into _site/
  check-links               check internal links in _site/
  paths FILE...             fail if any path is outside the agenda-intake allowlist
  candidates --archive PATH --start DATE --end DATE [--out DIR]
                            backfill Pass 2: write unconfirmed review bundles; fail on any quote that
                            is not on its cited pages
  import-decisions --bundle FILE --decisions FILE --archive PATH
                            turn review decisions on a candidate bundle into data/tracked/ records
  replay-check --archive PATH
                            the backfill acceptance fixture: July 30, 2024 Item 18 must link to
                            December 10, 2024 Item 22, with the deadline from Council's recorded action
"""
import argparse
import filecmp
import os
import sys
import tempfile

from . import candidates, council_time, decisions, generate, links, site, tracked, validate


def main(argv=None):
    p = argparse.ArgumentParser(prog="councilwatch")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--archive", required=True)
    g.add_argument("--out", default=generate.OUT_DIR)
    g.add_argument("--allow-dirty", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("--data", default=generate.OUT_DIR)
    v.add_argument("--tracked", default=tracked.TRACKED_DIR)
    r = sub.add_parser("reproduce")
    r.add_argument("--archive", required=True)
    r.add_argument("--data", default=generate.OUT_DIR)
    b = sub.add_parser("build")
    b.add_argument("--data", default=generate.OUT_DIR)
    b.add_argument("--out", default=site.SITE_DIR)
    b.add_argument("--tracked", default=tracked.TRACKED_DIR)
    sub.add_parser("check-links").add_argument("--site", default=site.SITE_DIR)
    sub.add_parser("paths").add_argument("files", nargs="*")
    c = sub.add_parser("candidates")
    c.add_argument("--archive", required=True)
    c.add_argument("--start", default="2021-01-19")
    c.add_argument("--end", required=True)
    c.add_argument("--out", default="_backfill")
    c.add_argument("--allow-dirty", action="store_true")
    sub.add_parser("replay-check").add_argument("--archive", required=True)
    ct = sub.add_parser("council-time")
    ct.add_argument("--archive", required=True)
    ct.add_argument("--allow-dirty", action="store_true")
    sub.add_parser("reproduce-council-time").add_argument("--archive", required=True)
    imp = sub.add_parser("import-decisions")
    imp.add_argument("--bundle", required=True)
    imp.add_argument("--decisions", required=True)
    imp.add_argument("--archive", required=True)
    imp.add_argument("--tracked", default=tracked.TRACKED_DIR)
    a = p.parse_args(argv)

    if a.cmd == "generate":
        d = generate.run(a.archive, a.out, a.allow_dirty)
        c = d["meta.json"]["counts"]
        print(f"{c['meetings']} meetings, {c['items']} items, {len(d['meta.json']['exceptions'])} exceptions "
              f"from archive {d['meta.json']['source']['archive_commit'][:12]}")
        return 0
    if a.cmd == "validate":
        errors = validate.validate(a.data)
        meeting_ids = {m["meeting_id"] for m in validate.load_dataset(a.data)["meetings.json"]}
        errors += tracked.validate(a.tracked, meeting_ids)
        errors += council_time.validate(meeting_ids=meeting_ids)
        for e in errors:
            print(e)
        print(f"{len(errors)} errors")
        return 1 if errors else 0
    if a.cmd == "reproduce":
        with tempfile.TemporaryDirectory() as tmp:
            generate.run(a.archive, tmp)
            names = ("meetings.json", "items.json", "meta.json")
            _, mismatch, missing = filecmp.cmpfiles(a.data, tmp, names, shallow=False)
            for n in mismatch + missing:
                print(f"{n}: differs from a fresh generation")
            print("reproducible" if not (mismatch or missing) else "not reproducible")
            return 1 if mismatch or missing else 0
    if a.cmd == "council-time":
        d = council_time.run(a.archive, allow_dirty=a.allow_dirty)
        c = d["meta.json"]["counts"]
        print(f"{c['transcripts']} transcripts ({c['transcripts_estimated']} estimated), {c['segments']} segments, "
              f"{c['correspondence_headings']} correspondence headings, {c['turns']} turns, "
              f"{len(d['meta.json']['exceptions'])} exceptions from archive {d['meta.json']['source']['archive_commit'][:12]}")
        return 1 if any(x["kind"] in council_time.BLOCKING for x in d["meta.json"]["exceptions"]) else 0
    if a.cmd == "reproduce-council-time":
        with tempfile.TemporaryDirectory() as tmp:
            council_time.run(a.archive, tmp)
            _, mismatch, missing = filecmp.cmpfiles(council_time.OUT_DIR, tmp, council_time.NAMES, shallow=False)
            for n in mismatch + missing:
                print(f"council-time/{n}: differs from a fresh generation")
            print("reproducible" if not (mismatch or missing) else "not reproducible")
            return 1 if mismatch or missing else 0
    if a.cmd == "build":
        files = site.build(a.data, a.out, a.tracked)
        print(f"built {len(files)} files into {a.out}")
        return 0
    if a.cmd == "check-links":
        n, problems = links.check(a.site)
        for x in problems:
            print(x)
        print(f"{n} pages, {len(problems)} broken links")
        return 1 if problems else 0
    if a.cmd == "candidates":
        cs, report = candidates.run(a.archive, a.start, a.end, allow_dirty=a.allow_dirty)
        problems = candidates.verify_all(a.archive, cs, a.allow_dirty)
        years = candidates.write_bundles(cs, report, a.out)
        print(f"{report['meetings_scanned']} meetings, {report['items_parsed']} items, candidates {report['candidates']}, "
              f"{report['linked_directions']} directions with proposed follow-ups, {len(report['exceptions'])} exceptions; "
              f"bundles for {', '.join(years) or 'no years'} in {a.out}")
        for x in problems:
            print(x)
        print(f"{len(problems)} quote check failures")
        return 1 if problems else 0
    if a.cmd == "import-decisions":
        try:
            added, undecided = decisions.run(a.bundle, a.decisions, a.archive, a.tracked)
        except decisions.DecisionError as x:
            print(x)
            print("nothing written")
            return 1
        errors = tracked.validate(a.tracked)
        for e in errors:
            print(e)
        print(f"{added} records added; {len(undecided)} candidates in the bundle have no decision yet; "
              f"{len(errors)} validation errors")
        return 1 if errors else 0
    if a.cmd == "replay-check":
        problems = candidates.replay_check(a.archive)
        for x in problems:
            print(x)
        print("replay fixture passes" if not problems else "replay fixture fails")
        return 1 if problems else 0
    if a.cmd == "paths":
        bad = validate.check_paths(a.files)
        for x in bad:
            print(f"outside the agenda-intake allowlist: {x}")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
