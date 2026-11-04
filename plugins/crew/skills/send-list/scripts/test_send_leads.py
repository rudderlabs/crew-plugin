"""Tests for send_leads.py's row preparation and payloads. Standard library only:

  python3 -I <this folder>/test_send_leads.py -v

Python -I keeps the current folder off the import path, so the test loads
send_leads.py by its own absolute path. The failure plan these come from: an account row keyed by
a domain written three ways, a person row sent in account mode, a free-mail
domain, a missing or duplicate domain, an id column, and the person mode these
changes must not move."""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("send_leads", os.path.join(HERE, "send_leads.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AccountMode(unittest.TestCase):
    def test_account_row_keys_by_domain(self):
        leads, problems = m.prepare([{"company_domain": "Acme.com", "company": "Acme", "segment": "consulting"}], 2, entity="account")
        self.assertEqual(problems, [])
        self.assertEqual(leads[0]["kind"], "account")
        self.assertEqual(leads[0]["user_id"], "account:acme.com")
        self.assertEqual(leads[0]["traits"], {"company": {"name": "Acme", "domain": "acme.com"}})
        self.assertEqual(leads[0]["props"]["segment"], "consulting")

    def test_account_domain_is_normalised(self):
        leads, problems = m.prepare([{"company_domain": "https://www.Acme.com/about"}], 2, entity="account")
        self.assertEqual(problems, [])
        self.assertEqual(leads[0]["user_id"], "account:acme.com")
        self.assertEqual(leads[0]["props"]["company_domain"], "acme.com")

    def test_account_row_with_a_person_is_refused(self):
        _, problems = m.prepare([{"company_domain": "acme.com", "linkedin_url": "https://www.linkedin.com/in/x"}], 2, entity="account")
        self.assertEqual(len(problems), 1)
        self.assertIn("person mode", problems[0][1])

    def test_account_free_mail_is_refused(self):
        _, problems = m.prepare([{"company_domain": "gmail.com"}], 2, entity="account")
        self.assertEqual(len(problems), 1)

    def test_account_without_domain_is_refused(self):
        _, problems = m.prepare([{"company": "Acme"}], 2, entity="account")
        self.assertIn("company_domain", problems[0][1])

    def test_account_duplicate_domain_is_refused(self):
        _, problems = m.prepare([{"company_domain": "acme.com"}, {"company_domain": "ACME.com"}], 2, entity="account")
        self.assertEqual(len(problems), 1)
        self.assertIn("row 2", problems[0][1])

    def test_account_id_column_wins(self):
        leads, _ = m.prepare([{"company_domain": "acme.com", "id": "crm-42"}], 2, entity="account")
        self.assertEqual(leads[0]["user_id"], "crm-42")

    def test_account_payloads_have_no_external_id(self):
        leads, _ = m.prepare([{"company_domain": "acme.com"}], 2, entity="account")
        identify, track = m.payloads(leads[0], "Partner Account Seeded", "linkedin_url", "shadow")
        self.assertNotIn("context", identify)
        self.assertEqual(track["event"], "Partner Account Seeded")
        self.assertEqual(track["userId"], "account:acme.com")
        self.assertTrue(identify["messageId"].endswith("-identify") and track["messageId"].endswith("-track"))
        self.assertEqual(identify["messageId"][:-9], track["messageId"][:-6])


class PersonModeUnchanged(unittest.TestCase):
    def test_person_mode_unchanged(self):
        leads, _ = m.prepare([{"name": "A B", "linkedin_url": "https://www.linkedin.com/in/ab"}], 2)
        self.assertEqual(leads[0]["kind"], "linkedin")
        identify, _ = m.payloads(leads[0], "E", "linkedin_url", "shadow")
        self.assertEqual(identify["context"]["externalId"][0]["id"], "https://www.linkedin.com/in/ab")


if __name__ == "__main__":
    unittest.main()
