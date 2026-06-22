# Command candidate catalog

This catalog provides search hints. Verify installation, version, license, platform support, and project conventions before selecting a command.

| Operation | Candidate commands or interfaces | Notes |
|---|---|---|
| File discovery | `find`, `fd`, `git ls-files` | Prefer `git ls-files` when only tracked files are relevant. |
| Text search | `rg`, `grep` | Fix locale and binary-file behavior where relevant. |
| JSON query/validation | `jq`, JSON Schema validator | `jq empty` checks JSON syntax, not domain validity. |
| YAML query | `yq`, language parser | Multiple unrelated tools use the name `yq`; identify implementation. |
| CSV transformation | DuckDB, `qsv`, Python `csv` | Specify encoding, delimiter, header, and sort rules. |
| Git state | `git status`, `git diff`, `git log` | Prefer porcelain or explicit machine formats. |
| GitHub metadata | `gh` | Network and authentication make the result environment-dependent. |
| JavaScript lint/typecheck | project package scripts, ESLint, oxlint, `tsc` | Prefer manifest scripts to direct global invocation. |
| Python lint/typecheck | project scripts, Ruff, mypy, Pyright | Respect existing configuration files. |
| Shell analysis | ShellCheck, `bash -n` | `bash -n` is syntax-only. |
| Markdown formatting | project formatter, Prettier, markdownlint | Formatting and semantic quality are separate. |
| Link checking | project link checker, generated script | Network link checks are not deterministic without a snapshot. |
| Archive operations | `tar`, `zip`, language libraries | Normalize timestamps if byte-for-byte reproducibility matters. |
| Hashing | `sha256sum`, `shasum -a 256`, language library | Select a portable fallback. |

## Selection rules

1. Use a repository-defined command when it represents the project's supported interface.
2. Use machine-readable output modes.
3. Pin or constrain versions when output shape is consumed programmatically.
4. Avoid shell pipelines that lose individual exit statuses.
5. Generate a bundled script when portability or error handling would otherwise require a fragile command chain.
6. Keep semantic evaluation outside the command even when a command supplies evidence.
