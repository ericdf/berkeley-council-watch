import unittest

from councilwatch import consent_money as cm


def c(rid, heading, amount=1000.0, aao=None):
    return {"record_id": rid, "heading": heading, "amount": amount, "aao": aao, "meeting_date": "2026-01-01",
            "meeting_id": "m", "item": "1", "from": "City Manager"}


class ConsentMoneyTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(cm.rule_kind("Contract: Acme for Paving"), "contracts")
        self.assertEqual(cm.rule_kind("Grant Application: Safe Routes to Transit"), "applications")
        self.assertEqual(cm.rule_kind("Revenue Grant Agreements: Funding Support from the State"), "incoming")
        self.assertEqual(cm.rule_kind("Resolution in Support of Prop 1, The Veterans and Affordable Housing Bond Act"),
                         "not_spending")
        self.assertEqual(cm.rule_kind("Formal Bid Solicitations and Request for Proposals Scheduled"), "planned")
        self.assertEqual(cm.rule_kind("Temporary Appropriations FY 2027"), "temporary")
        self.assertEqual(cm.rule_kind("Budget Referral: Playground"), "referrals")

    def test_review_repeat_and_relinquishments(self):
        consent = [c("a", "Contract: Acme"), c("b", "Loan Modification Requests"), c("r", "Relinquishment of Council Office Budget Funds"),
                   c("z", "Something unusual", amount=None)]
        items = [{"record_id": "b", "action": "Action: See action for Item 26b."}]
        rows = cm.classify(consent, items, {"a": {"kind": "grants_out"}})
        self.assertEqual([(k, x["record_id"], how) for k, x, how in rows],
                         [("grants_out", "a", "reviewed"), ("repeat", "b", "rule")])


if __name__ == "__main__":
    unittest.main()
