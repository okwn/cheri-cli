# Cheri Manual Test Checklist

## Auth and local state

- `cheri register` creates a user and first workspace.
- the bootstrap secret is shown exactly once in readable form
- local save is explicit
- bootstrap secret storage is a separate explicit choice
- `state.json` does not contain the session token
- `credentials.json` contains the session token and only contains the bootstrap secret when explicitly requested
- `cheri login` works with a saved session and with manual bootstrap entry
- `cheri logout` clears both local files

## Workspace and teams

- `cheri workspace list` shows accessible workspaces
- `cheri workspace create --name docs` creates and selects a workspace
- `cheri workspace use docs` switches the active workspace
- `cheri workspace join <invite-code>` joins another workspace cleanly
- `cheri teams invite` returns a `CHR-TEAM-...` code
- `cheri teams invite-reset --new` revokes and rotates invite generation

## Files

- `cheri file upload ./notes.md` uploads one file
- `cheri file upload ./src` uploads a directory tree with relative names preserved
- `cheri file list` shows version and editor metadata
- `cheri file download notes.md` refuses to overwrite an existing file unless `--force` is used
- `cheri activity` shows upload and download activity

## Tasks

- `cheri task create --directory cheri_test_files --mode on-change` stores a task definition and starts background watching immediately
- `cheri task find cheri_test_files` shows current-folder/Desktop/Documents/Downloads matches
- `cheri task run <task-id>` runs one upload-oriented sync pass
- `cheri task stop <task-id>` stops background watching without deleting the task
- `cheri task start <task-id>` starts background watching again
- `cheri task logs <task-id>` shows local logs
- `cheri task watch --all` respects stopped tasks and avoids duplicate in-progress runs

## Providers

- public setup flow allows `System (recommended)`
- public setup flow marks the other providers as coming soon
- `System` warns that files reset daily

## Backend hardening

- Worker does not emit wildcard CORS by default
- rate limiting is active on higher-risk auth/invite/file-grant routes
- session-protected routes reject missing tokens
- admin-only team routes reject non-admin members
