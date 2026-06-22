---
name: skill-lowering
description: Analyze an existing Agent Skill and refactor deterministic or mechanical instructions into existing CLI commands or bundled scripts while preserving semantic agent judgment. Use when simplifying, hardening, optimizing, or reducing repeated tool use in SKILL.md workflows.
---

# Skill Lowering

Lower high-level Agent Skill instructions into deterministic commands and scripts without changing the skill's observable behavior.

## Core principle

Move only mechanical work out of the agent. Keep semantic interpretation, trade-off decisions, current research, and human approval in the agent workflow.

The target is not to eliminate the agent. The target is to make the boundary between deterministic execution and agent judgment explicit.

## Inputs

Obtain:

- the target skill directory
- repository or runtime constraints, when available
- whether changes should be proposed only or applied
- whether adding dependencies is allowed

Do not assume that globally installed commands are available. Inspect the target repository and environment first.

## Workflow

### 1. Inventory the target skill

Run:

    python3 scripts/inventory.py <target-skill-directory> --format json

Read the complete target `SKILL.md` and any files it references. The inventory is structural evidence; it does not replace semantic reading.

### 2. Decompose the workflow

Split the target skill into atomic operations. Each operation should have one primary effect and an identifiable input and output.

For every operation, record:

- source file and line range
- original instruction
- required inputs
- produced outputs
- external state read or changed
- failure behavior
- ordering dependencies

Do not lower an entire section as one operation when it contains multiple decisions or side effects.

### 3. Classify each operation

Use exactly one primary classification:

| Classification | Meaning |
|---|---|
| `existing-command` | A repository command, project dependency, or established CLI can implement the behavior. |
| `bundled-script` | Deterministic code is appropriate, but no safe single command exists. |
| `keep-agent` | Semantic interpretation, synthesis, prioritization, or open-ended judgment is essential. |
| `human-gate` | Authorization, irreversible impact, or policy requires explicit human approval. |
| `unsupported` | Required behavior or equivalence cannot be established. |

Use `references/lowering-model.md` for the decision procedure.

### 4. Resolve replacements

Search in this order:

1. existing scripts and package commands in the target repository
2. already-declared project dependencies
3. operating-system or language-runtime standard tools
4. an established external CLI allowed by the target's compatibility constraints
5. a new bundled script with minimal dependencies
6. retain the operation as agent work

Use `references/command-catalog.md` as a candidate catalog, not as evidence that a command is installed or appropriate.

Prefer an existing project command over introducing a new tool. Do not add a dependency solely to replace a trivial one-line operation unless it materially improves correctness or portability.

### 5. Define the behavior contract

Before proposing a replacement, specify:

- accepted inputs and validation
- output format
- exit codes
- working directory
- timeout or termination behavior
- ordering and sorting rules
- side effects
- idempotency expectations
- behavior when the command is unavailable

Represent commands as executable plus argument arrays. Do not represent untrusted values by concatenating a shell command string.

### 6. Produce and validate a lowering plan

Produce both:

- a human-readable summary
- JSON conforming to `schemas/lowering-plan.schema.json`

Every proposed lowering must include evidence for behavioral equivalence and a verification method. Confidence alone is not evidence.

Validate the generated plan before using it:

    python3 scripts/validate_plan.py <lowering-plan.json>

The validator checks schema-like structure plus cross-field invariants that JSON Schema alone cannot express, including summary counts, classification/replacement agreement, stable operation ordering, unique IDs, safe relative paths, and non-overlapping source ranges.

Default to proposal-only mode. Apply changes only when the user requested implementation or the surrounding task explicitly authorizes repository edits.

### 7. Render or apply safe transformations

For an eligible single-line Markdown list instruction, generate a review-only patch:

    python3 scripts/render_patch.py <target-skill-directory> <lowering-plan.json> --output lowering.patch

Then inspect it and run:

    git apply --check lowering.patch

The renderer never modifies source files. It rejects stale source text, multi-line source ranges, non-list instructions, path traversal, invalid plans, and overlapping operations. Perform complex semantic rewrites directly and explain why they could not use the deterministic renderer.

When applying an approved lowering:

- place reusable deterministic code under `scripts/`
- keep the script interface narrow and documented
- make output machine-readable when the agent must consume it
- update `SKILL.md` to state when and how to invoke the command
- remove duplicated procedural detail from `SKILL.md`
- preserve the original semantic review step where required
- retain a fallback for unavailable optional tools

Do not silently replace a meaningful review with a successful exit code from a narrow linter.

### 8. Verify

Perform the strongest available verification:

1. syntax and schema validation
2. unit tests for generated scripts
3. fixtures covering success, empty input, malformed input, and failure
4. comparison of original and lowered outputs on the same fixtures
5. review of side effects and changed files

If the original behavior cannot be executed reproducibly, state that equivalence is reasoned rather than demonstrated.

## Lowering constraints

Never lower these solely into a command:

- choosing the best design under incomplete requirements
- assessing whether prose is persuasive, clear, or appropriate for an audience
- current web research or source credibility assessment
- security acceptance decisions
- destructive actions or publication without an approval boundary
- resolving contradictory stakeholder intent

A command may gather evidence for these operations, but the final judgment remains agentic or human-gated.

## Command safety

- Use argument arrays where the host supports them.
- Quote paths when showing shell examples.
- Reject path traversal when a generated script writes files.
- Set explicit encodings and stable sort order.
- Avoid network access unless it is part of the declared behavior.
- Do not execute a discovered repository script before inspecting it.
- Treat exit code `1` according to each command's documented semantics; it is not universally an execution failure.

## Output

Summarize:

1. operations found
2. proposed `existing-command` lowerings
3. proposed `bundled-script` lowerings
4. operations retained as `keep-agent`
5. human approval boundaries
6. files changed or proposed
7. verification completed and remaining uncertainty

Sort operations by source path, then source line, then operation ID.
