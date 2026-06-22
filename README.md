# Skill Lowering

**Skill Lowering** is a meta-skill that analyzes an existing Agent Skill and moves deterministic or mechanical work into existing CLI commands or bundled scripts. Semantic judgment remains in the agent workflow.

Repository: `skill-lowering-skill`

## Purpose

A Skill often mixes several kinds of work:

* deterministic discovery, parsing, validation, sorting, and transformation
* semantic analysis and synthesis
* approval-sensitive side effects

Skill Lowering identifies those boundaries and produces a behavior-preserving refactoring plan. It does not treat every instruction as automatable.

## Contents

* `SKILL.md` — lowering workflow and safety constraints
* `scripts/inventory.py` — deterministic structural inventory of a target Skill
* `scripts/validate_plan.py` — structural and cross-field validation for lowering plans
* `scripts/render_patch.py` — review-only unified diff generation for safe single-line lowerings
* `schemas/lowering-plan.schema.json` — machine-readable lowering plan contract
* `references/lowering-model.md` — classification and rejection rules
* `references/command-catalog.md` — candidate CLI catalog
* `tests/` — standard-library unit tests and fixture

## Usage

Install this directory as an Agent Skill, then ask the agent to analyze a target Skill, for example:

> Analyze `./skills/code-review` with Skill Lowering. Produce a lowering plan, but do not modify files.

Create the structural inventory:

```bash
python3 scripts/inventory.py ./skills/code-review --format json > inventory.json
```

After the agent produces `lowering-plan.json`, validate both its shape and semantic invariants:

```bash
python3 scripts/validate_plan.py lowering-plan.json
```

Generate a review-only patch for mechanically lowered single-line list instructions:

```bash
python3 scripts/render_patch.py \
  ./skills/code-review \
  lowering-plan.json \
  --output lowering.patch

git apply --check lowering.patch
```

`render_patch.py` never modifies the target Skill. It rejects stale source text, overlapping source ranges, unsafe paths, multi-line replacements, and non-list instructions. Complex rewrites remain the meta-skill's responsibility.

## Development

Requires Python 3.10 or later and no third-party packages.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_plan.py examples/lowering-plan.example.json
```

## Status

Experimental. Structural inventory, plan validation, and conservative review-only patch rendering are implemented. Semantic operation decomposition and command selection remain agentic by design.
