# Storage Provider Matrix

Cheri keeps a provider abstraction for future storage backends, but it is now explicit about what is actually production-ready.

## Provider interface

Every provider adapter follows the same contract:

- `validateConfig`
- `putObject`
- `getObject`
- `deleteObject`
- `listObjects`
- `statObject`
- `generateUploadTarget`
- `generateDownloadTarget`

## Public provider availability

| Provider | Public setup status | Transfer status | Notes |
| --- | --- | --- | --- |
| `System (recommended)` | Selectable now | Working now | Uses `HERMES_BUCKET`. Temporary. Files reset daily. |
| `S3-compatible` | Coming soon | Not active | Config model and validation hooks exist. Public selection is disabled by default. |
| `Google Drive` | Coming soon | Not active | Config model and validation hooks exist. Public selection is disabled by default. |
| `Backblaze B2` | Coming soon | Not active | Config model and validation hooks exist. Public selection is disabled by default. |

## System provider

`System (recommended)` is the only production-ready public choice in this build.

- Cheri shows a warning before selection.
- The warning must be acknowledged.
- The Worker uses R2 through `HERMES_BUCKET`.
- A scheduled cleanup removes old files daily.

## Experimental groundwork

The repository still includes:

- provider config models
- provider-specific field definitions
- validation hooks
- provider secret separation scaffolding
- provider registry wiring

This groundwork exists so future S3, Google Drive, and Backblaze B2 enablement does not require redesigning the workspace file registry or provider interface.

## Provider credentials

Provider credentials are not part of:

- the bootstrap secret
- the session token
- the invite code

They belong to workspace storage configuration only. Secret-bearing provider fields are separated from normal workspace metadata so future encrypted secret storage can replace the current KV-backed abstraction cleanly.
