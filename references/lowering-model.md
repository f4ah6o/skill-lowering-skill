# Lowering model

## Decision procedure

Evaluate each atomic operation in order.

### 1. Is the expected result mechanically testable?

A mechanically testable result has an objective predicate such as:

- valid syntax or schema
- exact membership or existence
- stable transformation
- fixed aggregation
- explicit threshold
- documented compiler, linter, or test outcome

If no objective predicate exists, prefer `keep-agent`.

### 2. Does an accepted implementation already exist?

Inspect repository scripts, package-manager scripts, language tooling, and declared dependencies. Record concrete evidence, such as a manifest entry or executable path.

If an accepted implementation exists, classify as `existing-command`.

### 3. Can a small deterministic implementation satisfy the contract?

Use `bundled-script` only when:

- inputs and outputs can be specified
- edge cases can be tested
- behavior is stable across repeated runs
- dependencies and platform assumptions are acceptable

A script that calls an LLM or performs open-ended search is not deterministic lowering.

### 4. Does the operation require authorization?

Use `human-gate` when the operation publishes, deletes, overwrites, spends money, changes access, or otherwise crosses an approval boundary. Mechanical preparation may still be lowered, but execution remains gated.

### 5. Can equivalence be established?

Use `unsupported` when the source instruction is too ambiguous or the proposed replacement covers only part of the behavior. Do not conceal partial coverage behind a high confidence score.

## Risk levels

| Risk | Typical operation | Required treatment |
|---|---|---|
| `low` | read-only validation, sorting, formatting | Unit or fixture test |
| `medium` | file generation, repository mutation | Dry run plus changed-file review |
| `high` | deletion, publication, permission change | Human gate and explicit rollback |

## Split-pattern examples

### Code review

- Run project linters: `existing-command`
- Parse linter output: `existing-command` or `bundled-script`
- Identify architectural defects: `keep-agent`
- Submit review: `human-gate` when publication requires approval

### Documentation maintenance

- Find broken local links: `bundled-script` or existing link checker
- Reflow Markdown: existing formatter
- Judge whether explanations match the audience: `keep-agent`

### Data extraction

- Parse a stable machine-readable source: `bundled-script`
- Infer missing business meaning: `keep-agent`
- Write into production: `human-gate` unless explicitly authorized

## Rejection conditions

Reject a proposed lowering when any condition holds:

- the command's documented behavior does not cover the original instruction
- output ordering is unspecified and relevant
- command availability is assumed but not verified
- failure modes would be hidden from the agent
- the replacement adds an unsafe shell interpolation boundary
- a side effect becomes less visible or less controlled
- the proposed script merely embeds a long prompt and invokes another agent
