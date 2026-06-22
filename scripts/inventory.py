#!/usr/bin/env python3
"""Create a deterministic structural inventory of an Agent Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules"}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".mts",
    ".cts",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
}
ACTION_TERMS = (
    "run",
    "read",
    "inspect",
    "validate",
    "check",
    "find",
    "search",
    "sort",
    "convert",
    "extract",
    "compare",
    "generate",
    "write",
    "update",
    "create",
    "delete",
    "fetch",
    "parse",
    "execute",
    "実行",
    "検索",
    "確認",
    "検証",
    "読む",
    "読み",
    "取得",
    "抽出",
    "変換",
    "並べ",
    "生成",
    "作成",
    "更新",
    "削除",
    "比較",
    "解析",
)
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})([^`]*)$")
LIST_RE = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(.+?)\s*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


class InventoryError(Exception):
    """Expected input or parsing error."""


@dataclass(frozen=True)
class Fence:
    language: str
    start_line: int
    end_line: int
    content: str


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_directory", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InventoryError(f"file is not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise InventoryError(f"cannot read file: {path}: {exc}") from exc


def parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped in {"true", "false"}:
        return stripped == "true"
    if stripped in {"null", "~"}:
        return None
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        return stripped[1:-1]
    return stripped


def parse_frontmatter(text: str) -> tuple[dict[str, Any], int]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, 0

    metadata: dict[str, Any] = {}
    for index, raw_line in enumerate(match.group(1).splitlines(), start=2):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if key:
            metadata[key] = parse_scalar(value)

    consumed_lines = text[: match.end()].count("\n")
    return metadata, consumed_lines


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def relative_posix(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root)).as_posix()


def file_record(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": relative_posix(path, root),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "text_candidate": path.suffix.lower() in TEXT_SUFFIXES or path.name == "SKILL.md",
    }


def extract_headings(lines: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    inside_fence = False
    fence_token = ""
    for line_number, line in enumerate(lines, start=1):
        fence = FENCE_RE.match(line)
        if fence:
            token = fence.group(1)
            if not inside_fence:
                inside_fence = True
                fence_token = token[0]
            elif token[0] == fence_token:
                inside_fence = False
                fence_token = ""
            continue
        if inside_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            result.append(
                {
                    "level": len(heading.group(1)),
                    "text": heading.group(2),
                    "line": line_number,
                }
            )
    return result


def extract_fences(lines: list[str]) -> list[Fence]:
    fences: list[Fence] = []
    start_line: int | None = None
    marker = ""
    language = ""
    content: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        match = FENCE_RE.match(line)
        if start_line is None:
            if match:
                start_line = line_number
                marker = match.group(1)
                language = match.group(2).strip().split(maxsplit=1)[0] if match.group(2).strip() else ""
                content = []
            continue

        if match and match.group(1)[0] == marker[0] and len(match.group(1)) >= len(marker):
            fences.append(
                Fence(
                    language=language,
                    start_line=start_line,
                    end_line=line_number,
                    content="\n".join(content),
                )
            )
            start_line = None
            marker = ""
            language = ""
            content = []
        else:
            content.append(line)

    if start_line is not None:
        fences.append(
            Fence(
                language=language,
                start_line=start_line,
                end_line=len(lines),
                content="\n".join(content),
            )
        )
    return fences


def normalize_link_target(raw_target: str) -> str | None:
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    return target or None


def extract_references(text: str) -> list[str]:
    references = {
        target
        for raw_target in LINK_RE.findall(text)
        if (target := normalize_link_target(raw_target)) is not None
    }
    return sorted(references)


def extract_instruction_candidates(lines: list[str], fences: list[Fence]) -> list[dict[str, Any]]:
    fenced_lines: set[int] = set()
    for fence in fences:
        fenced_lines.update(range(fence.start_line, fence.end_line + 1))

    candidates: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        if line_number in fenced_lines or HEADING_RE.match(raw_line):
            continue
        stripped = raw_line.strip()
        if not stripped:
            continue
        list_match = LIST_RE.match(raw_line)
        text = list_match.group(1).strip() if list_match else stripped
        lowered = text.casefold()
        if list_match or any(term.casefold() in lowered for term in ACTION_TERMS):
            candidates.append({"line": line_number, "text": text})
    return candidates


def extract_manifest_commands(root: Path) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            parsed = json.loads(read_utf8(package_json))
        except (json.JSONDecodeError, InventoryError):
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("scripts"), dict):
            for name, command in sorted(parsed["scripts"].items()):
                if isinstance(command, str):
                    commands.append(
                        {
                            "source": "package.json",
                            "name": name,
                            "invocation": ["npm", "run", name],
                            "declared_command": command,
                        }
                    )
    return commands


def build_inventory(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise InventoryError(f"not a directory: {root}")

    skill_path = resolved / "SKILL.md"
    if not skill_path.is_file():
        raise InventoryError(f"SKILL.md not found in: {resolved}")

    skill_text = read_utf8(skill_path)
    metadata, _ = parse_frontmatter(skill_text)
    lines = skill_text.splitlines()
    fences = extract_fences(lines)
    files = [file_record(path, resolved) for path in iter_files(resolved)]

    references = []
    for target in extract_references(skill_text):
        target_path = (resolved / target).resolve()
        try:
            inside_root = target_path.is_relative_to(resolved)
        except AttributeError:  # pragma: no cover - Python <3.9 compatibility guard
            inside_root = str(target_path).startswith(str(resolved))
        references.append(
            {
                "target": target,
                "inside_skill": inside_root,
                "exists": inside_root and target_path.exists(),
            }
        )

    scripts = [
        record
        for record in files
        if record["path"].startswith("scripts/") and record["path"] != "scripts/"
    ]

    return {
        "version": "1",
        "skill": {
            "path": resolved.as_posix(),
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "line_count": len(lines),
            "sha256": hashlib.sha256(skill_text.encode("utf-8")).hexdigest(),
        },
        "metadata": metadata,
        "headings": extract_headings(lines),
        "fenced_blocks": [
            {
                "language": fence.language,
                "start_line": fence.start_line,
                "end_line": fence.end_line,
                "content_sha256": hashlib.sha256(fence.content.encode("utf-8")).hexdigest(),
            }
            for fence in fences
        ],
        "instruction_candidates": extract_instruction_candidates(lines, fences),
        "references": references,
        "repository_commands": extract_manifest_commands(resolved),
        "scripts": scripts,
        "files": files,
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    skill = inventory["skill"]
    lines = [
        f"# Inventory: {skill.get('name') or 'unnamed skill'}",
        "",
        f"- Path: `{skill['path']}`",
        f"- SKILL.md lines: {skill['line_count']}",
        f"- Files: {len(inventory['files'])}",
        f"- Instruction candidates: {len(inventory['instruction_candidates'])}",
        f"- Repository commands: {len(inventory['repository_commands'])}",
        "",
        "## Instruction candidates",
        "",
    ]
    for candidate in inventory["instruction_candidates"]:
        lines.append(f"- L{candidate['line']}: {candidate['text']}")
    if not inventory["instruction_candidates"]:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        inventory = build_inventory(args.skill_directory)
    except InventoryError as exc:
        print(f"inventory: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        json.dump(inventory, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(inventory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
