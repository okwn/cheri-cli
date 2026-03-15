# Auth and Bootstrap Flow

Cheri keeps these concerns separate:

- user identity
- session token
- workspace access
- active workspace
- bootstrap secret
- invite code
- provider credentials

## Register

`cheri register`:

1. asks for username
2. asks for the first workspace name
3. shows provider choices
4. validates the selected provider
5. generates a 12-word bootstrap secret on the backend
6. creates a session
7. asks whether local state should be saved
8. asks separately whether the bootstrap secret should also be saved

## Login

`cheri login`:

- reuses a valid saved session when possible
- otherwise asks for username
- can reuse a saved bootstrap secret if one was explicitly stored
- otherwise asks for the 12-word bootstrap secret

## Logout

`cheri logout`:

- revokes the current backend session
- removes the local saved state and credentials files

## Local save vs copy behavior

Cheri no longer keeps all local auth data in one JSON file.

### Public local state

`state.json` stores:

- identity
- active workspace id
- accessible workspace summaries

### Sensitive local credentials

`credentials.json` stores:

- session token
- optional bootstrap secret

The bootstrap secret is no longer stored unless the operator explicitly chooses to store it.

### Copy-only mode

If local save is declined:

- Cheri clears any saved local state
- prints a copy-friendly payload
- leaves storage/retention to the operator

## Credential types

### Bootstrap secret

- format: 12 random words
- scope: user bootstrap and login
- backend storage: hash only

### Session token

- format: opaque bearer token
- scope: active authenticated session
- backend storage: hash only

### Invite code

- format: `CHR-TEAM-XXXXXXXX`
- scope: workspace join only
- resettable and revocable

### Provider credentials

- scope: workspace storage integration only
- stored separately from user auth concerns
- redacted in workspace summaries

## What is gone

- browser approval page
- device authorization polling
- dashboard login redirect
- invite HTML page
