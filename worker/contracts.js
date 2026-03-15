import { createId, isoNow, normalizeUsername, slugify } from "./security/tokens.js";

export function createUserRecord({ id, username, bootstrapSecretHash, defaultWorkspaceId }) {
  const now = isoNow();
  return {
    id,
    username,
    username_key: normalizeUsername(username),
    created_at: now,
    updated_at: now,
    bootstrap_secret_hash: bootstrapSecretHash,
    default_workspace_id: defaultWorkspaceId,
    last_active_workspace_id: defaultWorkspaceId,
    last_login_at: "",
    workspace_memberships: [],
  };
}

export function createWorkspaceRecord({ id, name, ownerUserId, ownerUsername, storage }) {
  const now = isoNow();
  return {
    id,
    name,
    slug: slugify(name),
    created_at: now,
    updated_at: now,
    owner_user_id: ownerUserId,
    storage,
    invite_generation: 1,
    members: [
      {
        user_id: ownerUserId,
        username: ownerUsername,
        role: "admin",
        joined_at: now,
      },
    ],
    settings: {
      metadata_versioning: true,
      future_conflict_detection: true,
      sync_hooks_ready: true,
    },
  };
}

export function createSessionRecord(userId, username) {
  const now = isoNow();
  return {
    id: `ses_${createId(12)}`,
    kind: "user_session",
    user_id: userId,
    username,
    issued_at: now,
    created_at: now,
    last_used_at: now,
  };
}

export function createInviteRecord({ code, workspace, actor, label }) {
  const now = isoNow();
  return {
    code,
    workspace_id: workspace.id,
    workspace_name: workspace.name,
    role: "member",
    status: "active",
    label,
    created_by: actor,
    created_at: now,
    expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    generation: workspace.invite_generation,
  };
}
