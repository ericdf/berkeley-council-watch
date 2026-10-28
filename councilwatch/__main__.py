"""Command line: python3 -m councilwatch <command>

  generate --archive PATH   regenerate data/generated/agenda-intake/ from an archive checkout
  validate                  check the generated dataset (schemas, ids, status rules, forbidden text)
  reproduce --archive PATH  regenerate into a scratch directory and require byte-identical output
  build                     render the static site into _site/
  check-links               check internal links in _site/
  paths FILE...             fail if any path is outside the agenda-intake allowlist
"""
import argparse
import filecmp
import os
import sys
import tempfile

from . import generate, links, site, validate


def main(argv=None):
    p = argparse.ArgumentParser(prog="councilwatch")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--archive", required=True)
    g.add_argument("--out", default=generate.OUT_DIR)
    g.add_argument("--allow-dirty", action="store_true")
    sub.add_parser("validate").add_argument("--data", default=generate.OUT_DIR)
    r = sub.add_parser("reproduce")
    r.add_argument("--archive", required=True)
    r.add_argument("--data", default=generate.OUT_DIR)
    b = sub.add_parser("build")
    b.add_argument("--data", default=generate.OUT_DIR)
    b.add_argument("--out", default=site.SITE_DIR)
    sub.add_parser("check-links").add_argument("--site", default=site.SITE_DIR)
    sub.add_parser("paths").add_argument("files", nargs="*")
    a = p.parse_args(argv)

    if a.cmd == "generate":
        d = generate.run(a.archive, a.out, a.allow_dirty)
        c = d["meta.json"]["counts"]
        print(f"{c['meetings']} meetings, {c['items']} items, {len(d['meta.json']['exceptions'])} exceptions "
              f"from archive {d['meta.json']['source']['archive_commit'][:12]}")
        return 0
    if a.cmd == "validate":
        errors = validate.validate(a.data)
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
    if a.cmd == "build":
        files = site.build(a.data, a.out)
        print(f"built {len(files)} files into {a.out}")
        return 0
    if a.cmd == "check-links":
        n, problems = links.check(a.site)
        for x in problems:
            print(x)
        print(f"{n} pages, {len(problems)} broken links")
        return 1 if problems else 0
    if a.cmd == "paths":
        bad = validate.check_paths(a.files)
        for x in bad:
            print(f"outside the agenda-intake allowlist: {x}")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
