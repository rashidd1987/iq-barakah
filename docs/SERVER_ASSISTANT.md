# Server assistant release — 2026-11-24

## Scope

The existing Reports bot remains the only Telegram listener. New Gmail/Instagram
read requests and read-only IQ Barakah project checks target `cloud`, other jobs
still target `mac`. Existing running jobs keep their executor and claim token.
The default is enabled; `CLOUD_READERS_ENABLED=0` routes new jobs to Mac for rollback.
The narrow server executor never loads Ollama and cannot modify mail/social data.
Owner task storage and production approvals are unchanged.

## Reliability

The jobs database migrates additively (`target` defaults to `mac`). Each executor
has its own serial queue; a sleeping Mac cannot block server reads. Transactions
prevent duplicate claims. Worker identity is fixed to `owner-mac` or `cloud-readers`
and is checked on recovery/result submission. Workers use the existing owner
worker secret; they share that trust boundary, not independent tenant isolation.

Private started/result files survive network interruption and service restarts.
A completed result is resent without executing the read or TTS again. An interrupted
execution reports `unknown`, releases the queue, and is not automatically retried.
No lease takeover or automatic repetition of writes exists. Only one instance of
each worker may run; the OS file lock and systemd enforce the server instance.

## VPS

Existing server: 77.233.214.199. Measured: 1 CPU, 957 MiB RAM, ~9 GiB disk free.
Code: `/opt/mizan-worker`; private state: `/var/lib/mizan-worker/.openjarvis`.
Systemd user: `mizan-worker`; no interactive login, no root runtime, no Telegram
bot token. Existing account credentials must only be transferred with explicit
owner consent. Config and credentials mode 600; state directories mode 700.

Install `piper-tts==1.8.0` in the dedicated venv; download `ru_RU-denis-medium`.
Model card documents CC0 dataset/base; retain the card and engine license.
Service has CPU/memory limits and restarts automatically. It must not be started
before the new Reports API is deployed: an old API ignores worker identity.

## Voices

- Default / Оникс: free server Piper Denis for server jobs, macOS Yuri for Mac jobs.
- Джарвас or `/jarvas`: existing paid Onyx generation on Reports, no extra worker charge.
- `/mac`: text only. Voice transcription remains a separate paid API operation.
- The short free acceptance clip is already bundled on Reports and needs no Mac.

The exact Yuri voice is not portable to Linux. No paid voice fallback is automatic.

## Release and rollback

1. Merge/reconcile the deployed assistant branch with current main, run all tests.
2. Stage runtime and test APIs/TTS privately without starting polling.
3. Record exact source SHA and pass CI. Obtain the normal Telegram production
   approval for that SHA before updating the scoped Amvera Reports mirror.
4. Preserve production-only modules, config and persistent `/data` files.
5. Verify Reports health and new API, then enable `mizan-cloud-worker.service`.
6. Stop the Mac worker temporarily; send real owner Gmail/Instagram voice requests.
   Require server job ID, live API result, Telegram text and playable audio.
7. Restart the server worker, verify no duplicate execution and independent queues.
8. For rollback stop the server worker first, disable routing for new jobs, and
   inspect pending cloud jobs before explicitly moving any back to Mac. Do not
   reset running jobs, delete the database, or run two Telegram pollers.

## Remaining work

Google OAuth Testing lifetime and Instagram token rotation need separate console
verification. OpenAI gpt-4o-mini-tts replacement is due before 2027-01-06.
No full-project rewrite, database merge, file deletion, paid plan upgrade or model
migration is included in this bounded server-reader release.

## Verification status

Local initial suite: 156 tests passed, including migration, executor isolation,
crash recovery and result idempotency. Live server credentials/TTS and Telegram
proof must be recorded after verification; staging does not establish readiness.
