import json
import os
import shutil
import subprocess
import tempfile
import unittest

from councilwatch import council_time as ct

VTT = """This information provided by Zoom. The City of Berkeley cannot certify the
following text since we did not create it.

WEBVTT

1
00:00:00.000 --> 00:00:05.000
Boardroom: Calling the meeting to order.

2
00:10:00.000 --> 00:10:05.000
Boardroom: Moving on to item number 18, and 19 with it.

3
00:20:00.000 --> 00:20:05.000
Jane Doe: Free Palestine, and please fix the streets.

4
00:30:00.000 --> 00:30:05.000
Boardroom: We are adjourned.
"""
CART = "\n".join(["ONE TWO THREE FOUR"] * 3 + ["FIVE SIX SEVEN EIGHT"] * 1) + "\n"   # 16 words over 4 lines
CATALOG = {"source": {"url": "https://berkeleyca.gov/x", "listing_sha256": "0" * 64}, "retrieved": "2026-10-28",
           "entries": [{"meeting": "city-council-2026-10-13", "date": "2026-10-13", "label": "regular"},
                       {"meeting": "city-council-2025-03-11", "date": "2025-03-11", "label": "regular"}]}
MAP = {"meetings": [{"meeting": "city-council-2026-10-13", "archived": {"annotated_agenda": ["bcc-2026-10-13-regular-annotated-agenda"]},
                     "listed": {"annotated_agenda": "bcc-2026-10-13-regular-annotated-agenda"}}], "unmatched": []}
P = lambda m: {"member": m, "as_printed": m[4:].title()}
RECORD = {"annotated_agenda": "bcc-2026-10-13-regular-annotated-agenda", "text": "r-text",
  "attendance": {"roll_call_time": "6:05 p.m.", "present": [P("off-taplin")], "absent": [P("off-tregub")],
                 "arrived_late": [dict(P("off-tregub"), time="6:30 p.m.")]},
  "items": [
    {"item": "18", "section": "Action Calendar", "heading": "Street Paving", "from": "Councilmember Taplin (Author)",
     "contact": "Terry Taplin, Councilmember", "speakers": 4, "lines": [10, 20],
     "attribution": [dict(P("off-taplin"), role="author", order=1)], "added_cosponsors": [P("off-tregub")],
     "motions": [{"seq": 0, "final": True, "kind": "main", "disposition": "carried", "severed": False, "vote_label": "vote",
                  "movers": [P("off-taplin"), P("off-tregub")], "vote": {
         "all_ayes": False, "ayes": [P("off-taplin")] * 7, "noes": [P("off-tregub")] * 2, "abstain": [], "absent": [], "recused": []}}]},
    {"item": "3", "section": "Consent Calendar", "heading": "Amendment: FY 2026 Annual Appropriations Ordinance", "from": "City Manager",
     "contact": None, "speakers": None, "lines": [1, 2], "attribution": [], "added_cosponsors": [], "motions": [],
     "financial_implications": "See report",
     "action": "Adopted first reading of Ordinance No. 8,010–N.S. Second reading scheduled for June 9, 2026."},
    {"item": "4", "section": "Consent Calendar", "heading": "Relinquishment of Council Office Budget Funds", "from": "Councilmember Taplin",
     "contact": None, "speakers": None, "lines": [3, 3], "attribution": [], "added_cosponsors": [], "motions": [], "action": "Adopted."}],
  "communications": [
    {"section": "Communications", "heading": "Item #18: Street Paving", "line": 40, "items": ["18"], "entries": [
        {"as_printed": "Jane Doe", "count": 1, "count_basis": "one entry"},
        {"as_printed": "37 similarly worded form letters", "count": 37, "count_basis": "similarly worded or form letters"},
        {"as_printed": "Submitted by Councilmember Tregub", "count": 1, "count_basis": "one entry"}]},
    {"section": "Communications", "heading": "Middle East", "line": 50, "items": [], "entries": [
        {"as_printed": "John Roe (3)", "count": 3, "count_basis": "parenthesized number"}]}]}


def seg(meeting, kind, item, ev, **span):
    return {"meeting": meeting, "kind": kind, "item": item, "public_comment": span.pop("pc", None),
            "evidence_start": ev, "level": "inferred", **span}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        a = self.archive = os.path.join(self.tmp, "archive")
        files = {
            "catalog/city-council-agendas/meetings.json": json.dumps(CATALOG),
            "registry/speakers.json": json.dumps({"officeholders": [{"id": "off-taplin", "name": "Terry Taplin", "office": "Councilmember", "district": 2},
                                                                   {"id": "off-tregub", "name": "Igor Tregub", "office": "Councilmember", "district": 4}]}),
            "tools/meeting_map.py": "import json, sys\nprint(json.dumps(%s))\n" % json.dumps(MAP),
            "L1/council-captions/v.txt": VTT, "L1/council-captions/c.txt": CART,
            "L1/annotated-agendas/r.txt": ("3. Amendment: FY 2026 Annual Appropriations Ordinance\nRecommendation: Adopt the first reading of an "
                                          "Ordinance amending the FY 2026 AAO in the amount of $17,362,804 (gross appropriations) and "
                                          "$16,419,776 (net appropriations).\n4. Relinquishment\n"),
            "L2/annotated-agendas/r.json": json.dumps(RECORD),
            "L3/council-captions/v-structure.json": json.dumps({"transcript_id": "v-text", "segments": [
                seg("2026-10-13 regular", "opening", None, "Calling", start="00:00:00", end="00:10:00"),
                seg("2026-10-13 regular", "item", "18/19", "Moving on", start="00:10:00", end="00:30:00",
                    pc=[{"start": "00:20:00", "end": "00:25:00"}]),
                seg("2026-10-13 regular", "closing", None, "adjourned", start="00:30:00", end="00:30:05")]}),
            "L3/council-captions/c-structure.json": json.dumps({"transcript_id": "c-text", "segments": [
                seg("2025-03-11 regular", "item", "22-24", "ONE", start_line=1, end_line=3),
                seg("2025-03-11 jpfa", "item", "1", "FIVE", start_line=4, end_line=4)]}),
        }
        entries = [
            {"id": "v-text", "layer": "L1", "file": "L1/council-captions/v.txt", "meeting_date": "2026-10-13"},
            {"id": "c-text", "layer": "L1", "file": "L1/council-captions/c.txt", "meeting_date": "2025-03-11"},
            {"id": "v-structure", "layer": "L3", "doc_type": "council_captions_structure", "file": "L3/council-captions/v-structure.json"},
            {"id": "c-structure", "layer": "L3", "doc_type": "council_captions_structure", "file": "L3/council-captions/c-structure.json"},
            {"id": "r-record", "layer": "L2", "doc_type": "annotated_agenda_record", "file": "L2/annotated-agendas/r.json"},
            {"id": "r-text", "layer": "L1", "file": "L1/annotated-agendas/r.txt"},
            {"id": "bcc-2026-10-13-regular-annotated-agenda", "layer": "L0", "meeting_date": "2026-10-13", "file": "x.pdf"},
        ]
        for e in entries:
            files[f"manifest/{e['id']}.json"] = json.dumps(e)
        for rel, body in files.items():
            os.makedirs(os.path.dirname(os.path.join(a, rel)), exist_ok=True)
            with open(os.path.join(a, rel), "w") as f:
                f.write(body)
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-C", a, *args], check=True, capture_output=True)
        self.review = os.path.join(self.tmp, "review")
        os.makedirs(self.review)
        self.write_review(
            threads={"threads": [{"id": "streets", "label": "Streets", "group": None}, {"id": "gaza", "label": "Gaza", "group": None},
                                 {"id": "routine", "label": "Routine business", "group": None}],
                     "segments": [{"segment": "v-structure#0", "thread": "routine", "auditor": False},
                                  {"segment": "v-structure#1", "thread": "streets", "auditor": False},
                                  {"segment": "v-structure#2", "thread": "routine", "auditor": False},
                                  {"segment": "c-structure#0", "thread": "streets", "auditor": False},
                                  {"segment": "c-structure#1", "thread": "routine", "auditor": False}],
                     "correspondence_headings": [{"heading": "Middle East", "thread": "gaza"}]},
            clock={"transcripts": {"c-text": {"called_to_order": "6:00 p.m.", "called_to_order_basis": "roll call",
                                              "adjourned": "8:10 p.m.", "adjourned_basis": "adjourned",
                                              "recess_minutes": 10, "recess_basis": ["7:00 p.m. - 7:10 p.m."]}}},
            turns={"turns": [{"transcript": "v-text", "start": "00:20:00", "end": "00:21:00", "thread": "gaza",
                              "quote": "Free Palestine", "within": "item 18", "extent": "partial"}]},
            links={"links": [{"n": 1, "d": "2026-10-13", "from": "streets", "to": "gaza", "label": "x", "evidence": "y"}]})
        self.out = os.path.join(self.tmp, "out")

    def write_review(self, **docs):
        for name, doc in docs.items():
            with open(os.path.join(self.review, name + ".json"), "w") as f:
                json.dump(doc, f)

    def gen(self):
        return ct.run(self.archive, self.out, self.review)

    def read_out(self):
        out = {}
        for n in ct.NAMES:
            with open(os.path.join(self.out, n), "rb") as f:
                out[n] = f.read()
        return out


class Generate(Base):
    def test_timestamped_minutes(self):
        s = {x["segment_id"]: x for x in self.gen()["segments.json"]}
        it = s["v-structure#1"]
        self.assertEqual((it["minutes"], it["public_comment_minutes"], it["estimated"]), (20.0, 5.0, False))
        self.assertEqual(it["record_ids"], ["city-council-2026-10-13--item-18", "city-council-2026-10-13--item-19"])
        self.assertEqual(it["meeting_id"], "city-council-2026-10-13")

    def test_court_reporter_estimate(self):
        s = {x["segment_id"]: x for x in self.gen()["segments.json"]}
        # 12 of 16 words, of a meeting of 130 minutes less a 10-minute recess
        self.assertEqual((s["c-structure#0"]["minutes"], s["c-structure#0"]["estimated"]), (90.0, True))
        self.assertEqual(s["c-structure#0"]["record_ids"], ["city-council-2025-03-11--item-22", "city-council-2025-03-11--item-23",
                                                            "city-council-2025-03-11--item-24"])
        self.assertIsNone(s["c-structure#1"]["meeting_id"])     # a JPFA meeting is not in the Council's listing
        self.assertEqual(s["c-structure#1"]["record_ids"], [])

    def test_correspondence_counts(self):
        c = self.gen()["correspondence.json"]
        first = next(x for x in c if x["heading"].startswith("Item #18"))
        self.assertEqual((first["letters_public"], first["form_letters"], first["letters_official"]), (38, 37, 1))
        self.assertEqual(first["record_ids"], ["city-council-2026-10-13--item-18"])

    def test_agenda_items_and_final_vote(self):
        it = next(x for x in self.gen()["items.json"] if x["item"] == "18")
        self.assertEqual(it["record_id"], "city-council-2026-10-13--item-18")
        self.assertEqual(it["final_motion"]["vote"], {"all_ayes": False, "ayes": 7, "noes": 2, "abstain": 0, "absent": 0, "recused": 0})
        self.assertEqual(it["attribution"][0]["member"], "off-taplin")
        self.assertEqual(it["motions"][0]["movers"], ["off-taplin", "off-tregub"])
        d = self.gen()
        self.assertEqual(d["attendance.json"][0]["arrived_late"], [{"member": "off-tregub", "time": "6:30 p.m."}])
        self.assertEqual([m["member"] for m in d["members.json"]], ["off-taplin", "off-tregub"])

    def test_consent_aao_amendment_counts_net_at_first_reading(self):
        c = self.gen()["consent.json"]
        self.assertEqual([x["item"] for x in c], ["3"])          # the relinquishment is routine
        x = c[0]
        self.assertEqual((x["aao"]["kind"], x["aao"]["reading"], x["aao"]["ordinance"]), ("amendment", "first", "8,010-N.S."))
        self.assertEqual((x["amount"], x["amount_source"], x["policy_bearing"]), (16419776.0, "net appropriation", True))

    def test_aao_second_reading_has_no_amount(self):
        it = {"heading": "Amendment: FY 2026 Annual Appropriations Ordinance", "recommendation": "Adopt second reading of Ordinance No. 8,010-N.S.",
              "action": "Adopted second reading of Ordinance No. 8,010–N.S.", "section": "Consent Calendar", "attribution": [], "from": "City Manager",
              "speakers": None, "financial_implications": None, "record_id": "x", "meeting_id": "m", "meeting_date": "2026-06-09", "item": "2"}
        x = ct.consent_records([it], [])[0]
        self.assertEqual((x["amount"], x["policy_bearing"]), (None, False))
        self.assertIn("counted at its first reading", x["reasons"][0])

    def test_turn_minutes_and_quote(self):
        d = self.gen()
        self.assertEqual(d["turns.json"][0]["minutes"], 1.0)
        self.assertEqual(d["meta.json"]["exceptions"], [])

    def test_blocking_exceptions(self):
        self.write_review(clock={"transcripts": {}},
                          turns={"turns": [{"transcript": "v-text", "start": "00:20:00", "end": "00:21:00", "thread": "gaza",
                                            "quote": "Free Tibet", "within": None, "extent": "whole"}]})
        kinds = sorted(x["kind"] for x in self.gen()["meta.json"]["exceptions"])
        self.assertEqual(kinds, ["no_meeting_clock", "turn_quote_not_found"])
        errors = ct.validate(self.out, self.review)
        self.assertTrue(any("unresolved exception" in e for e in errors))

    def test_unclassified_segment(self):
        with open(os.path.join(self.review, "threads.json")) as f:
            t = json.load(f)
        t["segments"] = t["segments"][1:]
        self.write_review(threads=t)
        self.assertIn({"kind": "unclassified_segment", "segment_id": "v-structure#0"}, self.gen()["meta.json"]["exceptions"])

    def test_validates_and_reproduces(self):
        self.gen()
        self.assertEqual(ct.validate(self.out, self.review), [])
        first = self.read_out()
        self.gen()
        self.assertEqual(first, self.read_out())

    def test_review_errors(self):
        self.gen()
        self.write_review(links={"links": [{"n": 1, "d": "2026-10-13", "from": "streets", "to": "nowhere", "label": "x", "evidence": "y"}]})
        self.assertTrue(any("unknown thread nowhere" in e for e in ct.validate(self.out, self.review)))


class Items(unittest.TestCase):
    def test_expand(self):
        self.assertEqual(ct.expand_items("18/19/20"), ["18", "19", "20"])
        self.assertEqual(ct.expand_items("1a-1d"), ["1a", "1b", "1c", "1d"])
        self.assertEqual(ct.expand_items("43a-c"), ["43a", "43b", "43c"])
        self.assertEqual(ct.expand_items("24, 28, 29"), ["24", "28", "29"])
        self.assertEqual(ct.expand_items("11a+11b"), ["11a", "11b"])
        self.assertEqual(ct.expand_items("Urgent"), [])
        self.assertEqual(ct.expand_items(None), [])

    def test_clock(self):
        self.assertEqual(ct.clock_minutes("12:27 a.m.") - ct.clock_minutes("7:06 p.m."), 321)
        with self.assertRaises(ValueError):
            ct.clock_minutes("7:06 pm")


class CommittedData(unittest.TestCase):
    def test_committed_council_time_validates(self):
        self.assertEqual(ct.validate(), [])


if __name__ == "__main__":
    unittest.main()
