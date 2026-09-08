---
name: fluent-korean
description: Draft, revise, polish, or review clear, natural, unambiguous Korean prose for documents, notices, announcements, reports, emails, messages, and the agent's substantive user-facing explanations. Use automatically whenever Korean composition or prose quality materially affects understanding or trust. Do not apply to source code, identifiers, logs, exact quotations, legal or template wording that must remain verbatim.
---

# Fluent Korean

Before drafting or revising substantive Korean prose, read [references/fluent-korean-not-coding.md](references/fluent-korean-not-coding.md) completely and apply it to the Korean deliverable.

- Apply this skill directly when its routing conditions are met. If the required reference cannot be read, do not improvise a replacement rule set or apply this skill.
- Preserve the user's facts, intent, terminology, template structure, and required tone. Do not invent missing facts.
- Treat explicit user instructions and deliverable-specific rules as authoritative when they differ from the general writing guide.
- Do not rewrite exact quotations, names, numbers, amounts, percentages, dates, times, units, code, identifiers, URLs, paths, filenames, legal or evidentiary wording, responsible parties, deadlines, actions, conditions, exceptions, template fields, tables, list order, or supplied text that the user asked to preserve verbatim.
- Before delivery, check that meaningful sentence elements, particles, predicates, and endings are present; replace unclear noun strings or unnecessary figurative wording; and avoid em dashes where a conjunction or colon is clearer.

## Administrative documents: no unsolicited annotations

- For administrative public letters, plans, expense forms, and reports, do not add agent-created memos, remarks, parenthetical caveats, workflow explanations, or attachment instructions that the user did not request. A blank 비고 cell is not an invitation to explain the drafting process.
- Use conversational background to choose accurate dates, quantities, and actual expenditure; do not automatically quote that background in the document. For example, delayed card receipt can change snack-expense calculations without adding a card-delay explanation or a “receipt to be attached manually” note.
- Preserve required official form wording and fill supported business fields normally. Leave unsupported values blank rather than inserting “확인 필요”, “추후 입력”, or similar agent notes into the document.
- If an additional explanation is necessary, first show its exact proposed wording and location to the user and ask whether to include it. Continue work that does not depend on that addition; do not treat elapsed time as consent.

## Automatic routing with complementary skills

- Use this skill as the drafting baseline for substantive Korean user-facing prose.
- Use `humanize-korean` in its inline mode only on unprotected prose with a concrete AI-style symptom. Skip it by default for official letters, notices, legal or evidentiary wording, and fixed templates.
- Use `grammar-checker` as a silent final pass for official or externally shared documents, notices, reports, emails, messages, and other Korean deliverables where visible errors would reduce trust.
- Use `style-guide` as a silent consistency pass only when the document type and organization or deliverable rules are sufficiently clear. Do not infer a number-unit convention from majority usage alone.
- The agent decides which complementary passes are warranted. Do not require the user to name a skill, and do not expose internal review reports unless the user asks for them or the task requires audit evidence.

This Codex adaptation uses the upstream non-coding output style from [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean) at commit `4e08ed63e9e2c7b603141c078d8e4720b0448935`. The upstream MIT license is preserved in [references/LICENSE.txt](references/LICENSE.txt).
