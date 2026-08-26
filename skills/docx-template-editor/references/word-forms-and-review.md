# Word forms, review and privacy

## Forms

Use Word content controls when the source already uses them. Preserve aliases, tags, locking behavior, placeholder text, checkbox state and repeating-section structure. Size response areas according to expected content.

## Comments and tracked changes

Keep comment anchors tight. Preserve author, date, resolved status and replies when reviewing an existing file. For tracked changes, retain `w:ins` and `w:del` until the user requests acceptance or rejection. Rendered pages do not reliably prove comment structure, so inspect the OOXML parts as well.

## Tables

Use tables only for genuine row-and-column data or forms. Preserve `tblGrid`, `tblW`, `tcW`, merge structure, cell margins and repeated header rows. Avoid fixed row heights when text may wrap.

## Privacy

Before public delivery, inspect core properties, custom properties, comments, revision identifiers, hidden text, tracked deletions, embedded files and image metadata. Remove only what the user requested and report what was scrubbed.
