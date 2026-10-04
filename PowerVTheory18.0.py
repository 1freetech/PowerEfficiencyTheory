"""Power Efficiency Theory repository audit 18.0

What changed in 18.0:
- audits the complete simulator lineage, including legacy v1/v2 filenames
- fingerprints normalized implementation substance to detect superficial version churn
- checks numbered releases for embedded-version and validation-artifact consistency
- emits machine-readable JSON plus a concise human-readable summary
"""

from __future__ import annotations

import argparse
import hashlib
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
    version_check_applicable: bool
    matches: bool | None
    validation_json: str | None
    validation_json_version: str | None
    validation_json_matches: bool | None
    implementation_fingerprint: str
    duplicate_of: str | None


VERSION_PATTERN = re.compile(r"PowerVTheory(\d+\.\d+)\.py$")
EMBEDDED_PATTERN = re.compile(r'"version"\s*:\s*"([^"]+)"')
LEGACY_VERSIONS = {
    "PowerVTheory.py": "1.0",
    "PowerETheory2.0": "2.0",
}


def normalized_implementation(text: str) -> str:
    """Remove release-only metadata so fingerprints reflect implementation substance."""
    text = re.sub(
        r"Power Efficiency Theory (?:Simulator|Calculator) \d+\.\d+",
        "Power Efficiency Theory <APP> <VERSION>",
        text,
    )
    text = re.sub(r'"version"\s*:\s*"\d+\.\d+"', '"version": "<VERSION>"', text)
    text = re.sub(
        r"power_efficiency_\d+_\d+_(validation\.json|summary\.txt)",
        r"power_efficiency_<VERSION>_\1",
        text,
    )
    return text


def implementation_fingerprint(text: str) -> str:
    return hashlib.sha256(normalized_implementation(text).encode("utf-8")).hexdigest()


def discover_python_versions(repo: Path) -> list[Path]:
    """Return legacy v1/v2 plus every numbered PowerVTheory release present in repo root."""
    candidates: list[Path] = []

    for name in LEGACY_VERSIONS:
        path = repo / name
        if path.is_file():
            candidates.append(path)

    for path in repo.glob("PowerVTheory*.py"):
        if VERSION_PATTERN.fullmatch(path.name):
            candidates.append(path)

    def version_key(path: Path) -> tuple[int, int, str]:
        version = extract_expected_version(path)
        if version is None:
            return (999999, 999999, path.name)
        major, minor = version.split(".", 1)
        return (int(major), int(minor), path.name)

    return sorted(candidates, key=version_key)


def extract_expected_version(path: Path) -> str | None:
    if path.name in LEGACY_VERSIONS:
        return LEGACY_VERSIONS[path.name]
    match = VERSION_PATTERN.fullmatch(path.name)
    return match.group(1) if match else None


def extract_embedded_version_from_text(text: str) -> str | None:
    match = EMBEDDED_PATTERN.search(text)
    return match.group(1) if match else None


def related_validation_file(py_path: Path, expected_version: str | None) -> Path | None:
    if not expected_version:
        return None
    stem = expected_version.replace(".", "_")
    candidate = py_path.parent / f"power_efficiency_{stem}_validation.json"
    return candidate if candidate.exists() else None


def audit_versions(repo: Path) -> dict:
    rows: list[VersionAuditRow] = []
    first_seen: dict[str, str] = {}

    for py_path in discover_python_versions(repo):
        expected = extract_expected_version(py_path)
        source_text = py_path.read_text(encoding="utf-8", errors="ignore")
        embedded = extract_embedded_version_from_text(source_text)
        version_check_applicable = py_path.name not in LEGACY_VERSIONS
        code_matches = (
            embedded == expected
            if version_check_applicable and expected is not None
            else None
        )

        fingerprint = implementation_fingerprint(source_text)
        duplicate_of = first_seen.get(fingerprint)
        first_seen.setdefault(fingerprint, py_path.name)

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
                version_check_applicable=version_check_applicable,
                matches=code_matches,
                validation_json=validation_path.name if validation_path is not None else None,
                validation_json_version=validation_version,
                validation_json_matches=validation_matches,
                implementation_fingerprint=fingerprint,
                duplicate_of=duplicate_of,
            )
        )

    checked = [row for row in rows if row.version_check_applicable]
    code_matches = sum(1 for row in checked if row.matches is True)
    code_mismatches = sum(1 for row in checked if row.matches is False)
    code_not_applicable = sum(1 for row in rows if not row.version_check_applicable)

    json_checks = [row for row in rows if row.validation_json is not None]
    json_matches = sum(1 for row in json_checks if row.validation_json_matches is True)
    json_mismatches = sum(1 for row in json_checks if row.validation_json_matches is False)
    substantive_duplicates = sum(1 for row in rows if row.duplicate_of is not None)

    return {
        "version": "18.0",
        "audit_scope": "complete Power Efficiency Theory simulator lineage in repo root, including legacy v1/v2 filenames",
        "summary": {
            "implementation_files_checked": len(rows),
            "numbered_version_checks": len(checked),
            "code_version_matches": code_matches,
            "code_version_mismatches": code_mismatches,
            "legacy_version_checks_not_applicable": code_not_applicable,
            "validation_json_files_checked": len(json_checks),
            "validation_json_matches": json_matches,
            "validation_json_mismatches": json_mismatches,
            "substantive_duplicates": substantive_duplicates,
        },
        "rows": [asdict(row) for row in rows],
    }


def build_summary_text(report: dict) -> str:
    summary = report["summary"]
    mismatches = [
        row
        for row in report["rows"]
        if row["matches"] is False or row["validation_json_matches"] is False
    ]
    duplicates = [row for row in report["rows"] if row["duplicate_of"] is not None]

    lines = [
        "Power Efficiency Theory 18.0 repository consistency audit",
        f"Checked {summary['implementation_files_checked']} implementation files, including legacy v1/v2, and {summary['validation_json_files_checked']} validation JSON artifacts.",
        f"Numbered code-version matches: {summary['code_version_matches']} | mismatches: {summary['code_version_mismatches']} | legacy N/A: {summary['legacy_version_checks_not_applicable']}",
        f"Validation JSON matches: {summary['validation_json_matches']} | mismatches: {summary['validation_json_mismatches']}",
        f"Substantive duplicate implementations: {summary['substantive_duplicates']}",
        "Mismatch details:",
    ]

    if mismatches:
        for row in mismatches:
            lines.append(
                "- {file}: expected={expected_version}, embedded={embedded_version}, "
                "validation={validation_json}, validation_version={validation_json_version}".format(**row)
            )
    else:
        lines.append("- No mismatches detected.")

    if duplicates:
        lines.append("Substantive duplicate details:")
        for row in duplicates:
            lines.append(
                f"- {row['file']} duplicates {row['duplicate_of']} "
                f"(fingerprint {row['implementation_fingerprint'][:12]})"
            )

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
    parser = argparse.ArgumentParser(description="Power Efficiency Theory repository audit 18.0")
    parser.add_argument("--validate", action="store_true", help="Run headless validation and exit")
    parser.add_argument("--repo", default=".", help="Repo path to audit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo = Path(args.repo).resolve()
    result = run_headless_validation(repo)
    print(result["summary_text"])
    if args.validate:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
