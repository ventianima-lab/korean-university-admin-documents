---
name: korean-admin-writing
description: Draft and polish Korean university administrative prose while preserving facts, legal wording, template labels, dates, amounts, deadlines, actions, exceptions, and list or table order. Use for official letters, plans, reports, notices, emails, messages, and form narrative fields.
---

# Korean administrative writing

Apply the following route only to prose that is not protected by a supplied form, quotation, legal basis, evidence record or exact user wording.

1. Use `fluent-korean` as the drafting baseline.
2. Use `style-guide` when the document type and organization or template rules are clear.
3. Use `humanize-korean` only when unprotected narrative prose shows a concrete translation-like or mechanical AI-style symptom. Skip it by default for fixed forms, official grounds, legal wording and short notices.
4. Use `grammar-checker` last and change only clear errors.

Do not normalize numbers, units, dates, list markers or links without an explicit governing rule. When rules conflict, preserve the source and report `UNIT_RULE_CONFLICT`. Return the polished result directly unless the user requests a detailed language audit.
