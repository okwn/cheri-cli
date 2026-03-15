import { createSessionRecord, createUserRecord, createWorkspaceRecord } from "../contracts.js";
import { appendActivity } from "../activity/service.js";
import { HttpError } from "../lib/http.js";
import { getUserByUsername, saveSession, saveUser, saveWorkspace, deleteSession } from "../lib/storage.js";
import { createWorkspaceStorageState, validateProviderSelection } from "../providers/index.js";
import { buildSessionPayload } from "../workspace/service.js";
import { createBootstrapSecret, createId, createSessionToken, isoNow, sha256 } from "../security/tokens.js";
import { booleanFlag, requiredString, workspaceName } from "../lib/validate.js";

function assertValidUsername(username) {
  const trimmed = String(username || "").trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{1,31}$/.test(trimmed)) {
    throw new HttpError(400, "Username must be 2-32 characters and use letters, numbers, dot, underscore, or dash.");
  }
  return trimmed;
}

export async function registerUser(env, body) {
  const username = assertValidUsername(body?.username);
  if (await getUserByUsername(env, username)) {
    throw new HttpError(409, "Username already exists.");
  }

  const initialWorkspaceName = workspaceName(body?.workspace_name || `${username} workspace`);

  const provider = await validateProviderSelection(env, body?.provider, {
    allowExperimental: booleanFlag(body?.provider?.experimental_acknowledged, false),
  });
  const workspaceId = `ws_${createId(12)}`;
  const userId = `usr_${createId(12)}`;
  const bootstrapSecret = createBootstrapSecret();

  const user = createUserRecord({
    id: userId,
    username,
    bootstrapSecretHash: await sha256(bootstrapSecret),
    defaultWorkspaceId: workspaceId,
  });
  const workspace = createWorkspaceRecord({
    id: workspaceId,
    name: initialWorkspaceName,
    ownerUserId: userId,
    ownerUsername: username,
    storage: await createWorkspaceStorageState(env, workspaceId, provider),
  });
  user.workspace_memberships = [
    {
      workspace_id: workspace.id,
      role: "admin",
      joined_at: workspace.created_at,
    },
  ];
  user.last_login_at = isoNow();

  await saveWorkspace(env, workspace);
  await saveUser(env, user);

  const sessionToken = createSessionToken();
  const session = createSessionRecord(user.id, user.username);
  await saveSession(env, sessionToken, session);
  await appendActivity(env, workspace.id, user.username, "session_registered", "Initial workspace bootstrap", {
    provider: provider.kind,
  });

  return buildSessionPayload(env, user, workspace.id, {
    session_token: sessionToken,
    session_issued_at: session.issued_at,
    bootstrap_secret: bootstrapSecret,
  });
}

export async function loginUser(env, body) {
  const username = assertValidUsername(body?.username);
  const bootstrapSecret = requiredString(body?.bootstrap_secret, "bootstrap_secret", {
    minLength: 8,
    maxLength: 256,
  });

  const user = await getUserByUsername(env, username);
  if (!user) {
    throw new HttpError(401, "Invalid username or bootstrap secret.");
  }
  const secretHash = await sha256(bootstrapSecret);
  if (secretHash !== user.bootstrap_secret_hash) {
    throw new HttpError(401, "Invalid username or bootstrap secret.");
  }

  user.last_login_at = isoNow();
  user.last_active_workspace_id = user.last_active_workspace_id || user.default_workspace_id;
  await saveUser(env, user);

  const sessionToken = createSessionToken();
  const session = createSessionRecord(user.id, user.username);
  await saveSession(env, sessionToken, session);
  if (user.last_active_workspace_id) {
    await appendActivity(env, user.last_active_workspace_id, user.username, "session_login", user.username);
  }

  return buildSessionPayload(env, user, user.last_active_workspace_id, {
    session_token: sessionToken,
    session_issued_at: session.issued_at,
  });
}

export async function logoutUser(env, auth) {
  await deleteSession(env, auth.token);
  if (auth.user.last_active_workspace_id) {
    await appendActivity(env, auth.user.last_active_workspace_id, auth.user.username, "session_logout", auth.user.username);
  }
}
