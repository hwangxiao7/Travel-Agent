# Conventions & Task-Completion Workflow

## MANDATORY: update docs in the same commit (repo rule, alwaysApply)
On any **substantive change** (new feature, enhancement, refactor, bug fix, prompt/model
optimization, dependency/architecture change) you MUST update docs in the **same commit** as the
code. Never commit code and leave docs "for later". See `.cursor/rules/document-and-commit-updates.mdc`.

Each doc update must state:
1. What tech / approach (libraries, models, APIs, algorithms, design patterns).
2. What was improved — the change, the motivation, expected benefit (perf / cost / token / accuracy / maintainability).
3. Scope of impact — modules/files touched, behavior change, compatibility/migration notes.

Where to write:
- Prepend a dated entry to `docs/CHANGELOG.md` (newest on top).
- If architecture / tech-selection changed, also update `docs/架构技术选型.md` / `docs/项目技术分析.md`.

CHANGELOG entry format:
```markdown
## YYYY-MM-DD — short title
- 技术/方案:...
- 改进:...(motivation + expected benefit)
- 影响范围:<files / modules changed>
```

## Commit rules
- Docs + related code in the **same commit**; message explains what/why.
- Only `push` when the user explicitly asks.
- Only stage files touched by this change — do not sweep unrelated / in-progress files.

## General guardrails
- Graceful degradation: features must still work with missing API keys / no LLM.
- Do not hardcode internal company gateways; stay OpenAI-compatible.
- No internal tokens in the repo. Devices must not use public tunneling tools.
