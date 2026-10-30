import json
import os
import shutil
import tempfile
import unittest

from councilwatch import generate, links, site, tracked, validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, tracked.TRACKED_DIR)
AGENDA = os.path.join(ROOT, generate.OUT_DIR)
MATTER = "contracts-audit-2026"


class TrackedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "tracked")
        shutil.copytree(SEED, self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit(self, name, fn):
        p = os.path.join(self.dir, name)
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        fn(d)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)

    def commitment(self, d, cid):
        return next(c for c in d if c["id"] == cid)

    def assertError(self, fragment):
        errors = tracked.validate(self.dir)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_seed_is_valid(self):
        meeting_ids = {m["meeting_id"] for m in validate.load_dataset(AGENDA)["meetings.json"]}
        self.assertEqual(tracked.validate(SEED, meeting_ids), [])

    def test_seed_shape(self):
        d = tracked.load(SEED)
        self.assertEqual(len(d["recommendations.json"]), 13)
        # Recommendation 1.2 has no commitment: management's response, date and plan are all to be determined.
        recs_with_commitments = {c["recommendation_id"] for c in d["commitments.json"]}
        self.assertNotIn(f"{MATTER}-rec-1.2", recs_with_commitments)
        statuses = {tracked.current_status(c)["status"] for c in d["commitments.json"]}
        self.assertNotIn("completion_verified", statuses)

    def test_verified_needs_independent_record(self):
        def fn(d):
            c = self.commitment(d, f"{MATTER}-cap-1.3")
            c["status_history"].append({"as_of": "2026-10-28", "status": "completion_verified",
                                        "basis": "x", "citations": [dict(c["citation"])]})
        self.edit("commitments.json", fn)
        self.assertError("completion_verified needs a citation to an independent record")

    def test_verified_with_auditor_follow_up_passes(self):
        def add_source(d):
            d.append({"id": "src-follow-up", "kind": "auditor_follow_up", "issuer": "City Auditor",
                      "title": "Follow-up", "document_date": "2027-01-01", "note": None,
                      "official_url": "https://berkeleyca.gov/follow-up.pdf", "archive_id": None,
                      "archive_url": None, "sha256": None, "retrieved": None})
        self.edit("sources.json", add_source)

        def fn(d):
            c = self.commitment(d, f"{MATTER}-cap-1.3")
            c["status_history"].append({"as_of": "2027-01-02", "status": "completion_verified", "basis": "x",
                                        "citations": [{"source_id": "src-follow-up", "locator": "p. 3"}]})
        self.edit("commitments.json", fn)
        self.assertEqual(tracked.validate(self.dir), [])

    def test_no_update_located_must_say_what_was_searched(self):
        self.edit("commitments.json",
                  lambda d: self.commitment(d, f"{MATTER}-cap-1.6")["status_history"][-1].pop("searched"))
        self.assertError("must say what was searched")

    def test_history_in_date_order(self):
        self.edit("commitments.json",
                  lambda d: self.commitment(d, f"{MATTER}-cap-1.6")["status_history"].reverse())
        self.assertError("not in date order")

    def test_not_yet_due_needs_a_date(self):
        self.edit("commitments.json",
                  lambda d: self.commitment(d, f"{MATTER}-cap-1.6")["due"].update(is_date=False))
        self.assertError("needs a stated due date")

    def test_unknown_source(self):
        self.edit("events.json", lambda d: d[0]["citations"][0].update(source_id="src-missing"))
        self.assertError("source 'src-missing' does not exist")

    def test_unknown_recommendation(self):
        self.edit("events.json", lambda d: d[-1]["recommendation_ids"].append(f"{MATTER}-rec-9.9"))
        self.assertError("does not exist")

    def test_broken_quote(self):
        self.edit("events.json", lambda d: d[1]["citations"][0].update(quote="City Con- tracts audit"))
        self.assertError("broken hyphen")

    def test_spaced_hyphen_is_not_a_broken_quote(self):
        self.edit("events.json", lambda d: d[1]["citations"][0].update(quote="Items Not Listed on the Agenda - 5 speakers."))
        self.assertEqual([e for e in tracked.validate(self.dir) if "broken hyphen" in e], [])

    def test_agenda_item_must_exist(self):
        errors = tracked.validate(self.dir, meeting_ids={"city-council-2026-10-27"})
        self.assertTrue(any("not in the agenda-intake data" in e for e in errors), errors)

    def test_matter_page(self):
        out = os.path.join(self.tmp, "site")
        site.build(AGENDA, out, self.dir)
        n, problems = links.check(out)
        self.assertEqual(problems, [])
        with open(os.path.join(out, "matters", f"{MATTER}.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("No update located", page)
        self.assertIn("Searched:", page)
        self.assertIn("We have not yet confirmed to what extent", page)
        self.assertIn('id="rec-2.7"', page)


if __name__ == "__main__":
    unittest.main()
