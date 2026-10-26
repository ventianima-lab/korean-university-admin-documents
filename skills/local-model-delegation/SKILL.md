---
name: local-model-delegation
description: Delegate a bounded task to a user-specified provider and model through an existing local model gateway. Use when the user names an external model for design, writing, or code work and the ordinary subagent catalog does not expose that exact provider/version. Do not use for automatic model substitution or gateway setup.
---

# Exact model delegation

A family nickname is not a provider/version identifier. A tool catalog can list one provider's model while the existing local gateway exposes another provider's newer model. Never substitute the visible family member merely because its nickname matches.

1. Preserve the user's latest provider, model version, and requested effort as a delegation contract. Resolve an ambiguous nickname from current conversation and verified local history before asking the user. A correction replaces the earlier assumption.
2. Inspect the existing runtime configuration or a previously verified adapter to locate the gateway. Query its live model catalog and select the exact observed identifier. A missing entry in the native subagent list is not proof that the gateway lacks it. Do not modify credentials, provider accounts, model catalogs, or default settings to perform ordinary delegation.
3. Use a tool that accepts that exact identifier, or the existing gateway's documented request interface. Do not submit an unsupported native-tool override and do not silently switch provider or version. If the exact route is unavailable, report the concrete failure and seek a substitution decision only when needed.
4. Give the model a bounded brief with verified facts, output schema, edit limits, and a task label prefixed with the actual model identifier and effort. Keep private records and credentials out of public examples. Pass credentials transiently without logging them. Keep unattended console helpers hidden.
5. Save a private receipt containing requested model, returned model/provider when exposed, response identifier, completion status, and usable output location. The returned identifier may omit the routing prefix; verify it with the selected gateway route. A model-list entry or successful HTTP status alone does not prove completed model work.
6. Apply and independently verify the returned artifact against the user's facts and requested format. For document design, preserve native editable content and perform the format-specific visual and structural checks. Report design advice as advice; claim file creation only after the file exists and opens.

## Completion gate

Before saying that a named model performed the task, check all three: the request used the exact user-selected route; the response completed with usable output; and the delivered result incorporates that output. Preserve the receipt privately. If any check fails, describe that boundary instead of attributing work to a different model.
