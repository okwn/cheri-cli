# Cheri Task Automation

`cheri task` manages local automation definitions for workspace-aware sync behavior.

## Supported commands

```bash
cheri task create --directory cheri_test_files --mode on-change
cheri task create --directory "C:\Users\Name\Desktop\cheri_test_files" --mode on-change
cheri task create --file notes.md --mode interval --every 10m
cheri task find cheri_test_files
cheri task list
cheri task start <task-id>
cheri task stop <task-id>
cheri task remove <task-id>
cheri task run <task-id>
cheri task logs <task-id>
cheri task watch --all
```

There is no public shorthand form such as `cheri task --file ...` in the current command tree. Use `cheri task create ...`.

## Default behavior

- new tasks auto-start background watching by default
- use `--no-start` if you only want to save the definition
- file tasks default to `instant`
- directory tasks default to `on-change`
- debounce defaults to `3` seconds
- recursive directory scanning defaults to `true`
- direction is currently fixed to `upload-only`

## Friendly target resolution

When you pass a simple file or folder name, Cheri resolves it in this order:

1. current working directory
2. Desktop
3. Documents
4. Downloads

Examples:

```bash
cheri task create --directory cheri_test_files --mode on-change
cheri task create --directory Downloads --pick
cheri task find cheri_test_files
```

Rules:

- quoted absolute paths still work
- Windows paths with spaces work
- if Cheri finds multiple matches, it shows a selection list
- if nothing matches, it prints the searched locations clearly

## Status meanings

- `watching`
  - the background watcher is active and waiting for changes
- `running`
  - a sync pass is happening now
- `stopped`
  - the task definition exists, but background watching is not active
- `idle`
  - the task is enabled, but no active watcher heartbeat is present
- `error`
  - the last task run or watch loop check failed

## What is supported today

- local-to-remote upload-oriented sync
- relative path preservation for directory uploads
- automatic background watching after task creation
- task start/stop/remove
- task logs
- predictable runtime snapshots
- basic in-progress lock to avoid duplicate task runs

## What is not production-ready yet

- pull-only task direction
- bidirectional task direction
- automatic remote deletions
- remote conflict resolution
- OS-native filesystem event integration
- service-manager / daemon packaging

## Local files

Task data lives in the user config directory:

- `tasks.json`
- `task-runtime.json`
- `task-logs.json`

Background watcher output is also written under:

- `task-watchers/`

## Safety behavior

- task targets are normalized and validated
- common noise files are skipped
- task registry records sent to the Worker use sanitized target labels
- provider readiness is checked before task execution
- workspace access is revalidated before every task run
- auto-search is limited to the current folder, Desktop, Documents, and Downloads
