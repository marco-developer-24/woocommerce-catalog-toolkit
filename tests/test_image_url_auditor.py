import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import image_url_auditor


class TestCheckImage(unittest.TestCase):

    @patch("image_url_auditor.urlopen")
    def test_valid_image(self, mock_urlopen):
        response = MagicMock()
        response.status = 200
        response.headers.get.side_effect = {
            "Content-Type": "image/jpeg",
            "Content-Length": "1234",
        }.get
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/image.jpg"
        )

        self.assertEqual(result["result"], "OK")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["content_type"], "image/jpeg")

    @patch("image_url_auditor.urlopen")
    def test_http_success_but_not_an_image(self, mock_urlopen):
        response = MagicMock()
        response.status = 200
        response.headers.get.side_effect = {
            "Content-Type": "text/html",
            "Content-Length": "500",
        }.get
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/not-an-image"
        )

        self.assertEqual(result["result"], "CHECK")

    @patch("image_url_auditor.urlopen")
    def test_http_404(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/missing.jpg",
            404,
            "Not Found",
            {},
            None,
        )

        result = image_url_auditor.check_image(
            "https://example.com/missing.jpg"
        )

        self.assertEqual(result["result"], "HTTP_ERROR")
        self.assertEqual(result["status"], 404)

    @patch("image_url_auditor.urlopen")
    def test_empty_url_does_not_make_request(self, mock_urlopen):
        result = image_url_auditor.check_image("")

        self.assertEqual(result["result"], "INVALID_URL")
        mock_urlopen.assert_not_called()

    def test_relative_url_is_invalid(self):
        result = image_url_auditor.check_image("/images/product.jpg")

        self.assertEqual(result["result"], "INVALID_URL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
