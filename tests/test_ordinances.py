import unittest

from councilwatch import ordinance_site as o


def item(date, action, heading="An ordinance", frm="City Manager", section="Consent Calendar"):
    return {"meeting_date": date, "action": action, "heading": heading, "from": frm, "section": section,
            "record_id": f"r-{date}", "meeting_id": f"m-{date}", "item": "1", "final_motion": None}


class OrdinanceTests(unittest.TestCase):
    def test_readings_join_by_number(self):
        ords = o.collect([
            item("2026-10-13", "Action: M/S/C (A/B) to adopt first reading of Ordinance No. 8,035–N.S."),
            item("2026-10-27", "Action: Adopted second reading of Ordinance No. 8,035–N.S."),
        ])
        self.assertEqual(set(ords["8035"]), {"first", "second"})
        self.assertEqual(ords["8035"]["first"]["meeting_date"], "2026-10-13")

    def test_one_step_adoption_and_several_numbers(self):
        r = o.readings(item("2024-12-10", "Action: Adopted: 1. Resolution No. 71,609–N.S. 2. Adopted Ordinance No. "
                                          "7,946-N.S. (Measure W), Ordinance No. 7,947-N.S. (Measure X)"))
        self.assertEqual(r, [("7946", "adopted"), ("7947", "adopted")])

    def test_origin(self):
        self.assertEqual(o.origin(item("d", "", frm="Councilmember Kesarwani (Author)")), "member")
        self.assertEqual(o.origin(item("d", "", heading="Confirming the Results of the November 5, 2024, Election")),
                         "voters")
        self.assertEqual(o.origin(item("d", "", frm="Housing Advisory Commission")), "commission")


if __name__ == "__main__":
    unittest.main()
