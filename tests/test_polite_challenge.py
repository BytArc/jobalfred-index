"""What the polite client takes for a bot check."""
import unittest


class TestWikipediaIsNotAChallenge(unittest.TestCase):
    def test_mediawiki_captcha_setting(self):
        from jobalfred_index.polite import is_challenge
        self.assertFalse(is_challenge(b'<script>RLCONF={"wgConfirmEditCaptchaNeededForGenericEdit":"hcaptcha","wgConfirmEditHCaptchaSiteKey":"5d0c-a5f4"}</script>'))
        self.assertTrue(is_challenge(b'<div class="h-captcha" data-sitekey="x"></div>'))
