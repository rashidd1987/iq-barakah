# Owner Council

The report bot accepts an owner task through `/council` or the
`🧠 Совет директоров` button and evaluates it from ten perspectives:

- CEO — strategy and priority;
- CTO — architecture and reliability;
- CPO — learner value and product flow;
- CMO — positioning, activation, and growth;
- CCO — customer experience and support;
- CFO — cost, return, and stop criteria;
- CISO — security, access, secrets, and rollback;
- COO — execution, monitoring, and operations;
- Data/DPO — metrics, minimum data, and privacy;
- Red Team critic — assumptions and failure modes.

## Execution boundary

The council is advisory and read-only. It cannot execute shell commands,
arbitrary GitHub workflows, deployments, database mutations, or secret changes.
Every executable button is an explicit allow-listed callback.

Read-only inspection may run immediately. A PWA build requires an explicit
owner selection. Production publication keeps the separate synchronized
Telegram/GitHub approval gate described in `RELEASE_APPROVAL_RUNBOOK.md`.

New executable actions must include:

1. a fixed callback identifier;
2. owner authorization;
3. input validation;
4. idempotency or duplicate-run protection;
5. tests proving the allow-list;
6. a separate approval for production impact.
