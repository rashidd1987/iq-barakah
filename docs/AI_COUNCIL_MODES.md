# AI council modes

The owner-only Telegram bot exposes one `Совет ИИ` entry with three modes.

## Built-in

Uses deterministic project status and ten fixed professional roles. It does
not call an external AI provider and does not consume API tokens.

## API

Only providers with a configured secret are shown. The owner selects a
provider, enters a task, and must press a second confirmation button before
the task leaves the service or consumes API tokens. The response is advisory:
it cannot change code or production.

Supported secrets:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `PERPLEXITY_API_KEY`
- `XAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `KIMI_API_KEY`

Each default model can be overridden with the matching `*_MODEL` variable.
Secrets must be stored as Amvera secrets and must never be sent in Telegram.

## Subscription handoff

Produces one reusable prompt and links to ChatGPT, Claude, and Gemini. The
owner manually copies the prompt into an existing consumer subscription.
Consumer subscriptions are not used for unattended execution.

## Execution boundary

AI responses only provide analysis. Code changes, workflows, deployments, and
production actions continue to use the existing allowlisted approval system.
