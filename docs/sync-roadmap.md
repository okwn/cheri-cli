# Sync Roadmap and Versioning Strategy

Cheri is already shaped for sync-oriented collaboration even though full bidirectional sync is not complete yet.

## What exists now

- workspace-scoped file registry
- workspace-level provider config and validation state
- upload and download grants
- file version increments on same-name uploads
- metadata fields for uploader, editor, checksum, provider object identity, remote revision, and local modified time
- activity feed for uploads, modifications, workspace joins, and invite actions
- local task automation with persisted definitions, snapshots, logs, and foreground watch loops

## File versioning strategy

Each file record tracks:

- stable file id
- logical name
- current version
- provider object key or id
- provider kind
- version history metadata
- checksum
- local modified timestamp
- remote revision marker
- remote modified timestamp
- sync status and conflict state

Re-uploading the same filename creates a new version record instead of treating the upload as an unrelated blob.

## Sync-oriented hooks

The current shape leaves room for:

- local-to-remote sync loops
- local task scheduling with richer runtime state and future daemon support
- remote-to-local reconciliation
- checksum comparison before upload
- conflict detection prompts
- version history inspection
- provider-specific change tracking adapters
- provider-specific optimizations behind the same abstraction

## Near-term roadmap

1. encrypted local state for saved credentials
2. explicit bootstrap rotation flow
3. richer session rotation and expiration controls
4. external provider connectors for S3-compatible, Google Drive, and Backblaze B2
5. conflict detection and merge-safe sync commands
