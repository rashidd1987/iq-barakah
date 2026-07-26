# Project knowledge library

The report bot keeps an owner-maintained product brief for every project in
`REPORT_BOT_DATA_DIR/project_knowledge.json`. This persistent file is runtime
data and must not be committed.

The brief is injected into built-in, API, multi-model, and subscription-handoff
council requests. Models are instructed not to infer a product category from
its name and to ask one clarification when the brief is insufficient.

## Owner workflow

- `/library` shows all briefs and the active project.
- `/use mizanlife` selects the project used by short tasks.
- `/brief ...` replaces the active project's brief with one message.
- `/iqbarakah`, `/mizanlife`, and `/mizanos` also make that project active.
- `/addproject` collects monitoring data and then one 20–2000 character brief.

A useful brief states what the product is, who it serves, its main functions,
its current stage or constraints, and what it explicitly is not.

## Safety boundary

Briefs must contain product facts only. API keys, `.env` values, credentials,
private customer data, payment data, and personal data must never be entered.
The library does not grant AI models permission to execute changes.
