# Skill Lowering

**Skill Lowering** is a meta-skill that analyzes an existing Agent Skill and moves deterministic or mechanical work into existing CLI commands or bundled scripts. Semantic judgment remains in the agent workflow.

The intended repository name is `skill-lowering`.

## Purpose

A Skill often mixes several kinds of work:

* deterministic discovery, parsing, validation, sorting, and transformation
* semantic analysis and synthesis
* approval-sensitive side effects

Skill Lowering identifies those boundaries and produces a behavior-preserving refactoring plan. It does not treat every instruction as automatable.

## Contents

* `SKILL.md` — lowering workflow and safety constraints
* `scripts/inventory.py` — deterministic structural inventory of a target Skill
* `schemas/lowering-plan.schema.json` — machine-readable lowering plan contract
* `references/lowering-model.md` — classification and rejection rules
* `references/command-catalog.md` — candidate CLI catalog
* `tests/` — standard-library unit tests and fixture

## Usage

Install this directory as an Agent Skill, then ask the agent to analyze a target Skill, for example:

> Analyze `./skills/code-review` with Skill Lowering. Produce a lowering plan, but do not modify files.

The agent first runs:

```
python3 scripts/inventory.py ./skills/code-review --format json
```

It then reads the target Skill, classifies atomic operations, and emits a lowering plan conforming to the bundled JSON Schema.

## Development

Requires Python 3.10 or later and no third-party packages.

```
python3 -m unittest discover -s tests -v
```

## Status

Experimental initial implementation. The deterministic inventory is implemented; semantic classification and source-to-source patch generation are intentionally performed by the meta-skill until their contracts stabilize.
