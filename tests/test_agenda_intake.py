import json
import os
import shutil
import subprocess
import tempfile
import unittest

from councilwatch import generate, links, site, validate
from councilwatch.archive import Archive, ArchiveError

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "archive")


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.archive = os.path.join(self.tmp, "archive")
        shutil.copytree(FIXTURE, self.archive)
        git(self.archive, "init", "-q")
        git(self.archive, "add", "-A")
        git(self.archive, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "fixture")
        self.out = os.path.join(self.tmp, "data")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def gen(self):
        return generate.run(self.archive, self.out)

    def edit(self, rel, fn):
        p = os.path.join(self.archive, rel)
        with open(p) as f:
            d = json.load(f)
        fn(d)
        with open(p, "w") as f:
            json.dump(d, f, indent=1)
        git(self.archive, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-am", "edit")

    def rewrite(self, name, fn):
        p = os.path.join(self.out, name)
        with open(p) as f:
            d = json.load(f)
        fn(d)
        with open(p, "w") as f:
            f.write(generate.dump(d))


class GenerateTests(Base):
    def test_meetings_and_items(self):
        d = self.gen()
        meetings, items, meta = d["meetings.json"], d["items.json"], d["meta.json"]
        self.assertEqual([m["meeting_id"] for m in meetings],
                         ["city-council-2026-10-27", "city-council-2026-10-13", "city-council-2026-10-05"])
        self.assertEqual(meta["counts"]["items"], 3)
        self.assertEqual([i["agenda_item_number"] for i in items], ["1", "2", "10"])
        it = items[1]
        self.assertEqual(it["record_id"], "city-council-2026-10-27--item-2")
        self.assertEqual(it["status"], "source_archived")
        self.assertEqual(it["official_title"], "Contract amendment & <renewal>")
        self.assertEqual(it["archive_url"],
                         "https://archive.org/details/berkeley-public-records-bcc-2026-10-27-regular-agenda-packet")
        self.assertEqual(it["source_locator"]["pages"], [21, 24])
        self.assertEqual(it["source_archive_commit"], meta["source"]["archive_commit"])

    def test_archived_file_links_to_pinned_commit(self):
        d = self.gen()
        commit = d["meta.json"]["source"]["archive_commit"]
        ref = d["meetings.json"][1]["archived"]["annotated_agenda"][0]
        self.assertTrue(ref["archive_url"].startswith(
            f"https://github.com/ericdf/berkeley-public-records/blob/{commit}/L0/annotated-agendas/"))
        self.assertTrue(ref["listed_by_city"])
        self.assertEqual(d["meetings.json"][2]["archived"], {})

    def test_reproducible(self):
        def snapshot():
            out = {}
            for n in sorted(os.listdir(self.out)):
                with open(os.path.join(self.out, n), "rb") as f:
                    out[n] = f.read()
            return out
        self.gen()
        first = snapshot()
        self.gen()
        self.assertEqual(first, snapshot())

    def test_duplicate_item_numbers_become_an_exception(self):
        self.edit("L2/agenda-packets/bcc-2026-10-27-regular-agenda-packet-items.json",
                  lambda d: d["items"][1].update(item="1"))
        d = self.gen()
        self.assertEqual([i["agenda_item_number"] for i in d["items.json"]], ["10"])
        self.assertEqual(d["meta.json"]["exceptions"][0]["kind"], "duplicate_item_numbers")
        self.assertEqual(validate.validate(self.out), [])

    def add_second_index(self, packet):
        src = os.path.join(self.archive, "manifest", "bcc-2026-10-27-regular-agenda-packet-items.json")
        with open(src) as f:
            e = json.load(f)
        e["id"] = "bcc-2026-10-27-regular-agenda-packet-revised-items"
        e["file"] = "L2/agenda-packets/bcc-2026-10-27-regular-agenda-packet-revised-items.json"
        with open(os.path.join(self.archive, "manifest", e["id"] + ".json"), "w") as f:
            json.dump(e, f, indent=1)
        with open(os.path.join(self.archive, "L2/agenda-packets/bcc-2026-10-27-regular-agenda-packet-items.json")) as f:
            idx = json.load(f)
        idx.update(id=e["id"], packet=packet)
        with open(os.path.join(self.archive, e["file"]), "w") as f:
            json.dump(idx, f, indent=1)
        git(self.archive, "add", "-A")
        git(self.archive, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "second index")

    def test_two_indexes_pick_the_city_listed_packet(self):
        self.add_second_index("bcc-2026-10-27-regular-agenda-packet-revised")
        d = self.gen()
        self.assertEqual(d["meta.json"]["exceptions"], [])
        self.assertEqual({i["source_locator"]["index_archive_id"] for i in d["items.json"]},
                         {"bcc-2026-10-27-regular-agenda-packet-items"})

    def test_two_indexes_for_the_same_packet_are_ambiguous(self):
        self.add_second_index("bcc-2026-10-27-regular-agenda-packet")
        d = self.gen()
        self.assertEqual(d["items.json"], [])
        self.assertEqual(d["meta.json"]["exceptions"][0]["kind"], "ambiguous_packet_index")
        self.assertEqual(validate.validate(self.out), [])

    def test_dirty_archive_refused(self):
        with open(os.path.join(self.archive, "manifest", "stray.json"), "w") as f:
            f.write("{}")
        with self.assertRaises(ArchiveError):
            Archive(self.archive)

    def test_not_an_archive(self):
        with self.assertRaises(ArchiveError):
            Archive(self.tmp)


class ValidateTests(Base):
    def setUp(self):
        super().setUp()
        self.gen()

    def assertError(self, fragment):
        errors = validate.validate(self.out)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_generated_data_is_valid(self):
        self.assertEqual(validate.validate(self.out), [])

    def test_outcome_status_without_action_source(self):
        self.rewrite("items.json", lambda d: d[0].update(status="action_recorded"))
        self.assertError("needs an authoritative action source")

    def test_unknown_status(self):
        self.rewrite("items.json", lambda d: d[0].update(status="adopted"))
        self.assertError("is not one of")

    def test_duplicate_record_id(self):
        self.rewrite("items.json", lambda d: d[1].update(record_id=d[0]["record_id"]))
        self.assertError("duplicate record_id")

    def test_unexpected_field(self):
        self.rewrite("items.json", lambda d: d[0].update(summary="The Council approved this."))
        self.assertError("unexpected field summary")

    def test_forbidden_text(self):
        self.rewrite("items.json", lambda d: d[0].update(official_title="/Users/someone/notes"))
        self.assertError("forbidden text")

    def test_item_count_must_match(self):
        self.rewrite("meetings.json", lambda d: d[0].update(item_count=99))
        self.assertError("item_count 99")

    def test_missing_city_source(self):
        self.rewrite("items.json", lambda d: d[0].pop("city_source_url"))
        self.assertError("missing city_source_url")

    def test_paths_allowlist(self):
        self.assertEqual(validate.check_paths(["data/generated/agenda-intake/items.json"]), [])
        self.assertEqual(validate.check_paths(["councilwatch/site.py", ".github/workflows/x.yml"]),
                         ["councilwatch/site.py", ".github/workflows/x.yml"])


class SiteTests(Base):
    def test_build_and_links(self):
        self.gen()
        out = os.path.join(self.tmp, "site")
        site.build(self.out, out)
        n, problems = links.check(out)
        self.assertEqual(problems, [])
        self.assertEqual(n, 3 + 4)  # three meeting pages, home, about, meetings index, data index
        with open(os.path.join(out, "meetings", "city-council-2026-10-27.html")) as f:
            page = f.read()
        self.assertIn("Contract amendment &amp; &lt;renewal&gt;", page)
        self.assertIn("pp. 21–24", page)
        self.assertIn("licensed under <a href=\"https://creativecommons.org/licenses/by/4.0/\">CC BY 4.0</a>", page)
        self.assertNotIn('href="/', page)

    def test_root_relative_link_is_reported(self):
        out = os.path.join(self.tmp, "site")
        os.makedirs(out)
        with open(os.path.join(out, "index.html"), "w") as f:
            f.write('<a href="/meetings/index.html">x</a><a href="missing.html">y</a>')
        _, problems = links.check(out)
        self.assertEqual(len(problems), 2)


if __name__ == "__main__":
    unittest.main()
