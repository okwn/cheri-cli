# Cheri Runtime Architecture

Cheri has two primary runtime surfaces.

## Python CLI

`cheri_cloud_cli/` is responsible for:

- command parsing and help output
- local state and credentials files
- workspace selection
- file upload/download streaming
- local task definitions, runtime snapshots, and logs

## Worker API backend

`worker/` is responsible for:

- register/login/logout
- session validation
- workspace membership checks
- invite creation/reset/acceptance
- normalized file metadata
- upload/download grants
- provider validation and provider config storage
- activity feeds
- mirrored task registry records

## Cloudflare foundation

- Worker: API backend
- R2: blob storage
- KV: lightweight registry/state layer

Current deployment references:

- Worker domain: `https://cheri.parapanteri.com`
- KV binding: `HERMES_KV`
- KV id: set your own namespace id before deploying your own Worker
- R2 binding: `HERMES_BUCKET`
- R2 bucket: `cheri-files`

The CLI discovers the backend URL in this order:

1. `CHERI_API_URL`
2. `CHERI_WORKER_URL`
3. saved local config in `settings.json`
4. embedded public defaults and optional repo deployment metadata such as `wrangler.toml`

## KV domains

Current KV namespaces are separated by domain:

- users
- username index
- sessions
- workspaces
- file metadata
- file-name index
- upload grants
- download grants
- invites
- activity
- tasks
- provider secrets
- rate-limit counters

This is still KV-first, but the boundaries are cleaner for future migration to D1 or another database.

## Provider architecture

The provider interface stays normalized regardless of backend transport. Current public product behavior is intentionally honest:

- `System (recommended)` is working now
- the other providers remain coming soon in the public setup flow

Secret-bearing provider fields are stored separately from the ordinary workspace provider summary.

## Task architecture

Tasks are local-first:

- task definition lives on the operator machine
- runtime snapshot lives on the operator machine
- logs live on the operator machine
- the Worker only mirrors task registry state and task activity summaries

## Removed runtime surface

The active runtime no longer includes:

- dashboard redirects
- HTML auth pages
- invite HTML pages
- worker-rendered product UI
