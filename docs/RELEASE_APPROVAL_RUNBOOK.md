# PWA production approval runbook

## Safety invariants

These rules must remain true:

1. A verified immutable PWA build is created before an approval request.
2. Production uses one shared approval record linked to the GitHub workflow run.
3. The owner may decide in Telegram or in GitHub; the first terminal decision wins.
4. Telegram approval or rejection reviews the native GitHub `production` deployment.
5. A GitHub decision updates the Telegram message and removes its buttons.
6. No download, SSH configuration, upload, or health check starts before approval
   synchronization succeeds.
7. Repeated decisions are idempotent and cannot reverse the first decision.
8. `production` keeps its GitHub Environment required-review protection.

CI enforces the workflow structure through
`report_bot/test_release_safety.py`. Do not bypass the `Release safety` check.

## Normal release

1. Start `Release PWA` with `target=production` and
   `confirm_production=RELEASE`, or use the report bot release command.
2. Wait for the Telegram and GitHub approval surfaces.
3. Approve or reject in either place.
4. Confirm that the second surface shows the same terminal decision.
5. For approval, verify the workflow health check before announcing success.

## Safe cancellation

Reject in Telegram or GitHub. A rejected production job must contain no deploy
steps. Cancelling a workflow is also safe before the environment approval.

## Required configuration

- GitHub Environment: `production`, required reviewer enabled.
- GitHub token repositories: only the explicitly monitored repositories.
- GitHub token permissions: `Metadata: read`, `Actions: read/write`,
  `Deployments: read/write`.
- GitHub secrets: `APPROVAL_API_URL`, `APPROVAL_API_SECRET`.
- Amvera variables: the matching approval secret and GitHub token.

Never print, copy into logs, or commit any secret value.

## Recovery

If Telegram cannot review GitHub, do not bypass the environment. Check the bot
health endpoint, token expiry, `Deployments` permission, and the workflow run.
If GitHub-to-Telegram synchronization fails, deployment must stop before upload.
Fix through a pull request, pass CI, and repeat with a rejection test first.
