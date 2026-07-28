from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = REPO_ROOT / ".harness"
ACTIVE_ROOT = HARNESS_ROOT / "plans" / "active"
REQUIRED_FIELDS = {"status", "owner", "created", "updated", "scope", "supersedes", "blocked_by"}
LINK_PATTERN = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def _front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML front matter")
    try:
        raw = text.split("---\n", 2)[1]
    except IndexError as exc:
        raise ValueError("unterminated YAML front matter") from exc
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if line and not line.startswith((" ", "-")) and ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def _check_active_plans(errors: list[str]) -> None:
    index = (ACTIVE_ROOT / "README.md").read_text(encoding="utf-8-sig")
    for path in sorted(ACTIVE_ROOT.glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            metadata = _front_matter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(REPO_ROOT)}: {exc}")
            continue
        missing = REQUIRED_FIELDS - metadata.keys()
        if missing:
            errors.append(f"{path.relative_to(REPO_ROOT)}: missing fields {sorted(missing)}")
        if metadata.get("status") != "active":
            errors.append(f"{path.relative_to(REPO_ROOT)}: active plan status must be active")
        filename_date = path.name[:10]
        if metadata.get("created") != filename_date:
            errors.append(f"{path.relative_to(REPO_ROOT)}: created date must match filename")
        if path.name not in index:
            errors.append(f"{path.relative_to(REPO_ROOT)}: missing from active plan index")


def _check_links(errors: list[str]) -> None:
    for path in [REPO_ROOT / "AGENTS.md", *HARNESS_ROOT.rglob("*.md")]:
        text = path.read_text(encoding="utf-8-sig")
        for target in LINK_PATTERN.findall(text):
            clean_target = target.split("#", 1)[0].strip()
            if not clean_target or "://" in clean_target or clean_target.startswith("mailto:"):
                continue
            resolved = (path.parent / clean_target).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(REPO_ROOT)}: broken local link {clean_target!r}")


def validate_harness() -> list[str]:
    errors: list[str] = []
    _check_active_plans(errors)
    _check_links(errors)
    return errors


def main() -> int:
    errors = validate_harness()
    if errors:
        for error in errors:
            print(f"harness validation failed: {error}", file=sys.stderr)
        return 1
    print("harness validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
