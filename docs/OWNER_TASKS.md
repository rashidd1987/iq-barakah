# Owner tasks

Mizan Project Reports keeps owner tasks in
`REPORT_BOT_DATA_DIR/owner_tasks.json`. The file is written atomically and
contains both current task state and a journal of create/complete events.

## Telegram flow

1. Select the project with `/use project_key`.
2. Send `/newtask` or tap `➕ Поручение`.
3. Enter one line:

   `What to do | YYYY-MM-DD | How completion will be verified`

4. Complete the task with its `✅ Выполнено` button or `/done task_id`.

Useful lists:

- `/tasks` — all open tasks;
- `/today` — tasks due today and overdue tasks.

Only Telegram IDs from `OWNER_TELEGRAM_IDS` can read or change tasks.
Completing the same task repeatedly is safe and does not duplicate journal
events.

## Scope of this release

This is the persistence and manual-control foundation. Scheduled morning and
evening briefs will read from the same store in a later release. This release
does not modify GitHub release approvals, monitoring, production deployment,
or project knowledge.
