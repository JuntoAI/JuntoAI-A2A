---
inclusion: manual
description: "When triggered after a spec is moved to .kiro/specs/DONE, reads the spec's requirements.md, derives the ship date from the tasks.md last-edit timestamp, and prepends a new feature entry to both CHANGELOG.md and the frontend release notes page. No versions — just a flat stream of shipped features ordered newest-first."
---

A spec was just completed. Do the following:

1. Identify the newly completed spec folder under .kiro/specs/DONE/ (the one not yet in the CHANGELOG).
2. Read its requirements.md and tasks.md files.
3. Determine the ship date by running `stat -c '%y' .kiro/specs/DONE/<spec>/tasks.md` and extracting the YYYY-MM-DD date portion.
4. Update CHANGELOG.md:
   - Prepend a new entry right after the header block (below the `---` separator), using the format:
     ```
     ## <Spec Title> (Spec <NNN>) — YYYY-MM-DD

     - bullet 1
     - bullet 2
     ```
   - Extract concise, technical bullet points from requirements.md summarizing what shipped.
5. Update frontend/app/release-notes/page.tsx:
   - Add a new object at the START of the FEATURES array with `title`, `specId`, `date`, and `items` fields.
   - Match the existing data structure and code style exactly.
6. Keep the tone concise and technical — match the style of existing entries.
7. Do NOT create any new files or summaries. Only edit the two existing files.
8. Commit and push the updated changelog.md and /release-note/page.tsx
