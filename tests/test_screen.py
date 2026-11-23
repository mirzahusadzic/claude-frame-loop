"""What is sent: each kind of secret is found, what only looks like one is not, a stretch that holds one is cut whole
and the rest of the change kept, and a change with one left is refused. The cases are the old tree's (36cdba3,
tests/testprivacy.py); each key is built from pieces, so this file holds none whole."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import random
import string
import unittest

from frameloop import screen, words

BODY = "a1B2c3D4e5F6g7H8i9J0" + "k1L2m3N4o5P6q7R8s9T0"
KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


class KindTests(unittest.TestCase):
    def test_each_is_found_as_a_secret(self):
        for line, kind in (
            ("key = '" + "sk-" + "ant-" + BODY + "'", "api-key"),
            ("id = '" + KEY + "'", "aws-key"),
            ("key = '" + "AI" + "za" + BODY[:35] + "'", "google-key"),
            ("stripe = '" + "sk_" + "live_" + BODY[:24] + "'", "stripe-key"),
            ("stripe = '" + "rk_" + "live_" + BODY[:24] + "'", "stripe-key"),
            ("jwt = '" + "ey" + "J" + BODY[:20] + "." + "ey" + "J" + BODY[:20] + "." + BODY[:20] + "'", "web-token"),
            ("token = '" + "gh" + "p_" + BODY[:36] + "'", "github-token"),
            ("token = '" + "xo" + "xb-" + BODY[:20] + "'", "slack-token"),
            ("-----BEGIN " + "RSA PRIVATE KEY-----", "private-key"),
            ("-----BEGIN " + "PGP PRIVATE KEY BLOCK-----", "private-key"),
            ("API" + "_KEY=" + BODY[:36], "assigned-key"),
            ("export STRIPE" + "_KEY='" + BODY[:40] + "'", "assigned-key"),
            ("api" + 'Key = "' + BODY[:36] + '"', "assigned-key"),
            ('"api' + 'Key": "' + BODY[:36] + '"', "assigned-key"),
            ("heroku_api" + "_key=4f3a9b2c-1d7e-4a8b-9c3d-" + "2e1f0a9b8c7d", "assigned-key"),
            ("public string Client" + 'Key = "' + BODY[:36] + '";', "assigned-key"),
        ):
            with self.subTest(kind=kind, line=line[:24]):
                self.assertEqual(screen.secret_in(line), kind)
                self.assertIn(kind, words.SECRETS)

    def test_the_other_half_of_an_aws_credential_is_a_secret(self):
        for line in (
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            'AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
            '"SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
            "aws-secret-access-key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ):
            self.assertEqual(screen.secret_in(line), "aws-secret")
        self.assertEqual(screen.secret_in('"SessionToken": "' + "A" * 200 + '"'), "aws-session")
        self.assertIsNone(screen.secret_in("session_token = get_token()"))

    def test_what_only_looks_like_one_is_not(self):
        for line in (
            "SORT_KEY = lambda row: row.name",
            "CACHE_KEY=settings.cache_key_for_this_request_please",
            "key = os.environ['API_KEY']",
            "skip = 'sk_live_'",
            "header = 'eyJhbGciOi'",
            'primary_key = "orders_2024_partition_by_customer_id"',
            'sortKey = "ordersPartitionByCustomerId2024v"',
            'PartitionKey = "OrdersByCustomerIdAndRegion2024"',
            "monkey = '" + BODY + "'",
        ):
            with self.subTest(line=line):
                self.assertIsNone(screen.secret_in(line))

    def test_a_random_key_rarely_reads_as_a_name(self):
        drawn = random.Random(11)
        for alphabet in (string.ascii_letters + string.digits, "0123456789abcdef"):
            keys = ["".join(drawn.choice(alphabet) for _ in range(40)) for _ in range(500)]
            keys = [k for k in keys if any(c.isdigit() for c in k)]
            passed = [k for k in keys if screen.secret_in(f'Client{"Key"} = "{k}"') is None]
            self.assertLessEqual(len(passed), len(keys) // 100, passed[:3])


class CutTests(unittest.TestCase):
    DIFF = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n-old = 1\n+new = 2\n"
        "diff --git a/t.py b/t.py\n--- a/t.py\n+++ b/t.py\n@@ -4,3 +4,2 @@\n ctx\n-KEY = '{key}'\n"
        "-SECRET = 'beside it'\n@@ -20 +19 @@\n-x = 3\n+x = 4\n"
    )

    def test_the_stretch_that_holds_a_secret_is_cut_whole_and_the_rest_is_kept(self):
        sent, cut = screen.cut(self.DIFF.format(key=KEY))
        self.assertEqual(cut, "aws-key")
        self.assertNotIn(KEY, sent)
        self.assertNotIn("beside it", sent, "the lines beside the secret go with it")
        self.assertIn("+new = 2", sent)
        self.assertIn("+x = 4", sent, "another stretch of the same file is still sent")

    def test_a_change_with_nothing_but_the_secret_or_none_left_to_cut_is_refused_whole(self):
        only = "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+KEY = '" + KEY + "'\n"
        bare = "diff --git a/t.py b/t.py\n-KEY = '" + KEY + "'\n"
        header = "diff --git a/" + KEY + ".py b/" + KEY + ".py\n@@ -1 +1 @@\n-a\n+b\n"
        for diff in (only, bare, header, "no diff at all, but " + KEY):
            with self.subTest(diff=diff[:30]):
                self.assertEqual(screen.cut(diff), (None, "aws-key"))

    def test_a_change_with_no_secret_is_sent_as_it_is(self):
        diff = self.DIFF.format(key="a plain value")
        self.assertEqual(screen.cut(diff), (diff, None))
        self.assertEqual(screen.cut("no diff at all"), ("no diff at all", None))

    def test_gadfly_withholds_the_same_patterns(self):
        self.assertEqual(screen.withheld(), {"always": {"patterns": [p for _, p in screen.PATTERNS]}})


if __name__ == "__main__":
    unittest.main()
