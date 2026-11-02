import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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
    def test_custom_fractional_timeout_is_passed_to_request(self, mock_urlopen):
        response = MagicMock()
        response.status = 200
        response.headers.get.side_effect = {
            "Content-Type": "image/webp",
            "Content-Length": "2048",
        }.get
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/image.webp",
            timeout=0.5,
        )

        self.assertEqual(result["result"], "OK")
        mock_urlopen.assert_called_once()
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 0.5)

    @patch("image_url_auditor.urlopen")
    def test_generic_content_type_is_flagged_with_explanation(self, mock_urlopen):
        response = MagicMock()
        response.status = 200
        response.headers.get.side_effect = {
            "Content-Type": "application/octet-stream",
            "Content-Length": "1234",
        }.get
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/product-image"
        )

        self.assertEqual(result["result"], "CHECK")
        self.assertIn("application/octet-stream", result["error"])

    @patch("image_url_auditor.urlopen")
    def test_missing_content_type_is_flagged_with_explanation(self, mock_urlopen):
        response = MagicMock()
        response.status = 200
        response.headers.get.return_value = ""
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/product-image"
        )

        self.assertEqual(result["result"], "CHECK")
        self.assertIn("missing Content-Type", result["error"])

    @patch("image_url_auditor.urlopen")
    def test_http_204_is_not_a_valid_image(self, mock_urlopen):
        response = MagicMock()
        response.status = 204
        response.headers.get.side_effect = {
            "Content-Type": "image/jpeg",
            "Content-Length": "",
        }.get
        mock_urlopen.return_value.__enter__.return_value = response

        result = image_url_auditor.check_image(
            "https://example.com/empty-image.jpg"
        )

        self.assertEqual(result["status"], 204)
        self.assertEqual(result["result"], "CHECK")

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


    def test_invalid_timeouts_are_rejected_before_network_request(self):
        invalid_timeouts = (
            0,
            -1,
            float("nan"),
            float("inf"),
            float("-inf"),
            True,
            None,
            "1",
        )

        for timeout in invalid_timeouts:
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    image_url_auditor.check_image(
                        "https://example.com/image.jpg",
                        timeout=timeout,
                    )


    @patch("image_url_auditor.urlopen")
    def test_http_error_without_headers_is_reported_without_crashing(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/unavailable.jpg",
            503,
            "Service Unavailable",
            None,
            None,
        )

        result = image_url_auditor.check_image(
            "https://example.com/unavailable.jpg"
        )

        self.assertEqual(result["status"], 503)
        self.assertEqual(result["result"], "HTTP_ERROR")
        self.assertIn("HTTP 503", result["error"])

    @patch("image_url_auditor.urlopen")
    def test_connection_timeout_is_reported_as_connection_error(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError(TimeoutError("connection timed out"))

        result = image_url_auditor.check_image(
            "https://example.com/slow-image.jpg"
        )

        self.assertEqual(result["result"], "CONNECTION_ERROR")
        self.assertIn("timed out", result["error"])


    @patch("image_url_auditor.urlopen")
    def test_common_http_error_statuses_are_preserved(self, mock_urlopen):
        cases = (
            (403, "Forbidden"),
            (429, "Too Many Requests"),
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable"),
            (504, "Gateway Timeout"),
        )

        for status, reason in cases:
            with self.subTest(status=status):
                mock_urlopen.side_effect = HTTPError(
                    "https://example.com/image.jpg",
                    status,
                    reason,
                    {},
                    None,
                )

                result = image_url_auditor.check_image(
                    "https://example.com/image.jpg"
                )

                self.assertEqual(result["status"], status)
                self.assertEqual(result["result"], "HTTP_ERROR")
                self.assertIn(f"HTTP {status}", result["error"])


class TestBuildAuditSummary(unittest.TestCase):

    def test_counts_all_known_results_and_calculates_ok_rate(self):
        results = [
            {"result": "OK"},
            {"result": "OK"},
            {"result": "CHECK"},
            {"result": "HTTP_ERROR"},
            {"result": "CONNECTION_ERROR"},
            {"result": "INVALID_URL"},
        ]

        summary = image_url_auditor.build_audit_summary(results)

        self.assertEqual(summary["total"], 6)
        self.assertEqual(
            summary["counts"],
            {
                "OK": 2,
                "CHECK": 1,
                "HTTP_ERROR": 1,
                "CONNECTION_ERROR": 1,
                "INVALID_URL": 1,
                "UNKNOWN": 0,
            },
        )
        self.assertEqual(summary["success_rate"], 33.33)

    def test_empty_results_have_zero_success_rate(self):
        summary = image_url_auditor.build_audit_summary([])

        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["success_rate"], 0.0)
        self.assertTrue(all(value == 0 for value in summary["counts"].values()))

    def test_unknown_result_is_counted_in_its_own_bucket(self):
        summary = image_url_auditor.build_audit_summary(
            [{"result": "OK"}, {"result": "UNEXPECTED"}]
        )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["counts"]["OK"], 1)
        self.assertEqual(summary["counts"]["UNKNOWN"], 1)
        self.assertEqual(sum(summary["counts"].values()), summary["total"])
        self.assertEqual(summary["success_rate"], 50.0)

    def test_formatted_summary_contains_counts_and_rate(self):
        summary = image_url_auditor.build_audit_summary(
            [{"result": "OK"}, {"result": "CHECK"}]
        )

        report = image_url_auditor.format_audit_summary(summary)

        self.assertIn("Total URLs: 2", report)
        self.assertIn("Valid images (OK): 1", report)
        self.assertIn("Success rate: 50.00%", report)



class TestImageAuditCli(unittest.TestCase):

    def _write_input(self, path):
        with open(path, "w", encoding="utf-8", newline="") as source:
            writer = csv.DictWriter(
                source,
                fieldnames=("SKU", "PRODUCT_NAME", "IMAGE_URL"),
                delimiter=";",
            )
            writer.writeheader()
            writer.writerow({"SKU": "A-1", "PRODUCT_NAME": "Product A", "IMAGE_URL": "https://example.com/a.jpg"})
            writer.writerow({"SKU": "B-2", "PRODUCT_NAME": "Product B", "IMAGE_URL": "https://example.com/b.jpg"})

    @patch("image_url_auditor.check_image")
    def test_cli_writes_summary_and_preserves_csv_columns(self, mock_check):
        mock_check.side_effect = [
            {"status": 200, "content_type": "image/jpeg", "content_length": "123", "response_time": 0.1, "result": "OK", "error": ""},
            {"status": 404, "content_type": "", "content_length": "", "response_time": 0.2, "result": "HTTP_ERROR", "error": "HTTP 404: Not Found"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.csv"
            output_path = Path(temp_dir) / "audit.csv"
            summary_path = Path(temp_dir) / "summary.txt"
            self._write_input(input_path)
            args = ["image_url_auditor.py", "--input", str(input_path), "--output", str(output_path), "--summary-output", str(summary_path)]
            with patch.object(sys, "argv", args), redirect_stdout(io.StringIO()):
                image_url_auditor.main()

            self.assertTrue(summary_path.is_file())
            report = summary_path.read_text(encoding="utf-8")
            self.assertIn("Total URLs: 2", report)
            self.assertIn("Valid images (OK): 1", report)
            self.assertIn("HTTP errors: 1", report)
            self.assertIn("Success rate: 50.00%", report)
            with open(output_path, encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, delimiter=";")
                self.assertEqual(reader.fieldnames, ["SKU", "PRODUCT_NAME", "IMAGE_URL", *image_url_auditor.FIELDNAMES])
                rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["SKU"], "A-1")
            self.assertEqual(rows[1]["SKU"], "B-2")
            self.assertEqual(rows[0]["result"], "OK")
            self.assertEqual(rows[1]["result"], "HTTP_ERROR")
            self.assertEqual(mock_check.call_count, 2)

    @patch("image_url_auditor.check_image")
    def test_cli_refuses_to_overwrite_existing_summary(self, mock_check):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.csv"
            output_path = Path(temp_dir) / "audit.csv"
            summary_path = Path(temp_dir) / "summary.txt"
            self._write_input(input_path)
            summary_path.write_text("keep this report", encoding="utf-8")
            args = ["image_url_auditor.py", "--input", str(input_path), "--output", str(output_path), "--summary-output", str(summary_path)]
            with patch.object(sys, "argv", args):
                with self.assertRaises(SystemExit) as raised:
                    image_url_auditor.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(summary_path.read_text(encoding="utf-8"), "keep this report")
            self.assertFalse(output_path.exists())
            mock_check.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
