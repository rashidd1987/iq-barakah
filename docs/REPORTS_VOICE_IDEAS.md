# Reports voice inbox and idea base

Mizan Project Reports accepts Telegram voice messages from IDs listed in
`OWNER_TELEGRAM_IDS`. Audio is downloaded in memory, limited to 20 MB, sent to
the configured OpenAI transcription API, and then discarded. The bot stores no
audio file.

After transcription the owner must choose one explicit action:

- save the transcript as an idea;
- prepare an owner task draft;
- prepare a Codex task draft;
- cancel without saving.

Task drafts require a due date in the voice note. They are shown with a second
confirmation button before being created. A Codex task still uses the existing
PR-only workflow and is not dispatched until the owner presses the separate
`Передать Codex` confirmation. Voice input never changes `main` or production.

## Persistent ideas

Ideas are written atomically to `REPORT_BOT_DATA_DIR/ideas.json`. Production
uses the persistent `/data` mount, so ideas survive application restarts and
deployments. Each idea records its text, active project, source, timestamp, and
owner ID. Audio is not persisted.

Commands:

- `/newidea` — enter an idea as text (voice can be sent at any time);
- `/ideas` — show the 20 newest ideas;
- `/ideasexport` — download all ideas as Markdown and JSON.

The Markdown export is suitable for upload as context to ChatGPT, Claude,
Gemini, or another AI. JSON is intended for future automations and migration.

## Configuration

`OPENAI_API_KEY` is required for voice transcription and task extraction. The
key is read from environment secrets and is never included in logs or exports.
Optional model overrides are `OPENAI_TRANSCRIBE_MODEL` and `OPENAI_MODEL`.
