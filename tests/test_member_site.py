import unittest

from councilwatch import member_site as ms


class FakeAttention:
    record_thread = {}
    thread_info = {"other": {"label": "Other", "group": None}}


def item(rid, attribution=(), contact=None, added=(), motions=()):
    return {"record_id": rid, "meeting_id": "city-council-2026-01-20", "meeting_date": "2026-01-20", "item": rid[-1],
            "heading": "H", "contact": contact, "attribution": list(attribution), "added_cosponsors": list(added),
            "motions": list(motions)}


def att(member, role, order):
    return {"member": member, "as_printed": member, "role": role, "order": order}


MEMBERS = [{"member": "off-tregub", "name": "Igor Tregub", "office": "Councilmember", "district": 4},
           {"member": "off-taplin", "name": "Terry Taplin", "office": "Councilmember", "district": 2},
           {"member": "off-ishii", "name": "Adena Ishii", "office": "Mayor", "district": None}]


def build(items, cosponsors=(), motions=()):
    d = {"members.json": MEMBERS, "items.json": items, "attendance.json": [],
         "review": {"threads.json": {"items": []}, "cosponsors.json": {"additions": list(cosponsors)},
                    "motions.json": {"motions": list(motions)}}}
    return ms.Members(FakeAttention(), d)


class Bins(unittest.TestCase):
    def bins(self, M, member):
        return sorted(b for b, _ in M.roles[member])

    def test_sole_author_is_lead_and_cosponsor_listed(self):
        M = build([item("r1", [att("off-tregub", "author", 1), att("off-ishii", "co-sponsor", 2)])])
        self.assertEqual(self.bins(M, "off-tregub"), ["lead"])
        self.assertEqual(self.bins(M, "off-ishii"), ["listed"])

    def test_contact_names_the_lead_among_several_authors(self):
        M = build([item("r1", [att("off-tregub", "author", 1), att("off-taplin", "co-author", 2)],
                        contact="Igor Tregub, Councilmember, District 4")])
        self.assertEqual(self.bins(M, "off-tregub"), ["lead"])
        self.assertEqual(self.bins(M, "off-taplin"), ["joint"])

    def test_no_contact_means_joint_for_all(self):
        M = build([item("r1", [att("off-tregub", "author", 1), att("off-taplin", "author", 2)], contact="City Clerk")])
        self.assertEqual(self.bins(M, "off-tregub") + self.bins(M, "off-taplin"), ["joint", "joint"])

    def test_added_cosponsor_timing(self):
        added = [{"member": "off-taplin", "as_printed": "x"}, {"member": "off-ishii", "as_printed": "x"}]
        M = build([item("r1", [att("off-tregub", "author", 1)], added=added)],
                  cosponsors=[{"record_id": "r1", "member": "off-taplin", "finding": "at_meeting"},
                              {"record_id": "r1", "member": "off-ishii", "finding": "thanked_only"}])
        self.assertEqual(self.bins(M, "off-taplin"), ["at_meeting"])
        self.assertEqual(self.bins(M, "off-ishii"), ["later"])

    def test_vote_positions_and_divided(self):
        v = {"all_ayes": False, "ayes": ["off-tregub"], "noes": ["off-taplin"], "abstain": [], "absent": [], "recused": ["off-ishii"]}
        m = {"seq": 0, "kind": "competing", "disposition": "failed", "final": False, "movers": ["off-taplin", "off-ishii"], "vote": v}
        M = build([item("r1", motions=[m])], motions=[{"record_id": "r1", "seq": 0}])
        self.assertEqual([M.position(v, x) for x in ("off-tregub", "off-taplin", "off-ishii")], ["aye", "no", "recused"])
        self.assertEqual(M.position({"all_ayes": True, "ayes": [], "noes": [], "abstain": [], "absent": [], "recused": []}, "off-tregub"), "all_ayes")
        it, mo = M.divided()[0]
        self.assertEqual(M.kind(it, mo), "substitute")


if __name__ == "__main__":
    unittest.main()
