from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CREATED = "2026-09-11T00:00:00Z"


def parse_requirements(text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"un-pinned requirement: {line}")
        name, version = line.split("==", 1)
        name = re.sub(r"\[.*\]$", "", name.strip())
        items.append((name, version.strip()))
    return sorted(items, key=lambda item: item[0].lower())


def spdx_id(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9.-]", "-", name)
    return f"SPDXRef-Package-{safe}"


def build_sbom(requirements_text: str) -> dict:
    digest = hashlib.sha256(requirements_text.encode("utf-8")).hexdigest()
    packages = []
    relationships = []
    for name, version in parse_requirements(requirements_text):
        identifier = spdx_id(name)
        packages.append(
            {
                "SPDXID": identifier,
                "name": name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": identifier,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "TradeOps-GenAI-Integration-python-dependencies",
        "documentNamespace": f"https://tradeops.local/spdx/{digest}",
        "creationInfo": {"created": CREATED, "creators": ["Tool: tradeops-i8-sbom"]},
        "packages": packages,
        "relationships": relationships,
    }


def render(requirements_path: Path) -> str:
    payload = build_sbom(requirements_path.read_text(encoding="utf-8"))
    return json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--output", default="security/sbom.spdx.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    requirements_path = Path(args.requirements)
    expected_payload = build_sbom(requirements_path.read_text(encoding="utf-8"))
    output = Path(args.output)
    if args.check:
        try:
            actual_payload = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print("SBOM_CHECK_FAIL: regenerate security/sbom.spdx.json")
            return 1
        if actual_payload != expected_payload:
            print("SBOM_CHECK_FAIL: regenerate security/sbom.spdx.json")
            return 1
        print("SBOM_CHECK_PASS")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(expected_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
