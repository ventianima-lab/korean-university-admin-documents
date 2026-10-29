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

## Delayed messages, dates, and forms of address

- When a user explains that promised material is being sent late, open the message with a direct apology that acknowledges both the prior promise and the delay. Do not dilute the apology with excuses or shift responsibility to the recipient.
- Resolve relative deadlines such as “next Friday” against the client-provided current date and timezone, then write the exact calendar date in the deliverable. Preserve a user-specified relative phrase only when they explicitly want it shown.
- Treat a user-corrected honorific or form of address as protected wording. Replace every conversational occurrence consistently, while preserving official form names, role labels, and filenames unless the user also asks to change them.
- After an address correction, run `scripts/verify_message_address.py --require "<chosen address>" --forbid "<replaced address>" <saved TXT/EML files>` on every saved draft variant. It decodes MIME message bodies and excludes attachments; checking raw encoded EML is insufficient. Reopen a saved webmail draft and compare its visible body with the corrected local body before reporting readiness. Keep official role labels intact and stop at the user's requested sending boundary.
- When the user asks to remove a particular sentence or condition, delete it completely. Do not replace it with a paraphrase that recreates the same request, caution, or restriction unless mandatory legal, safety, or template wording requires disclosure.
- Distinguish planned details from confirmed details. When a date or time comes only from a draft or plan, identify it as the planned or proposed schedule instead of presenting it as a confirmed appointment.
- For document-request emails, separate forms the recipient must complete or sign from internal administrative forms. If an internal form needs no recipient signature or confirmation and can be completed from documents already being requested, omit it from both the attachment list and the request list to avoid redundant transmission of personal or financial data. Before handoff or sending, verify that every attachment still appears in the body and that every attachment named in the body is actually included.

## Document requests include the relevant parties' permission

- Treat a user's request to write or revise a document as already cleared with the named vendor or party for the requested preparation, supplied names, and requested use of supplied seals or signatures. Do not ask whether permission was obtained or request that same permission again.
- Use facts supplied by the user as source facts, including an actual quotation date or the party's requested stamp use. Look up existing context and files before asking for missing factual values; a factual question must not become a repeated permission check.
- Keep preparation within the requested scope. Submission, sending, and unrelated external actions require their own task instruction; permission to prepare a document does not invent missing dates, amounts, approval states, or signatures.

## Administrative documents: no unsolicited annotations

- For administrative public letters, plans, expense forms, and reports, do not add agent-created memos, remarks, parenthetical caveats, workflow explanations, or attachment instructions that the user did not request. A blank 비고 cell is not an invitation to explain the drafting process.
- Use conversational background to choose accurate dates, quantities, and actual expenditure; do not automatically quote that background in the document. For example, delayed card receipt can change snack-expense calculations without adding a card-delay explanation or a “receipt to be attached manually” note.
- Preserve required official form wording and fill supported business fields normally. Leave unsupported values blank rather than inserting “확인 필요”, “추후 입력”, or similar agent notes into the document.
- Default an otherwise empty 비고/remarks cell to blank. Populate it only with the minimum source-supported content explicitly requested there or required by the applicable official form/instructions. Do not fill space with repeated main-text facts, obvious explanations, drafting status, self-check notes, or rejected explanations moved from another field. At handoff, every newly populated remarks cell must have that specific basis; otherwise omit the addition. Preserve existing user-entered or mandatory remarks rather than clearing them under this rule.
- Omit unrequested explanations instead of creating an extra approval question for them. Report a material missing fact briefly in the conversation when needed; preserve explanations required by the official form or explicitly requested by the user.
- For a user-requested activity or case report, use the supplied plan, photographs and other reliable sources to develop the activity’s purpose, the participants’ contribution, observed results and prospective effects. Reflect the user’s stated educational or community significance; label event-wide attendance as event-wide, and do not invent individual roles, measured effects or funding links. Fill a shared role only when the user or evidence supports it.
- When the user supplies participants’ motivation or explains how successive activities grew, write that account into the requested report rather than returning an outline or asking the user to supply the prose. Connect the stated need, learned skills, each actual activity, supported responses, and next steps; preserve changes in audience or setting instead of flattening them into one event. For a scored case report, map the actual judging criteria to these sections and check that each claimed result has evidence, each future measure reads as a proposal, and no unsupported funding link or measured therapeutic effect is introduced merely to fill a scoring gap.
- Before adding an AI-use disclosure or other drafting-process explanation, distinguish the activity or output being reported from the assistance used to prepare the form and check the actual notice’s scope. Follow the user’s explicit removal and any reported confirmation; do not reinsert rejected wording or its paraphrase. Preserve mandatory protected template text and identify any still-unresolved source conflict separately rather than presenting a disputed annotation as an established requirement.
- Apply this check to 목적, 주요내용, 안건, 일정 and narrative bullets, not just 비고. Meeting purposes describe the supported business to be discussed; a budgeted meal does not make meal provision a meeting objective. Do not add meal/refreshment provision, purchasing, payment, or evidence-handling explanations to those fields merely to justify an expense. Keep required expense details in the official costing or expenditure fields; preserve an explicitly requested logistics field or mandatory template wording.
- Before delivery, compare every populated purpose, agenda, schedule, remarks, attachment, and narrative field against the source template and requested changes. Each agent-added sentence must have a supported purpose and belong in that field. New process notes, caveats, drafting status, manual-attachment instructions, and logistics inserted as meeting objectives fail this check even when the budget arithmetic is correct. If the user rejects an explanation, reject paraphrases of the same explanation too. Existing wording is not automatically permission to add another annotation.
- For purchase or expense packets in any document format, read [../hancom-hwpx-documents/references/procurement-forms.md](../hancom-hwpx-documents/references/procurement-forms.md) before filling. Use its saved-field check and `style-guide`'s complete-column gate after saving, including for editable Word quotations.

## External submission emails

- For a submission from a department or office, identify both the organization and the submitting unit in the subject or opening sentence, using verified names. Do not imply that one unit's records represent the entire organization.
- Keep the covering email to the sender, requested material, and submission purpose. Apply the no-unsolicited-annotations check to the email body as well as the attachment: omit internal system names, drafting methods, verification steps, and accounting-process explanations unless the user or submission instructions require them. A choice used to prepare the attachment does not itself justify explaining that choice to the recipient. If the user rejects an unnecessary explanation, delete it rather than replacing it with a plainer version of the same explanation.
- Before sending, inspect the actual subject and rendered or MIME-decoded body for the organization and submitting unit, and check every extra explanatory sentence against the user's request or submission requirements. Matching attachment bytes alone does not satisfy this check. A correction to already-sent wording does not authorize a follow-up or replacement email.

## Automatic routing with complementary skills

- Use this skill as the drafting baseline for substantive Korean user-facing prose.
- Use `humanize-korean` in its inline mode only on unprotected prose with a concrete AI-style symptom. Skip it by default for official letters, notices, legal or evidentiary wording, and fixed templates.
- Use `grammar-checker` as a silent final pass for official or externally shared documents, notices, reports, emails, messages, and other Korean deliverables where visible errors would reduce trust.
- Use `style-guide` as a silent consistency pass only when the document type and organization or deliverable rules are sufficiently clear. Do not infer a number-unit convention from majority usage alone.
- The agent decides which complementary passes are warranted. Do not require the user to name a skill, and do not expose internal review reports unless the user asks for them or the task requires audit evidence.

This Codex adaptation uses the upstream non-coding output style from [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean) at commit `4e08ed63e9e2c7b603141c078d8e4720b0448935`. The upstream MIT license is preserved in [references/LICENSE.txt](references/LICENSE.txt).
