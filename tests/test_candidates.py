import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from councilwatch import candidates as C

TOOLS = os.path.join(os.path.dirname(__file__), "fixtures", "archive", "tools")

# Layout as pdftotext -layout prints an annotated agenda: a page header, a ceremonial list that is not
# agenda items, a calendar heading, an item whose fields run across a page break, and Communications.
JULY = (
    "  Tuesday, July 30, 2024         ANNOTATED AGENDA                            Page 9\n"
    " Ceremonial Matters:\n"
    " 1.   Adjourned in Memory of a Resident\n"
    " City Manager Comments:\n"
    " The City Manager provided an update on the budget.\n"
    "Action Calendar – New Business\n"
    "\n"
    "18.    Berkeley Restaurant Inspections: Chronically Understaffed Program Did Not\n"
    "       Meet Targets\n"
    "       From: Auditor\n"
    "       Recommendation: We recommend City Council request that the City Manager\n"
    "       report back by January 2025 and at least annually thereafter, regarding the status of\n"
    "       our audit recommendations.\n"
    "       Contact: Jenny Wong, Auditor, (510) 981-6750\n"
    "       Action: 7 speakers. M/S/C (Arreguin/Taplin) to approve the recommendation with a\n"
    "\f"
    "  Tuesday, July 30, 2024         ANNOTATED AGENDA                            Page 10\n"
    "       revision to schedule the report back for December 2024.\n"
    "       Vote: All Ayes.\n"
    "\n"
    "19.    Contract: Street Paving\n"
    "       From: City Manager\n"
    "       Action: Adopted Resolution No. 1.\n"
    "\n"
    "Communications\n"
    "  Item #18: Berkeley Restaurant Inspections\n"
    "  1. A Resident\n"
    "\f"
)
DECEMBER = (
    "  Tuesday, December 10, 2024         ANNOTATED AGENDA                            Page 7\n"
    "Information Reports\n"
    "\n"
    "22.    Restaurant Inspection Audit Status Report\n"
    "       From: City Manager\n"
    "       Contact: Scott Gilman, Health, Housing, and Community Services, (510) 981-5400\n"
    "       Action: Moved to Action Calendar. 0 speakers. Discussion held.\n"
    "\n"
    "23.    Referral: Update the Paving Plan\n"
    "       From: Councilmember\n"
    "       Action: Approved.\n"
    "\f"
)
LOOSE = dict(C.load_rules())
LOOSE["link"] = dict(LOOSE["link"], min_link_score=0.5, max_term_share=1.0)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.archive = a = os.path.join(self.tmp, "archive")
        shutil.copytree(TOOLS, os.path.join(a, "tools"))
        base = "https://berkeleyca.gov/files/"
        entries = []
        for date in ("2024-07-30", "2024-12-10"):
            entries.append({"meeting": f"city-council-{date}", "name": f"City Council {date} - Regular", "date": date,
                            "label": "regular", "start_utc": None, "page_url": f"https://berkeleyca.gov/{date}",
                            "city": {"agenda_html": None, "agenda_packet": None,
                                     "annotated_agenda": f"{base}{date}-annotated.pdf", "video": None, "mp3": None, "mp4": None}})
        write(a, "catalog/city-council-agendas/meetings.json",
              json.dumps({"source": {"url": "https://berkeleyca.gov/agendas"}, "retrieved": "2026-10-28", "entries": entries}))
        write(a, "catalog/granicus/city-council.json", '{"entries": []}')
        for date, text, has_l1 in (("2024-07-30", JULY, True), ("2024-12-10", DECEMBER, False)):
            aa = f"bcc-{date}-regular-annotated-agenda"
            write(a, f"manifest/{aa}.json", json.dumps({
                "id": aa, "layer": "L0", "doc_type": "annotated_agenda", "body": "Berkeley City Council",
                "meeting_date": date, "meeting_label": "regular", "file": f"L0/annotated-agendas/{aa}.pdf",
                "sha256": "0" * 64, "source_url": f"{base}{date}-annotated.pdf"}))
            write(a, f"L0/annotated-agendas/{aa}.pdf", "not a real pdf\n")
            if has_l1:
                write(a, f"manifest/{aa}-text.json", json.dumps({
                    "id": f"{aa}-text", "layer": "L1", "doc_type": "annotated_agenda_text",
                    "file": f"L1/annotated-agendas/{aa}-text.txt", "sha256": "1" * 64,
                    "derived_from": {"id": aa, "sha256": "0" * 64}}))
                write(a, f"L1/annotated-agendas/{aa}-text.txt", text)
        git(a, "init", "-q")
        git(a, "add", "-A")
        git(a, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "fixture")
        # December has no archived L1, so the finder runs pdftotext on the PDF; stand in for it here.
        real = subprocess.run

        def fake(cmd, *args, **kw):
            if cmd[0] == "pdftotext" and cmd[1] == "-layout":
                return subprocess.CompletedProcess(cmd, 0, DECEMBER, "")
            if cmd[0] == "pdftotext" and cmd[1] == "-v":
                return subprocess.CompletedProcess(cmd, 0, "", "pdftotext version test")
            return real(cmd, *args, **kw)
        self.patch = mock.patch.object(C.subprocess, "run", side_effect=fake)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)


class ParseTests(unittest.TestCase):
    def test_items_fields_and_page_span(self):
        items = C.parse_items(JULY.split("\f")[:-1])
        self.assertEqual([i["number"] for i in items], ["18", "19"])
        it = items[0]
        self.assertEqual(it["title"], "Berkeley Restaurant Inspections: Chronically Understaffed Program Did Not Meet Targets")
        self.assertEqual(it["section"], "Action Calendar – New Business")
        self.assertEqual(it["pages"], [1, 2])
        self.assertEqual(it["fields"]["action"], "7 speakers. M/S/C (Arreguin/Taplin) to approve the recommendation "
                                                 "with a revision to schedule the report back for December 2024.")
        self.assertNotIn("ANNOTATED AGENDA", it["fields"]["action"])

    def test_ceremonial_list_and_communications_are_not_items(self):
        numbers = [i["number"] for i in C.parse_items(JULY.split("\f"))]
        self.assertNotIn("1", numbers)

    def test_deadline_from_action_wins(self):
        it = C.parse_items(JULY.split("\f"))[0]
        matches, deadlines = C.find_matches(it, C.load_rules())
        self.assertEqual({m["rule"] for m in matches}, {"report_back", "annual_follow_up"})
        self.assertEqual([(d["field"], d["text"], d["ends"]) for d in deadlines],
                         [("recommendation", "by January 2025", "2025-01-31"), ("action", "for December 2024", "2024-12-31")])

    def test_season_deadline(self):
        self.assertEqual(C.deadline_end("Fall", "2026").isoformat(), "2026-12-21")
        self.assertEqual(C.deadline_end("Winter", "2026").isoformat(), "2027-03-20")

    def test_follow_up_titles(self):
        rules = C.load_rules()
        self.assertTrue(C.is_follow_up_title("Restaurant Inspection Audit Status Report", rules))
        self.assertFalse(C.is_follow_up_title("Referral: Update the Paving Plan", rules))
        self.assertFalse(C.is_follow_up_title("Contract: Street Paving", rules))


class RunTests(Fixture):
    def test_replay_link(self):
        cs, report = C.run(self.archive, "2024-07-30", "2024-12-31", rules=LOOSE)
        d = next(c for c in cs if c["item"] == "18")
        self.assertEqual(d["kind"], "direction")
        self.assertEqual(d["effective_deadline"]["text"], "for December 2024")
        self.assertEqual(d["review_status"], "unconfirmed")
        self.assertEqual([(x["meeting_id"], x["item"]) for x in d["links"]], [("city-council-2024-12-10", "22")])
        self.assertEqual(report["text_basis"], {"archive_l1": 1, "pdftotext_at_run_time": 1})
        dec = next(c for c in cs if c["meeting_id"] == "city-council-2024-12-10" and c["item"] == "22")
        self.assertEqual(dec["source"]["text_basis"]["kind"], "pdftotext_at_run_time")

    def test_follow_up_found_outside_the_requested_range(self):
        cs, _ = C.run(self.archive, "2024-07-01", "2024-07-31", rules=LOOSE)
        self.assertEqual([c["meeting_id"] for c in cs], ["city-council-2024-07-30"])
        self.assertEqual(cs[0]["links"][0]["meeting_id"], "city-council-2024-12-10")

    def test_quotes_verify_and_a_changed_quote_fails(self):
        cs, _ = C.run(self.archive, "2024-07-30", "2024-12-31", rules=LOOSE)
        self.assertEqual(C.verify_all(self.archive, cs), [])
        cs[0]["matches"][0]["quote"] = "We recommend City Council request that the City Manager report back by March 2025."
        self.assertTrue(C.verify_all(self.archive, cs))

    def test_reproducible_bundles(self):
        out1, out2 = os.path.join(self.tmp, "b1"), os.path.join(self.tmp, "b2")
        for out in (out1, out2):
            cs, report = C.run(self.archive, "2024-07-30", "2024-12-31", rules=LOOSE)
            C.write_bundles(cs, report, out)
        for name in sorted(os.listdir(out1)):
            with open(os.path.join(out1, name), "rb") as f1, open(os.path.join(out2, name), "rb") as f2:
                self.assertEqual(f1.read(), f2.read(), name)
        with open(os.path.join(out1, "candidates-2024.md"), encoding="utf-8") as f:
            md = f.read()
        self.assertIn("Possible follow-up (unconfirmed)", md)

    def test_unarchived_agenda_is_an_exception(self):
        os.remove(os.path.join(self.archive, "manifest", "bcc-2024-12-10-regular-annotated-agenda.json"))
        git(self.archive, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-am", "drop")
        _, report = C.run(self.archive, "2024-07-30", "2024-12-31", rules=LOOSE)
        self.assertEqual([e["kind"] for e in report["exceptions"]], ["annotated_agenda_not_archived"])


if __name__ == "__main__":
    unittest.main()
