# shift_handoff/references -- plant reference material (Layer 3)

One job: the plant-specific material the stages read, configured once.

## What's here
- `glossary.md` -- your terms and abbreviations (read by 02_summary).
- `format.md` -- your brief layout (read by 04_brief).

## Rules
- Each run copies these into its own `references/` folder, so old runs stay reproducible.
- If a file is missing (e.g. in the backend Docker image), the stage uses its built-in default.
