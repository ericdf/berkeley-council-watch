import json
import os
import shutil

from councilwatch import candidates as C
from councilwatch import decisions as D
from councilwatch import tracked
from tests.test_candidates import LOOSE, Fixture

EMPTY = {name: [] for name in tracked.FILES}


class DecisionTests(Fixture):
    def setUp(self):
        super().setUp()
        cs, report = C.run(self.archive, "2024-07-30", "2024-12-31", rules=LOOSE)
        self.bundle_dir = os.path.join(self.tmp, "bundle")
        C.write_bundles(cs, report, self.bundle_dir)
        self.bundle = os.path.join(self.bundle_dir, "candidates-2024.json")
        self.tracked = os.path.join(self.tmp, "tracked")
        os.makedirs(self.tracked)
        for name in tracked.FILES:
            with open(os.path.join(self.tracked, name), "w") as f:
                f.write("[]\n")
        self.commit = report["archive_commit"]

    def decisions(self, items):
        path = os.path.join(self.tmp, "decisions-2024.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"year": "2024", "rules_version": 4, "archive_commit": self.commit,
                       "reviewed_on": "2026-10-28", "decisions": items}, f)
        return path

    CONFIRM = {
        "candidate_id": "city-council-2024-07-30--item-18", "decision": "confirm",
        "matter": {"id": "restaurant-inspections-audit-2024", "kind": "audit",
                   "title": "Restaurant Inspections audit", "description": "The audit and its report-back."},
        "commitment": {"label": "City Manager report back", "actor": "City Manager", "kind": "report_back"},
        "links": [{"to": "city-council-2024-12-10--item-22", "decision": "confirm", "status": "reported_complete",
                   "basis": "The status report was on the December 10, 2024 agenda."}],
    }

    def load(self, name):
        with open(os.path.join(self.tracked, name), encoding="utf-8") as f:
            return json.load(f)

    def test_confirm_with_link(self):
        added, undecided = D.run(self.bundle, self.decisions([self.CONFIRM]), self.archive, self.tracked)
        self.assertEqual(tracked.validate(self.tracked), [])
        (c,) = self.load("commitments.json")
        self.assertEqual(c["statement"], "M/S/C (Arreguin/Taplin) to approve the recommendation with a "
                                         "revision to schedule the report back for December 2024.")
        self.assertEqual(c["due"], {"as_stated": "December 2024", "is_date": True})
        self.assertEqual([h["status"] for h in c["status_history"]], ["not_yet_due", "reported_complete"])
        self.assertEqual(c["citation"]["locator"], "Item 18, Action (pp. 1–2)")
        self.assertEqual(len(self.load("events.json")), 2)
        self.assertEqual({s["archive_id"] for s in self.load("sources.json")},
                         {"bcc-2024-07-30-regular-annotated-agenda", "bcc-2024-12-10-regular-annotated-agenda"})
        self.assertIn("city-council-2024-12-10--item-22", undecided)

    def test_reimport_is_a_no_op(self):
        path = self.decisions([self.CONFIRM])
        D.run(self.bundle, path, self.archive, self.tracked)
        added, _ = D.run(self.bundle, path, self.archive, self.tracked)
        self.assertEqual(added, 0)

    def test_changed_reimport_is_refused(self):
        D.run(self.bundle, self.decisions([self.CONFIRM]), self.archive, self.tracked)
        changed = json.loads(json.dumps(self.CONFIRM))
        changed["commitment"]["actor"] = "City Attorney"
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([changed]), self.archive, self.tracked)

    def test_reject_needs_reason(self):
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([{"candidate_id": "city-council-2024-07-30--item-18",
                                                 "decision": "reject"}]), self.archive, self.tracked)
        added, _ = D.run(self.bundle, self.decisions([{"candidate_id": "city-council-2024-07-30--item-18",
                                                        "decision": "reject", "reason": "No checkable deliverable."}]),
                         self.archive, self.tracked)
        self.assertEqual(added, 0)

    def test_link_confirm_needs_status_and_basis(self):
        bad = json.loads(json.dumps(self.CONFIRM))
        del bad["links"][0]["basis"]
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([bad]), self.archive, self.tracked)
        self.assertEqual(self.load("commitments.json"), [])

    def test_verified_is_not_a_link_status(self):
        bad = json.loads(json.dumps(self.CONFIRM))
        bad["links"][0]["status"] = "completion_verified"
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([bad]), self.archive, self.tracked)

    def test_follow_up_report_cannot_be_a_commitment(self):
        bad = json.loads(json.dumps(self.CONFIRM))
        bad["candidate_id"] = "city-council-2024-12-10--item-22"
        bad.pop("links")
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([bad]), self.archive, self.tracked)

    def test_unknown_candidate(self):
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, self.decisions([{"candidate_id": "city-council-2024-07-30--item-99",
                                                 "decision": "reject", "reason": "x"}]), self.archive, self.tracked)

    def test_archive_commit_must_match(self):
        path = self.decisions([self.CONFIRM])
        with open(path) as f:
            d = json.load(f)
        d["archive_commit"] = "f" * 40
        with open(path, "w") as f:
            json.dump(d, f)
        with self.assertRaises(D.DecisionError):
            D.run(self.bundle, path, self.archive, self.tracked)
