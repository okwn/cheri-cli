# Security Notes

Cheri now separates:

- bootstrap secret
- session token
- workspace membership
- invite code
- provider credentials

## Current hardening in the repository

- bootstrap secrets, invite codes, session tokens, and grant tokens use cryptographically secure randomness
- session tokens are hashed before KV storage
- file and team routes require valid session plus workspace membership
- admin-only team operations enforce role checks
- upload and download use short-lived Worker-issued grants
- the local CLI state is split into public state and sensitive credentials files
- the bootstrap secret is not stored locally unless explicitly requested
- provider secret fields are separated from ordinary workspace metadata
- provider summaries are redacted before display
- task registry records store `target_label`, not raw local absolute paths
- download destination handling blocks accidental overwrite unless `--force` is used

## Current limitations

- local credentials are separated but not yet encrypted at rest
- provider secret storage is separated in KV but not yet encrypted with an external secret manager
- there is no bootstrap rotation flow yet
- there is no full refresh-token/session-rotation model yet
- Worker-side abuse protection is still lightweight rate-limiting scaffolding, not a full defense layer

## Logging expectations

- do not print bootstrap secrets in normal output
- do not print session tokens in normal output
- do not print raw provider secrets back after prompt entry
- treat invite codes as credentials and avoid sharing them in logs

## Backend exposure

- the Worker is API-only
- legacy dashboard-style routes return deprecation responses
- CORS is no longer wildcard-open by default
- CORS headers are only emitted for explicitly allowed origins
