# Cheri Export Report

## What was copied

- `cheri_cloud_cli/`
- `worker/`
- `bin/`
- `scripts/`
- `tests/`
- `docs/`
- `guide/`
- `cli.py`
- `index.js`
- `package.json`
- `package-lock.json`
- `setup.py`
- `wrangler.toml`

## What was excluded

- `.venv/`
- `.wrangler/`
- local state and credential files
- smoke-test artifacts
- internal audit reports such as `RAPOR*.md`
- internal implementation notes from the source working repo
- raw `wrangler_information` files

## Sanitized or templated items

- `wrangler.toml`
  - kept for public deployment guidance
  - KV namespace id replaced with a placeholder value
- `cheri_cloud_cli/deployment.py`
  - embedded KV namespace id replaced with a public-safe placeholder
- `.env.example`
  - added as a safe config example
- `README.md`
  - written for GitHub-facing installation, usage, backend setup, invite testing, and task behavior
- `.gitignore`
  - covers runtime residue, local overrides, build output, and editor junk

## Remaining limitations before publication

- the public backend domain is still referenced because the current CLI defaults to it
- the supported install path remains Python-based
- only `System (recommended)` is public-ready as a storage provider
- the deployed backend must stay compatible with the published CLI version
