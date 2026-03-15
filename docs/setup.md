# Cheri Setup

Cheri is installed globally as a CLI and can then be run from any directory.

## Requirements

- Python 3.9+
- `pip`
- Node.js 18+ for Worker tests and the npm launcher stub
- Wrangler
- Cloudflare KV namespace
- Cloudflare R2 bucket

## Worker bindings

`wrangler.toml` expects:

- `HERMES_KV`
- `HERMES_BUCKET`

Current repository deployment metadata resolves to:

- Worker API domain: `https://cheri.parapanteri.com`
- KV binding: `HERMES_KV`
- KV id: replace with your own namespace id before self-hosting
- R2 binding: `HERMES_BUCKET`
- R2 bucket: `cheri-files`

The deployed Worker is API-only in this build. Browser/dashboard pages, invite HTML, and approval pages are not part of the active product flow.

## Deploy the Worker

```bash
wrangler deploy
```

Set the API URL locally:

```bash
$env:CHERI_API_URL = "https://cheri.parapanteri.com"
```

On Unix-like shells:

```bash
export CHERI_API_URL=https://cheri.parapanteri.com
```

Cheri also discovers the backend URL automatically from:

1. `CHERI_API_URL`
2. `CHERI_WORKER_URL`
3. saved local config in `settings.json`
4. embedded public defaults and optional repo deployment metadata such as `wrangler.toml`

## Install Cheri globally from this repo

```bash
python -m pip install .
cheri --help
```

Windows alternative:

```bash
py -3 -m pip install .
cheri --help
```

## Config and state directory

Cheri stores user-level config here by default:

- Linux: `~/.config/cheri/`
- macOS: `~/Library/Application Support/Cheri/`
- Windows: `%APPDATA%\\Cheri\\`

Files:

- `settings.json`
- `state.json`
- `credentials.json`
- `tasks.json`
- `task-runtime.json`
- `task-logs.json`

## First run

```bash
cheri config get
cheri config check
cheri register
```

The setup flow currently:

1. asks for username
2. asks for the first workspace name
3. shows provider choices
4. allows `System (recommended)` as the public production-ready option
5. marks `S3-compatible`, `Google Drive`, and `Backblaze B2` as coming soon
6. validates the selected provider
7. generates a 12-word bootstrap secret
8. asks whether local state should be saved
9. asks separately whether the bootstrap secret should also be saved

## Current provider availability

- `System (recommended)`
  - fully working
  - temporary
  - resets daily
- `S3-compatible`
  - coming soon in the public flow
- `Google Drive`
  - coming soon in the public flow
- `Backblaze B2`
  - coming soon in the public flow

## Common flows

```bash
cheri config get
cheri config set api-url https://cheri.parapanteri.com
cheri config check
cheri login
cheri workspace list
cheri workspace create --name docs
cheri workspace use docs
cheri workspace join CHR-TEAM-8X2K91QZ
cheri file upload ./notes.md
cheri file upload ./src
cheri file list
cheri file download notes.md --dest ./downloads
cheri teams invite
cheri activity
cheri task create --directory cheri_test_files --mode on-change
cheri task create --directory "C:\Users\Name\Desktop\cheri_test_files" --mode on-change
cheri task stop <task-id>
cheri task start <task-id>
```

## Future npm install

The repository includes `package.json` and a `bin` entry so a future distribution can expose:

```bash
npm install -g cheri
```

Today, the npm launcher is only a wrapper around the Python CLI. The supported install path remains `python -m pip install .`.

## Task UX notes

- `cheri task create` auto-starts background watching by default
- use `--no-start` if you only want to save the task definition
- simple names such as `cheri_test_files` are resolved against:
  - the current working directory
  - Desktop
  - Documents
  - Downloads
- use `cheri task find <name>` if you want to see matching locations before creating the task

## Update and uninstall

Update from the repo:

```bash
python -m pip install --upgrade .
```

Remove the CLI:

```bash
python -m pip uninstall cheri
```
