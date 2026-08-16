"""Command-line entry point for collecting Work24 occupation data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .work24 import Work24Client, Work24Error, collection_stamp, write_jobs_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="고용24 직업정보 XML을 수집하고 목록을 CSV로 정규화합니다."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/work24"),
        help="XML 원문 저장 위치 (기본값: data/raw/work24)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="직업 목록 수집")
    list_parser.add_argument("--keyword", help="UTF-8 직업명 검색어")
    list_parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/processed/work24_jobs.csv"),
        help="정규화된 CSV 저장 위치",
    )

    detail_parser = subparsers.add_parser("detail", help="직업 상세 한 구간 수집")
    detail_parser.add_argument("job_code", help="직업 목록 API가 반환한 직업코드")
    detail_parser.add_argument(
        "--section",
        type=int,
        choices=range(1, 8),
        required=True,
        help="1 요약, 2 하는 일, 3 교육/자격/훈련, 4 임금/전망, 5 능력/지식/환경, 6 성격/흥미/가치관, 7 업무활동",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    client = Work24Client(os.environ.get("WORK24_AUTH_KEY", ""))
    stamp = collection_stamp()

    if args.command == "list":
        payload, total, jobs = client.list_jobs(keyword=args.keyword)
        raw_path = args.output_dir / f"jobs_{stamp}.xml"
        client.save_raw(payload, raw_path)
        write_jobs_csv(jobs, args.csv)
        print(f"목록 {len(jobs)}건 저장 (API total={total})")
        print(f"원문: {raw_path}")
        print(f"CSV: {args.csv}")
        return 0

    payload = client.job_detail(args.job_code, args.section)
    raw_path = args.output_dir / "details" / f"{args.job_code}_s{args.section}_{stamp}.xml"
    client.save_raw(payload, raw_path)
    print(f"상세 XML 저장: {raw_path}")
    return 0


def main() -> None:
    try:
        raise SystemExit(run(build_parser().parse_args()))
    except (ValueError, Work24Error) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
