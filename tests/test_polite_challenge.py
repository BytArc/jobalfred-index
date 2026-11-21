"""What the polite client takes for a bot check."""
import unittest


class TestWikipediaIsNotAChallenge(unittest.TestCase):
    def test_mediawiki_captcha_setting(self):
        from jobalfred_index.polite import is_challenge
        self.assertFalse(is_challenge(b'<script>RLCONF={"wgConfirmEditCaptchaNeededForGenericEdit":"hcaptcha","wgConfirmEditHCaptchaSiteKey":"5d0c-a5f4"}</script>'))
        self.assertTrue(is_challenge(b'<div class="h-captcha" data-sitekey="x"></div>'))


class FakeResponse:
    def __init__(self, status, headers=None, content=b"{}"):
        self.status_code, self.headers, self.content, self.url = status, headers or {}, content, ""


class FakeSession:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def request(self, method, url, **kw):
        self.calls.append(url)
        return self.answers(url)


class TestFamilyBlock(unittest.TestCase):
    def client(self, answers):
        from unittest import mock
        from jobalfred_index.polite import Client
        c = Client(default_gap=0, inflight=4)
        c.configure_host(".myworkdayjobs.com", gap=0)
        s = FakeSession(answers)
        c._session = lambda: s
        self.addCleanup(mock.patch.stopall)
        mock.patch("jobalfred_index.polite.time.sleep", lambda _s: None).start()
        return c, s

    def test_a_429_from_one_workday_host_skips_every_workday_host(self):
        from jobalfred_index.polite import HOST_SKIPPED
        c, s = self.client(lambda url: FakeResponse(429, {"cf-mitigated": "challenge"}) if "acme" in url else FakeResponse(200))
        self.assertEqual(c.post("https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/x/jobs", robots=False).status, 429)
        r = c.post("https://other.wd1.myworkdayjobs.com/wday/cxs/other/y/jobs", robots=False)
        self.assertEqual(r.status, HOST_SKIPPED)
        self.assertNotIn("other", " ".join(s.calls))
        self.assertEqual(c.get("https://jobs.lever.co/beta", robots=False).status, 200)   # other platforms are untouched

    def test_a_403_still_counts_per_host(self):
        c, s = self.client(lambda url: FakeResponse(403) if "jobs.lever.co" in url else FakeResponse(200))
        for _ in range(3):
            c.get("https://jobs.lever.co/acme", robots=False)
        self.assertIn("jobs.lever.co", c.blocked)
        self.assertEqual(c.get("https://api.lever.co/v0/postings/x", robots=False).status, 200)
