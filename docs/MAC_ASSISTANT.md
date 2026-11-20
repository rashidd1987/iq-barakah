# Mizan: local Mac executor

The existing `@mizan_project_reports_bot` remains the only Telegram listener.
`/mac <task>` queues a task for the owner's Mac. `/macstatus` shows recent tasks
and the last poll. Existing reminders, approvals and Codex PR workflows are unchanged.

## Scope

OpenJarvis with Ollama `qwen3.5:2b-q4_K_M` handles Russian texts, plans, calculations,
and draft code. It can read/write text files only in `~/Documents/Mizan Assistant`.
It has no shell, deploy, messaging or production tools. Copy relevant source
files into `inbox/`; documents go to `outbox/` and code drafts to `code/`.
Use Mizan's existing Codex agent tasks for changes to real repositories and PRs.
PDF/DOCX parsing, voice input for `/mac`, and file delivery as Telegram attachments
are not included in this first integration. Text results are returned in Telegram.

## Install and pair

1. Install OpenJarvis and Ollama, pull `qwen3.5:2b-q4_K_M` and verify an actual file task.
2. Run `~/.openjarvis/.venv/bin/python scripts/install_mac_worker.py` to copy the
   runtime and prepare the workspace. This does not enable polling or autostart.
3. Review and deploy the server changes through the existing Reports approval
   procedure. Use a full immutable commit SHA; keep existing production approval.
4. In a private Terminal run the installed `install_mac_worker.py --pair` with
   the application's verified HTTPS origin. It generates a separate secret locally.
   Store that value as `MAC_WORKER_SECRET` in the Reports application's secret
   variables. Never put the secret in Git, chat, arguments or logs. The helper
   displays it only in the owner's Terminal for manual transfer.
5. After the server accepts the secret, the helper installs a user LaunchAgent
   `ru.mizan.mac-worker`. No Telegram bot token is installed on the Mac.
6. Verify `/macstatus`, then `/mac сохрани проверочный план в outbox/test.md`.
   Check both the actual file and the reply before claiming Telegram readiness.

Mac must be awake, online and logged in. Ollama must run. This setup does not
change sleep settings or keep the laptop awake. Worker logs are in
`~/.openjarvis/.state/mac-worker.log`; per-task state is private under `mac-jobs/`.

## Reliability and security

- Telegram enqueue is owner-only and private-chat-only. No HTTP enqueue route exists.
- Worker API requires its own 32+ character bearer secret; no access if unconfigured.
- Mac only makes outbound HTTPS requests. Redirects are refused; no inbound port.
- SQLite transactions prevent parallel claims and duplicate Telegram deliveries.
- Started jobs are never automatically requeued. Local completed results survive
  network errors and are reported again without repeating model/file execution.
- A crash or timeout reports `unknown`; inspect files before manually resubmitting.
- Result notifications have at-least-once delivery; Telegram outages may duplicate
  a notification, but do not repeat task execution.
- There is one owner Mac. The shared worker secret grants access to queued Mac
  tasks only, not to approval decisions. Rotate it on both sides if exposed.

To disable: unload `ru.mizan.mac-worker` with `launchctl bootout` and remove or
rotate `MAC_WORKER_SECRET` server-side. Do not delete the job database during
recovery: it is the duplicate-execution record.

## Checks

Run `python -m unittest report_bot.test_mac_queue report_bot.test_mac_bridge
report_bot.test_mac_worker report_bot.test_report_bot report_bot.test_agent_safety
report_bot.test_release_safety` with Reports dependencies. HTTP tests require
permission to bind a localhost socket. A real local-model and Telegram smoke
are separate deployment checks.
