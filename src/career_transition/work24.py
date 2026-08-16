"""Small, dependency-free client for the official Work24 occupation API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


LIST_ENDPOINT = (
    "https://www.work24.go.kr/cm/openApi/call/wk/"
    "callOpenApiSvcInfo212L01.do"
)
DETAIL_ENDPOINT = (
    "https://www.work24.go.kr/cm/openApi/call/wk/"
    "callOpenApiSvcInfo212D03.do"
)
DETAIL_SECTIONS = range(1, 8)


class Work24Error(RuntimeError):
    """Raised when a Work24 request or response cannot be processed."""


@dataclass(frozen=True, slots=True)
class JobSummary:
    job_class_code: str
    job_class_name: str
    job_code: str
    job_name: str


def _text(element: ET.Element, tag: str) -> str:
    value = element.findtext(tag)
    return value.strip() if value else ""


def parse_job_list(xml_bytes: bytes) -> tuple[int, list[JobSummary]]:
    """Parse a Work24 occupation-list XML response."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise Work24Error("고용24 응답이 유효한 XML이 아닙니다.") from exc

    total_text = _text(root, "total") or "0"
    try:
        total = int(total_text)
    except ValueError as exc:
        raise Work24Error(f"고용24 total 값이 숫자가 아닙니다: {total_text!r}") from exc

    jobs = [
        JobSummary(
            job_class_code=_text(item, "jobClcd"),
            job_class_name=_text(item, "jobClcdNM"),
            job_code=_text(item, "jobCd"),
            job_name=_text(item, "jobNm"),
        )
        for item in root.findall(".//jobList")
    ]
    return total, jobs


def write_jobs_csv(jobs: Iterable[JobSummary], output_path: Path) -> None:
    """Write normalized occupation summaries in a stable UTF-8 CSV schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["job_class_code", "job_class_name", "job_code", "job_name"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(job) for job in jobs)


class Work24Client:
    """Client limited to the occupation-list and occupation-detail APIs."""

    def __init__(self, auth_key: str, *, timeout: float = 30.0) -> None:
        if not auth_key or auth_key == "replace_with_your_issued_key":
            raise ValueError("WORK24_AUTH_KEY에 발급받은 인증키를 설정하세요.")
        self._auth_key = auth_key
        self.timeout = timeout

    def _get(self, endpoint: str, params: dict[str, str]) -> bytes:
        query = urlencode({"authKey": self._auth_key, "returnType": "XML", **params})
        request = Request(
            f"{endpoint}?{query}",
            headers={"User-Agent": "military-career-transition-analysis/0.1"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as exc:
            raise Work24Error(f"고용24가 HTTP {exc.code} 오류를 반환했습니다.") from None
        except URLError:
            raise Work24Error("고용24에 연결할 수 없습니다.") from None

        if not payload.strip():
            raise Work24Error("고용24가 빈 응답을 반환했습니다.")
        return payload

    def list_jobs(self, *, keyword: str | None = None) -> tuple[bytes, int, list[JobSummary]]:
        params = {"target": "JOBCD", "srchType": "K"}
        if keyword:
            params["keyword"] = keyword
        payload = self._get(LIST_ENDPOINT, params)
        total, jobs = parse_job_list(payload)
        return payload, total, jobs

    def job_detail(self, job_code: str, section: int) -> bytes:
        if not job_code.strip():
            raise ValueError("job_code는 비어 있을 수 없습니다.")
        if section not in DETAIL_SECTIONS:
            raise ValueError("section은 1부터 7까지여야 합니다.")
        return self._get(
            DETAIL_ENDPOINT,
            {
                "target": "JOBDTL",
                "jobGb": "1",
                "jobCd": job_code.strip(),
                "dtlGb": str(section),
            },
        )

    @staticmethod
    def save_raw(payload: bytes, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(payload)


def collection_stamp() -> str:
    """Return an auditable UTC timestamp suitable for file names."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
