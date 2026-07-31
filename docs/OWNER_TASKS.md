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
- `/morning` — an on-demand owner brief across projects, tasks, and approvals.
- `/plan` — propose up to three concrete actions; only selected proposals become
  tasks and repeated taps cannot create duplicates.

The same brief is sent once a day at `MORNING_REPORT_HOUR` in
`REPORT_TIMEZONE`. The default is 09:00 Europe/Moscow. It prioritizes confirmed
site outages, failed workflows, pending owner decisions, overdue tasks, and
tasks due today. The last-send date is stored separately, so a container restart
does not duplicate the morning message.

Only Telegram IDs from `OWNER_TELEGRAM_IDS` can read or change tasks.
Completing the same task repeatedly is safe and does not duplicate journal
events.

## Scope of this release

This release does not modify GitHub release approvals, production deployment,
or project knowledge. The morning brief reads approvals and tasks but cannot
approve, complete, or execute them automatically.
