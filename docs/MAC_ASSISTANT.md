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

## Voice tasks

Send a Telegram voice message to the Reports bot, check its transcript, choose
«Выполнить на Mac», then «Запустить на Mac». No due date is required. Only the
owner in a private chat can enqueue it. The original transcript is the task;
transcription uses the existing OpenAI integration. The Mac uses its existing
scoped file tools and the normal durable queue/result notifications. Cancelled,
expired, replaced or duplicate confirmations do not create extra jobs.

## IQ Barakah project reports

The Mac runtime recognizes a request to check/audit/report IQ Barakah (including
`IQBarak` from speech recognition). It reads a fresh, fixed GitHub `main` snapshot
in `~/.openjarvis/projects/iq-barakah.git`, outside Documents and outside the
model's writable workspace. No GitHub token is installed for the public snapshot.
It produces an independently verified Markdown report in the configured outbox
and returns the report through the existing Telegram queue. No Amvera update is
needed for this local capability.

Checks: bounded Python AST syntax and package.json validation, exact-commit
Quality checks status from GitHub, and HTTP availability of iq-barakah.ru.
A successful report does not mean the application is free of bugs. Source is not
executed, dependencies are not installed, and local dirty changes, private CRM
records, production databases and full user flows are not inspected. Refresh
failures are explicit and never reuse an old snapshot as current. Secret/env,
data/vendor files and symlinks are excluded from source scanning. Source lines
and provider error payloads are not sent to Telegram.

Mail, social accounts, calendars and task stores require separately implemented
connectors and owner authorization; Codex app connections are not automatically
available to the background Mac worker.

### Mac HTTPS transport

During the owner smoke test, Python TLS handshakes intermittently timed out while
macOS curl could reach the same verified HTTPS origin. The worker uses the built-in
`/usr/bin/curl` SecureTransport client with certificate validation, HTTPS-only
protocols, no redirects, no user curl config, bounded retries, response size and
time limits. Bearer credentials and result payloads are supplied through stdin,
never process arguments. Existing queue idempotency and saved-result recovery
remain in force. Network outages can still delay a result.

## Account readers (authorization pending)

The local worker has explicit Gmail and Instagram read-only routes. A connected
Gmail app in Codex does not authorize the background worker. Neither account is
considered connected until its local helper completes a real API capability check.

- Gmail: user creates a Desktop OAuth client, enables Gmail API, adds only the
  owner's account as a test user, then runs `connect_gmail.py --client PATH`.
  The helper binds only to loopback, verifies OAuth state and PKCE, requests only
  gmail.readonly and verifies rashidd1987@gmail.com. Credentials stay outside the
  model workspace with private permissions. The first reader shows unread inbox
  subjects/senders only (up to 10), hiding security-code subjects. Message bodies
  and attachments are not currently included.
- Instagram: existing Meta app IQ Barakah Publisher can supply an authorized
  Facebook Login user token with instagram_basic, instagram_manage_insights,
  pages_show_list and pages_read_engagement for the linked Page. The helper
  defaults to Facebook Login; an Instagram Login token can be selected explicitly
  only if its Insights capability is verified. The owner runs
  `connect_instagram.py` and pastes the token in a hidden local Terminal prompt.
  It checks @rashidiqmizan and an actual Insights request before saving. The reader
  reports daily reach for seven completed UTC days; it does not sum daily uniques.
- Both readers have fixed provider hosts, no redirect following, no write endpoints,
  and return a clear failure when authorization is absent. Mail/post content never
  becomes an instruction to the agent. Tokens are not exposed in process args.
- Mizan personal tasks already use the server's owner-only voice flow: voice note,
  «Моя задача», review the draft and date, then «Создать». Select «Выполнить на Mac»
  for account reports, not for creating an owner task. A text create/complete smoke
  passed on 2026-11-22 (task PLd0H1u9); the voice creation smoke remains pending.
