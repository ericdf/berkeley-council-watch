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
        self.assertEqual(len([r for r in d["recommendations.json"] if r["id"].startswith(f"{MATTER}-")]), 13)
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

    def test_unrecorded_management_response(self):
        # The Rocky Road audit report is not archived: its recommendations come from the City's status
        # reports, which do not print management's original responses.
        d = tracked.load(SEED)
        rr = [r for r in d["recommendations.json"] if r["id"].startswith("rocky-road-audit-2020-")]
        self.assertEqual(len(rr), 5)
        self.assertTrue(all(v is None for r in rr for v in r["management_response"].values()))
        out = os.path.join(self.tmp, "site")
        site.build(AGENDA, out, self.dir)
        with open(os.path.join(out, "matters", "rocky-road-audit-2020.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("not in the sources cited", page)
        self.assertNotIn("Completion verified", page)


    def test_unresolved_qualification(self):
        # A qualification may say what the record cannot establish and which record would resolve it.
        d = tracked.load(SEED)
        m = next(x for x in d["matters.json"] if x["id"] == "prop64-youth-cannabis-grant-2021")
        self.assertTrue(all(q.get("unresolved") for q in m["qualifications"]))
        out = os.path.join(self.tmp, "site")
        site.build(AGENDA, out, self.dir)
        with open(os.path.join(out, "matters", "prop64-youth-cannabis-grant-2021.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("<strong>Unresolved.</strong>", page)
        self.assertIn("No update located", page)
        self.assertNotIn("Completion verified", page)

    def test_unresolved_must_be_text(self):
        self.edit("matters.json", lambda d: d[0]["qualifications"][0].update(unresolved=""))
        self.assertError("shorter than 1")

    def test_reported_not_met_validates_and_renders(self):
        # A reporting party's statement that work was not done: like reported_complete, not verification.
        def fn(d):
            c = self.commitment(d, f"{MATTER}-cap-1.3")
            c["status_history"].append({"as_of": "2027-01-02", "status": "reported_not_met",
                                        "basis": "x", "citations": [dict(c["citation"])]})
        self.edit("commitments.json", fn)
        self.assertEqual(tracked.validate(self.dir), [])
        out = os.path.join(self.tmp, "site")
        site.build(AGENDA, out, self.dir)
        with open(os.path.join(out, "matters", f"{MATTER}.html"), encoding="utf-8") as f:
            self.assertIn("Reported not met", f.read())
        with open(os.path.join(out, "matters", "prop64-youth-cannabis-grant-2021.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("Measure of success, as stated:", page)

    def test_reported_not_met_needs_a_citation(self):
        def fn(d):
            c = self.commitment(d, f"{MATTER}-cap-1.3")
            c["status_history"].append({"as_of": "2027-01-02", "status": "reported_not_met",
                                        "basis": "x", "citations": []})
        self.edit("commitments.json", fn)
        self.assertError("reported_not_met needs a citation")


if __name__ == "__main__":
    unittest.main()
