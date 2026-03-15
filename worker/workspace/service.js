import { createWorkspaceRecord } from "../contracts.js";
import { appendActivity } from "../activity/service.js";
import { HttpError } from "../lib/http.js";
import {
  findMembership,
  listWorkspacesForUser,
  saveUser,
  saveWorkspace,
} from "../lib/storage.js";
import { createWorkspaceStorageState, getWorkspaceProviderConfig, redactProvider, validateProviderSelection } from "../providers/index.js";
import { createId, isoNow } from "../security/tokens.js";
import { booleanFlag, requiredString, workspaceName } from "../lib/validate.js";

export function serializeUserProfile(user) {
  return {
    id: user.id,
    username: user.username,
    created_at: user.created_at,
  };
}

export function buildWorkspaceSummary(workspace, user) {
  const membership = findMembership(workspace, user.id);
  const provider = getWorkspaceProviderConfig(workspace);
  return {
    id: workspace.id,
    name: workspace.name,
    slug: workspace.slug,
    role: membership?.role || "member",
    created_at: workspace.created_at,
    joined_at: membership?.joined_at || "",
    member_count: Array.isArray(workspace.members) ? workspace.members.length : 0,
    provider: provider ? redactProvider(provider) : null,
  };
}

export async function listAccessibleWorkspaceRecords(env, user) {
  return listWorkspacesForUser(env, user);
}

export async function listAccessibleWorkspaces(env, user) {
  const workspaces = await listAccessibleWorkspaceRecords(env, user);
  return workspaces.map((workspace) => buildWorkspaceSummary(workspace, user));
}

function resolveWorkspaceIdentifier(workspaces, identifier) {
  const normalized = String(identifier || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return workspaces.find((workspace) => (
    workspace.id.toLowerCase() === normalized
    || workspace.name.toLowerCase() === normalized
    || workspace.slug === normalized
  )) || null;
}

export async function buildSessionPayload(env, user, activeWorkspaceId, extra = {}) {
  const workspaces = await listAccessibleWorkspaces(env, user);
  const resolvedActiveWorkspaceId = activeWorkspaceId || user.last_active_workspace_id || user.default_workspace_id || workspaces[0]?.id || "";
  const issuedAt = extra.session_issued_at || isoNow();
  const sessionToken = extra.session_token || "";
  const bootstrapSecret = extra.bootstrap_secret || "";
  return {
    identity: serializeUserProfile(user),
    session: {
      token: sessionToken,
      issued_at: issuedAt,
    },
    bootstrap: {
      secret: bootstrapSecret,
    },
    workspace_access: {
      active_workspace_id: resolvedActiveWorkspaceId,
      workspaces,
    },
    user: serializeUserProfile(user),
    workspaces,
    active_workspace_id: resolvedActiveWorkspaceId,
    issued_at: issuedAt,
    ...(sessionToken ? { session_token: sessionToken } : {}),
    ...(bootstrapSecret ? { bootstrap_secret: bootstrapSecret } : {}),
    ...extra,
  };
}

export async function createWorkspaceForUser(env, user, name, providerSelection) {
  const normalizedWorkspaceName = workspaceName(name);
  const provider = await validateProviderSelection(env, providerSelection, {
    allowExperimental: booleanFlag(providerSelection?.experimental_acknowledged, false),
  });
  const workspaceId = `ws_${createId(12)}`;
  const workspace = createWorkspaceRecord({
    id: workspaceId,
    name: normalizedWorkspaceName,
    ownerUserId: user.id,
    ownerUsername: user.username,
    storage: await createWorkspaceStorageState(env, workspaceId, provider),
  });
  user.workspace_memberships = [
    ...(user.workspace_memberships || []),
    {
      workspace_id: workspace.id,
      role: "admin",
      joined_at: workspace.created_at,
    },
  ];
  user.last_active_workspace_id = workspace.id;
  await saveWorkspace(env, workspace);
  await saveUser(env, user);
  await appendActivity(env, workspace.id, user.username, "workspace_created", workspace.name, { provider: provider.kind });
  return workspace;
}

export async function selectWorkspace(env, user, body) {
  const identifier = requiredString(body?.identifier || body?.name || "", "Workspace identifier", {
    minLength: 1,
    maxLength: 120,
  });

  const workspaces = await listAccessibleWorkspaceRecords(env, user);
  const existing = resolveWorkspaceIdentifier(workspaces, identifier);
  if (existing) {
    user.last_active_workspace_id = existing.id;
    await saveUser(env, user);
    await appendActivity(env, existing.id, user.username, "workspace_selected", existing.name);
    return buildSessionPayload(env, user, existing.id);
  }

  if (!body?.create_if_missing) {
    throw new HttpError(404, "Workspace not found.");
  }

  const normalizedWorkspaceName = workspaceName(identifier);
  const workspace = await createWorkspaceForUser(env, user, normalizedWorkspaceName, body.provider);
  return buildSessionPayload(env, user, workspace.id);
}
