# Credential-bearing notice evidence

Check notice bodies for authentication context before saving or displaying their attachments. A poster, screenshot, or embedded document image may repeat a shared account shown in text. Text redaction does not prove image safety. When a safe preflight path is unavailable, do not download or display the suspected image; record a security-related inspection gap without the credential values.

Apply redaction to structured string fields before serialization, file persistence, or tool output. For a paired `ID/PW` line, redact the whole credential-bearing line, not only the first whitespace-delimited field. Parse JSON and walk its values rather than applying line removal to serialized JSON, where escaped newlines and following fields can be damaged. Test both fields, next-line preservation, JSON round-trip, and idempotence with synthetic values.

Use [../scripts/redact_credential_text.py](../scripts/redact_credential_text.py) as a narrow paired-line helper, not a comprehensive secret detector. Other credential formats and image safety still require separate checks.

After an actual exposure, correct retained text and remove the offending saved image where authorized. Record the incident without secrets, distinguish current artifact cleanup from the irreversible earlier output, and request credential rotation from the account owner. Do not mark the original non-exposure requirement as passed merely because a later residual scan passes.
