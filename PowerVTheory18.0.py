"""Power Efficiency Theory Simulator 18.0

## What changed in 18.0 and why
- adds a version-consistency audit for additive PowerVTheory releases so scheduled work can catch stale metadata drift instead of creating empty churn
- emits a machine-readable audit report plus a concise summary of which versioned simulator files match or mismatch their embedded version labels
- preserves the additive-only workflow by creating new 18.0 artifacts rather than rewriting earlier user-created files in place
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class VersionAuditRow:
    file: str
    expected_version: str | None
    embedded_version: str | None
    matches: bool
    validation_json: str | None
    validation_json_version: str | None
    validation_json_matches: bool | None


VERSION_PATTERN = re.compile(r"PowerVTheory(\d+\.\d+)\.py$")
EMBEDDED_PATTERN = re.compile(r'"version"\s*:\s*"([^"]+)"')


def discover_python_versions(repo: Path) -> list[Path]:
    candidates = []
    for path in repo.glob("PowerVTheory*.py"):
        if VERSION_PATTERN.search(path.name):
            candidates.append(path)
    return sorted(candidates, key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)])


def extract_expected_version(path: Path) -> str | None:
    match = VERSION_PATTERN.search(path.name)
    return match.group(1) if match else None


def extract_embedded_version_from_text(text: str) -> str | None:
    match = EMBEDDED_PATTERN.search(text)
    return match.group(1) if match else None


def related_validation_file(py_path: Path, expected_version: str | None) -> Path | None:
    if not expected_version:
        return None
    stem = expected_version.replace('.', '_')
    candidate = py_path.parent / f"power_efficiency_{stem}_validation.json"
    return candidate if candidate.exists() else None


def audit_versions(repo: Path) -> dict:
    rows: list[VersionAuditRow] = []
    for py_path in discover_python_versions(repo):
        expected = extract_expected_version(py_path)
        embedded = extract_embedded_version_from_text(py_path.read_text(encoding="utf-8", errors="ignore"))
        validation_path = related_validation_file(py_path, expected)
        validation_version = None
        validation_matches = None
        if validation_path is not None:
            try:
                obj = json.loads(validation_path.read_text(encoding="utf-8"))
                validation_version = obj.get("version")
                validation_matches = validation_version == expected
            except Exception:
                validation_version = None
                validation_matches = False

        rows.append(
            VersionAuditRow(
                file=py_path.name,
                expected_version=expected,
                embedded_version=embedded,
                matches=(embedded == expected) if expected is not None else False,
                validation_json=validation_path.name if validation_path is not None else None,
                validation_json_version=validation_version,
                validation_json_matches=validation_matches,
            )
        )

    total = len(rows)
    code_matches = sum(1 for row in rows if row.matches)
    code_mismatches = sum(1 for row in rows if not row.matches)
    json_checks = [row for row in rows if row.validation_json is not None]
    json_matches = sum(1 for row in json_checks if row.validation_json_matches is True)
    json_mismatches = sum(1 for row in json_checks if row.validation_json_matches is False)

    return {
        "version": "18.0",
        "audit_scope": "additive PowerVTheory Python releases in repo root",
        "summary": {
            "python_files_checked": total,
            "code_version_matches": code_matches,
            "code_version_mismatches": code_mismatches,
            "validation_json_files_checked": len(json_checks),
            "validation_json_matches": json_matches,
            "validation_json_mismatches": json_mismatches,
        },
        "rows": [asdict(row) for row in rows],
    }


def build_summary_text(report: dict) -> str:
    summary = report["summary"]
    mismatches = [row for row in report["rows"] if not row["matches"] or row["validation_json_matches"] is False]
    lines = [
        "Power Efficiency Theory 18.0 version consistency audit",
        f"Checked {summary['python_files_checked']} versioned Python files and {summary['validation_json_files_checked']} validation JSON artifacts.",
        f"Code version matches: {summary['code_version_matches']} | mismatches: {summary['code_version_mismatches']}",
        f"Validation JSON matches: {summary['validation_json_matches']} | mismatches: {summary['validation_json_mismatches']}",
        "Mismatch details:",
    ]
    if mismatches:
        for row in mismatches:
            lines.append(
                "- {file}: expected={expected_version}, embedded={embedded_version}, validation={validation_json}, validation_version={validation_json_version}".format(**row)
            )
    else:
        lines.append("- No mismatches detected.")
    return "\n".join(lines)


def run_headless_validation(repo: Path) -> dict:
    report = audit_versions(repo)
    summary_text = build_summary_text(report)
    out_json = repo / "power_efficiency_18_0_validation.json"
    out_txt = repo / "power_efficiency_18_0_summary.txt"
    payload = {
        **report,
        "summary_text": summary_text,
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_txt.write_text(summary_text + "\n", encoding="utf-8")
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Power Efficiency Theory Simulator 18.0")
    parser.add_argument("--validate", action="store_true", help="Run headless validation and exit")
    parser.add_argument("--repo", default=".", help="Repo path to audit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo = Path(args.repo).resolve()
    if args.validate:
        result = run_headless_validation(repo)
        print(result["summary_text"])
        print(json.dumps(result, indent=2))
        return 0

    result = run_headless_validation(repo)
    print(result["summary_text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
