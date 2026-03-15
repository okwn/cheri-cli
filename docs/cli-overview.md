# Cheri CLI Overview

Cheri is a CLI-first collaboration and file sync product. The Worker exists to serve the `cheri` command surface, not a browser dashboard.

## Command groups

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

## CLI UX note

- Use `cheri --help` for the top level.
- Use `cheri <group> --help` for a command family.
- Use `cheri help <group>` if you prefer explicit help discovery.
- Use `cheri config get` to inspect the current backend URL resolution.
- Use `cheri config check` to verify Worker connectivity from the CLI.

## Most common flows

### Bootstrap and login

```bash
cheri config get
cheri config check
cheri register
cheri login
cheri logout
```

### Workspace and teams

```bash
cheri workspace list
cheri workspace create --name docs
cheri workspace use docs
cheri workspace join CHR-TEAM-8X2K91QZ
cheri teams invite
cheri teams list
cheri teams invite-reset --new
```

### Files

```bash
cheri file upload ./notes.md
cheri file upload ./src
cheri file list
cheri file download notes.md --dest ./downloads
cheri file download notes.md --force
```

### Tasks

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

## Reality checks

- The active product path is CLI-first.
- The Worker is JSON API-only.
- The default backend URL for this repository is `https://cheri.parapanteri.com`.
- Backend URL resolution honors `CHERI_API_URL`, `CHERI_WORKER_URL`, and saved local config before falling back to deployment metadata.
- `System (recommended)` is the only production-ready selectable storage provider in this build.
- `S3-compatible`, `Google Drive`, and `Backblaze B2` are coming soon in the public setup flow.
- Task automation is real, currently upload-only and local-first, and new tasks auto-start background watching unless `--no-start` is used.

## What is intentionally not part of the product path

- browser approval flow
- worker-rendered dashboard
- invite HTML pages
- device authorization polling
- dashboard-only compatibility routes
