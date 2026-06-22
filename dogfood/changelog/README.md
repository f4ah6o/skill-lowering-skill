# Dogfood: changelog Skill

This case analyzes `f4ah6o/skills/skills/changelog/SKILL.md` as committed in
`04ea9d91e1f61bfbee1d121ccfebaeea0f0fc647`.

## Result

The workflow was decomposed into ten operations:

- five `bundled-script` candidates
- five `keep-agent` operations
- no safe existing command already declared by the target Skill
- no human-gated operation in the read-only review workflow

The mechanical candidates cover file-name selection, default heading structure,
release-section transformation, exact duplicate detection, and release-date
validation. Entry wording, category assignment, impact assessment, migration
instructions, and final review remain agentic.

## Files

- `target/SKILL.md` — captured target used for reproducible tests
- `lowering-plan.json` — validated lowering plan
- `expected.patch` — patch rendered for `op-009` only

The full plan intentionally includes multi-line and non-list operations that the
conservative renderer cannot rewrite. This exposed the need for operation-level
selection and led to the repeatable `--operation ID` option.

## Reproduce

```bash
python3 scripts/validate_plan.py dogfood/changelog/lowering-plan.json
python3 scripts/render_patch.py \
  dogfood/changelog/target \
  dogfood/changelog/lowering-plan.json \
  --operation op-009 \
  --output /tmp/changelog.patch
diff -u dogfood/changelog/expected.patch /tmp/changelog.patch
```
