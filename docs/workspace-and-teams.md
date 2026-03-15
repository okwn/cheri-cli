# Workspace and Teams

Workspaces are the core collaboration unit in Cheri.

## Workspace commands

```bash
cheri workspace list
cheri workspace create --name project-alpha
cheri workspace use project-alpha
cheri workspace join CHR-TEAM-8X2K91QZ
```

## Current workspace behavior

- one user can belong to multiple workspaces
- the CLI stores one active workspace locally
- workspace-scoped commands use the active workspace by default
- `--workspace <id-or-name>` overrides the active workspace for one command without rewriting the saved active workspace

## Workspace create

`cheri workspace create --name <name>`:

- creates a workspace if it does not exist
- prompts for provider selection
- currently allows `System (recommended)` in the public setup flow
- selects the new workspace immediately

## Workspace use

`cheri workspace use <id-or-name>`:

- accepts workspace id, name, or slug
- updates the saved active workspace

## Workspace join

`cheri workspace join <invite-code>`:

- accepts a short invite code such as `CHR-TEAM-8X2K91QZ`
- adds membership to the invited workspace
- switches the active workspace to the joined workspace
- keeps the same user identity and session

## Team commands

```bash
cheri teams invite
cheri teams list
cheri teams invite-reset
```

## Invite behavior

- invite codes are short generated tokens
- invite codes are persisted in the backend
- invite reset revokes the current active invite generation
- `cheri teams invite-reset --new` can mint a replacement code immediately

## Team list behavior

`cheri teams list` shows:

- members
- roles
- joined timestamps
- active invite codes for admins
- invite generation state for admins

## Roles

Current role behavior is simple:

- `admin`
- `member`

Admin access is required for:

- `cheri teams invite`
- `cheri teams invite-reset`
