# Cheri

Cheri is a CLI-first collaborative workspace sync tool. It focuses on shared workspaces, file transfer, team invites, activity history, and task-based local sync automation. The backend uses Cloudflare Workers for the API layer, KV for lightweight registry/state, and R2 for blob storage.

## What Cheri Does

Cheri gives a small team a command-line workflow for:

- creating an account and workspace
- joining additional workspaces by invite code
- uploading, listing, and downloading workspace files
- reviewing recent activity
- creating local sync tasks that can watch files or folders and upload changes automatically

It is designed around a CLI client talking to a Worker API backend. The old dashboard/browser-first product path is not part of this repository.

## Current Status

Cheri is usable as a CLI-first project, but it is not fully feature-complete.

Ready now:

- register / login / logout
- workspace create / list / use / join
- file upload / download / list
- team invite / list / invite-reset
- activity feed
- task create / list / start / stop / run / logs / watch
- System provider support
- Worker + KV + R2 backend architecture

Still limited:

- `System (recommended)` is the only public provider that is production-ready in this build
- S3-compatible, Google Drive, and Backblaze B2 are scaffolded but not public-ready
- task automation is upload-only today
- conflict handling and bidirectional sync are not implemented
- if `cheri` is not found after install, your Python scripts directory may need to be on `PATH`

## Features

- `cheri register`, `cheri login`, `cheri logout`
- `cheri workspace create`, `list`, `use`, `join`
- `cheri file upload`, `download`, `list`
- `cheri teams invite`, `list`, `invite-reset`
- `cheri activity`
- `cheri task create`, `find`, `list`, `start`, `stop`, `remove`, `run`, `logs`, `watch`
- workspace-scoped file metadata and short-lived transfer grants
- short invite codes such as `CHR-TEAM-8X2K91QZ`
- background task auto-start on creation
- friendly task target lookup for current directory, Desktop, Documents, and Downloads

## Architecture

Cheri has three main pieces:

1. CLI client
   - Python package in `cheri_cloud_cli/`
   - handles command parsing, auth prompts, local state, task automation, and file transfer orchestration

2. Worker API backend
   - source in `worker/`
   - handles auth, workspace membership, invites, activity, file metadata, provider validation, and transfer grants

3. Cloudflare storage foundation
   - KV stores lightweight metadata such as users, sessions, memberships, invites, activity, task registry state, and provider config references
   - R2 stores file/blob content

The current main provider is `System (recommended)`, which uses Worker-managed R2-backed storage and resets files daily.

## Installation

The supported install path today is Python-based.

### Requirements

- Python 3.9+
- `pip`
- Node.js 18+ if you want to run the Worker test suite
- Wrangler if you want to deploy the backend yourself

### Install from this repo

```bash
git clone <your-github-url> cheri-app
cd cheri-app
python -m pip install .
cheri --help
```

Windows alternative:

```powershell
py -3 -m pip install .
cheri --help
```

If `cheri` is still not found after install:

- open a new shell
- or ensure your Python scripts directory is on `PATH`
- on Windows, that is typically under `%APPDATA%\Python\PythonXY\Scripts` or the active interpreter's scripts path

## Global CLI Usage

After install, `cheri` should work from any directory:

```bash
cheri --help
cheri config get
cheri workspace list
```

Your current working directory only matters when you pass local file or folder paths. Task target resolution is more forgiving than raw file commands: a simple name such as `cheri_test_files` is checked against the current directory, Desktop, Documents, and Downloads.

## Backend Configuration

Cheri resolves its backend URL in this order:

1. `CHERI_API_URL`
2. `CHERI_WORKER_URL`
3. saved local CLI config
4. embedded public defaults and optional repo deployment metadata

This published repo defaults to:

- `https://cheri.parapanteri.com`

Useful commands:

```bash
cheri config get
cheri config set api-url https://cheri.parapanteri.com
cheri config reset
cheri config check
```

Environment example:

```bash
export CHERI_API_URL=https://cheri.parapanteri.com
```

Windows:

```powershell
$env:CHERI_API_URL = "https://cheri.parapanteri.com"
```

## Deploying the Backend

If you want to self-host the backend:

1. create your own Cloudflare KV namespace
2. create your own R2 bucket
3. update `wrangler.toml`
   - set the KV namespace id
   - set the bucket name
   - update the route pattern if you use your own domain
4. deploy with Wrangler

```bash
wrangler deploy
```

The Worker expects these bindings:

- `HERMES_KV`
- `HERMES_BUCKET`

If you deploy your own backend, point the CLI to it with either:

- `CHERI_API_URL`
- or `cheri config set api-url <url>`

## Quick Start

```bash
cheri config get
cheri config check
cheri register
cheri workspace list
cheri file upload ./notes.md
cheri file list
cheri file download notes.md --dest ./downloads
```

Recommended first run:

1. run `cheri register`
2. choose `System (recommended)`
3. acknowledge the daily reset warning
4. choose whether to save local session state
5. keep the bootstrap secret safe
6. upload a file to verify the workspace

## Invite / Collaboration Test

This is the simplest two-user collaboration check.

### User A

1. Install Cheri.
2. Verify backend config with `cheri config get`.
3. Register:

```bash
cheri register
```

4. Create or switch to the workspace you want to share:

```bash
cheri workspace create --name docs
cheri workspace use docs
```

5. Create an invite code:

```bash
cheri teams invite
```

### User B

1. Install Cheri.
2. Verify backend config with `cheri config get`.
3. Register or log in.
4. Join with the invite code:

```bash
cheri workspace join CHR-TEAM-8X2K91QZ
```

5. Confirm access:

```bash
cheri workspace list
cheri teams list
```

### Shared verification

User A:

```bash
cheri file upload ./shared.txt
```

User B:

```bash
cheri file list
cheri file download shared.txt --dest ./downloads
cheri activity
```

## Task / Folder Sync

Cheri tasks are local automation definitions tied to a workspace.

Examples:

```bash
cheri task create --directory cheri_test_files --mode on-change
cheri task create --directory "C:\Users\Name\Desktop\cheri_test_files" --mode on-change
cheri task create --file notes.md --mode interval --every 10m
cheri task find cheri_test_files
cheri task list
cheri task stop <task-id>
cheri task start <task-id>
cheri task run <task-id>
cheri task logs <task-id>
```

Current task behavior:

- `cheri task create` auto-starts background watching by default
- use `--no-start` if you only want to save the task definition
- simple names are resolved from:
  - current directory
  - Desktop
  - Documents
  - Downloads
- `cheri task stop` stops background watching without deleting the task
- `cheri task start` starts it again
- foreground `cheri task watch` is still available for explicit watch-loop runs

Current limitations:

- upload-only only
- no pull-only mode
- no bidirectional sync
- no remote delete reconciliation
- no conflict resolution yet

## Command Reference

```bash
cheri register
cheri login
cheri logout
cheri config get
cheri config set api-url <url>
cheri config reset
cheri config check
cheri workspace create --name <name>
cheri workspace list
cheri workspace use <id-or-name>
cheri workspace join <invite-code>
cheri file upload <path>
cheri file download <file-or-id>
cheri file list
cheri teams invite
cheri teams list
cheri teams invite-reset
cheri activity
cheri task create
cheri task find <name>
cheri task list
cheri task start <task-id>
cheri task stop <task-id>
cheri task remove <task-id>
cheri task run <task-id>
cheri task logs <task-id>
cheri task watch --all
cheri help
```

## Known Limitations

- only `System (recommended)` is public-ready
- current default backend is public, but live deployment must stay in sync with the CLI contract
- task automation is local-first and upload-only
- local secret storage is separated but not encrypted at rest
- the npm launcher is present for future packaging, but Python remains the supported install path today

## Development

Repo structure:

- `cheri_cloud_cli/` — Python CLI implementation
- `worker/` — Cloudflare Worker API
- `docs/` — product and setup documentation
- `guide/` — static guide UI
- `tests/` — Python and Worker tests
- `scripts/` — helper scripts

Test commands:

```bash
node tests/node/worker.test.mjs
python -m unittest discover -s tests/python -p "test_*.py"
```

Combined npm entry:

```bash
npm test
```

Deploy command:

```bash
wrangler deploy
```

## Security Notes

Cheri stores local state in a user-level config directory, not in the repo by default.

Sensitive files:

- `credentials.json`
- any local override `.env`
- any task watcher logs if they contain operational details

Do not commit:

- bootstrap secrets
- session tokens
- provider credentials
- local config overrides
- `.wrangler/` local state
- generated task/runtime files

Bootstrap secret basics:

- it is only for the user's own register/login flow
- it is not an invite code
- keep it outside screenshots, logs, and commits

## License

This export does not include a license file. Choose and add an explicit license before wider publication.
