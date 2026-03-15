import { createInviteRecord } from "../contracts.js";
import { appendActivity } from "../activity/service.js";
import { HttpError } from "../lib/http.js";
import {
  ensureUserWorkspaceMembership,
  ensureWorkspaceMember,
  listInvitesByWorkspace,
  loadInvite,
  loadWorkspace,
  saveInvite,
  saveUser,
  saveWorkspace,
} from "../lib/storage.js";
import { buildSessionPayload, buildWorkspaceSummary } from "../workspace/service.js";
import { createInviteCode, isoNow } from "../security/tokens.js";
import { inviteCode as validateInviteCode, safeLabel } from "../lib/validate.js";

function isInviteActive(invite, workspace) {
  return Boolean(
    invite
    && invite.status === "active"
    && invite.generation === workspace.invite_generation
    && Date.parse(invite.expires_at || "") > Date.now(),
  );
}

function classifyInvite(invite, workspace) {
  if (!invite) {
    return "unknown";
  }
  if (invite.status === "accepted") {
    return "accepted";
  }
  if (invite.status === "revoked") {
    return "revoked";
  }
  if (Date.parse(invite.expires_at || "") <= Date.now()) {
    return "expired";
  }
  if (invite.generation !== workspace.invite_generation) {
    return "revoked";
  }
  return "active";
}

function summarizeInviteState(invites, workspace, membership) {
  const counts = {
    active: 0,
    accepted: 0,
    revoked: 0,
    expired: 0,
  };
  for (const invite of invites) {
    const state = classifyInvite(invite, workspace);
    counts[state] = (counts[state] || 0) + 1;
  }
  return {
    visible: membership.role === "admin",
    invite_generation: workspace.invite_generation,
    active_count: counts.active,
    accepted_count: counts.accepted,
    revoked_count: counts.revoked,
    expired_count: counts.expired,
  };
}

export async function listTeamSnapshot(env, workspace, user, membership) {
  const workspaceInvites = await listInvitesByWorkspace(env, workspace.id);
  const invites = membership.role === "admin"
    ? workspaceInvites.filter((invite) => isInviteActive(invite, workspace))
    : [];
  return {
    workspace: buildWorkspaceSummary(workspace, user),
    members: workspace.members || [],
    invites,
    invite_state: summarizeInviteState(workspaceInvites, workspace, membership),
  };
}

export async function createWorkspaceInvite(env, workspace, user, label = "") {
  const invite = createInviteRecord({
    code: createInviteCode(),
    workspace,
    actor: user.username,
    label: safeLabel(label, "Invite label", 80),
  });
  await saveInvite(env, invite);
  await appendActivity(env, workspace.id, user.username, "invite_created", invite.code, { label: invite.label });
  return invite;
}

export async function resetWorkspaceInvites(env, workspace, user, options = {}) {
  const invites = await listInvitesByWorkspace(env, workspace.id);
  let revokedCount = 0;
  for (const invite of invites) {
    if (!isInviteActive(invite, workspace)) {
      continue;
    }
    invite.status = "revoked";
    invite.revoked_at = isoNow();
    await saveInvite(env, invite);
    revokedCount += 1;
  }
  workspace.invite_generation = Number(workspace.invite_generation || 1) + 1;
  await saveWorkspace(env, workspace);
  let replacementInvite = null;
  if (options.create_replacement) {
    replacementInvite = await createWorkspaceInvite(env, workspace, user, options.label || "");
  }
  await appendActivity(env, workspace.id, user.username, "invite_reset", `Revoked ${revokedCount} invite(s).`, {
    created_replacement: !!replacementInvite,
  });
  return {
    revoked_count: revokedCount,
    invite_generation: workspace.invite_generation,
    invite: replacementInvite,
    invite_state: summarizeInviteState(await listInvitesByWorkspace(env, workspace.id), workspace, { role: "admin" }),
  };
}

export async function acceptWorkspaceInvite(env, user, inviteCode) {
  const normalizedCode = validateInviteCode(inviteCode);
  const invite = await loadInvite(env, normalizedCode);
  if (!invite) {
    throw new HttpError(404, "Invite code not found.");
  }
  const workspace = await loadWorkspace(env, invite.workspace_id);
  if (!workspace) {
    throw new HttpError(404, "Workspace not found.");
  }
  if (!isInviteActive(invite, workspace)) {
    throw new HttpError(410, "Invite code expired or was revoked.");
  }

  const joinedAt = isoNow();
  ensureWorkspaceMember(workspace, user.id, user.username, invite.role || "member", joinedAt);
  ensureUserWorkspaceMembership(user, workspace.id, invite.role || "member", joinedAt);
  user.last_active_workspace_id = workspace.id;
  await saveWorkspace(env, workspace);
  await saveUser(env, user);

  invite.status = "accepted";
  invite.accepted_by = user.username;
  invite.accepted_at = joinedAt;
  await saveInvite(env, invite);
  await appendActivity(env, workspace.id, user.username, "member_joined", `${user.username} joined via invite`, {
    invite_code: invite.code,
  });

  return buildSessionPayload(env, user, workspace.id);
}
