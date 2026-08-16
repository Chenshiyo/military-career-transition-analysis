from pathlib import Path
import tempfile
import unittest

from career_transition.work24 import Work24Client, Work24Error, parse_job_list, write_jobs_csv


FIXTURE = Path(__file__).parent / "fixtures" / "jobs.xml"


class ParseJobListTests(unittest.TestCase):
    def test_parses_official_list_shape(self) -> None:
        total, jobs = parse_job_list(FIXTURE.read_bytes())

        self.assertEqual(total, 2)
        self.assertEqual([job.job_code for job in jobs], ["100001", "100002"])
        self.assertEqual(jobs[1].job_name, "네트워크관리자")

    def test_rejects_invalid_xml(self) -> None:
        with self.assertRaisesRegex(Work24Error, "유효한 XML"):
            parse_job_list(b"not xml")

    def test_writes_excel_friendly_csv(self) -> None:
        _, jobs = parse_job_list(FIXTURE.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "jobs.csv"
            write_jobs_csv(jobs, output)
            content = output.read_text(encoding="utf-8-sig")

        self.assertIn("job_class_code,job_class_name,job_code,job_name", content)
        self.assertIn("100002", content)


class ClientValidationTests(unittest.TestCase):
    def test_rejects_missing_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "WORK24_AUTH_KEY"):
            Work24Client("")

    def test_rejects_invalid_detail_section(self) -> None:
        client = Work24Client("test-only-key")
        with self.assertRaisesRegex(ValueError, "1부터 7"):
            client.job_detail("100001", 8)


if __name__ == "__main__":
    unittest.main()
