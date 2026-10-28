import unittest
from unittest.mock import patch

from src.image_url_auditor import check_image


class TestMalformedUrls(unittest.TestCase):
    def test_malformed_ipv6_url_is_invalid(self):
        result = check_image("http://[invalid/")

        self.assertEqual(result["result"], "INVALID_URL")
        self.assertEqual(result["error"], "Malformed URL")

    @patch("src.image_url_auditor.urlopen")
    def test_url_with_credentials_is_rejected_without_request(self, mock_urlopen):
        result = check_image("https://user:secret@example.com/image.jpg")

        self.assertEqual(result["result"], "INVALID_URL")
        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
