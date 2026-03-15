import { isoNow } from "../security/tokens.js";
import { kvGet, kvSet, listFilesByWorkspace } from "../lib/storage.js";
import { normalizeStoredFileRecord, serializeFileRecord } from "../services/storage_registry.js";

const COLLABORATION_ACTIONS = new Set([
  "workspace_created",
  "workspace_selected",
  "session_registered",
  "session_login",
  "session_logout",
  "invite_created",
  "invite_reset",
  "member_joined",
]);

export async function appendActivity(env, workspaceId, actor, action, summary, metadata = {}) {
  const logKey = `activity:${workspaceId}`;
  const activity = (await kvGet(env, logKey)) || [];
  activity.unshift({
    at: isoNow(),
    actor,
    action,
    summary,
    metadata,
  });
  await kvSet(env, logKey, activity.slice(0, 400));
}

export async function appendTaskActivity(env, workspaceId, actor, body = {}) {
  const action = String(body.action || "task_sync_event").trim() || "task_sync_event";
  const summary = String(body.summary || "Task sync activity").trim() || "Task sync activity";
  const metadata = {
    task_id: String(body.task_id || "").trim(),
    target: String(body.target || "").trim(),
    mode: String(body.mode || "").trim(),
    status: String(body.status || "").trim(),
    uploaded_count: Number(body.uploaded_count || 0),
    changed_count: Number(body.changed_count || 0),
    deleted_count: Number(body.deleted_count || 0),
    dry_run: !!body.dry_run,
  };
  return appendActivity(env, workspaceId, actor, action, summary, metadata);
}

function sortFilesBy(key, files) {
  return [...files].sort((left, right) => String(right[key] || "").localeCompare(String(left[key] || "")));
}

export async function buildActivityFeed(env, workspaceId) {
  const files = (await listFilesByWorkspace(env, workspaceId))
    .map(normalizeStoredFileRecord)
    .filter((file) => file.status === "available");
  const activity = (await kvGet(env, `activity:${workspaceId}`)) || [];
  return {
    recent_uploads: sortFilesBy("uploaded_at", files).slice(0, 10).map(serializeFileRecord),
    recent_modified_files: sortFilesBy("updated_at", files).slice(0, 10).map(serializeFileRecord),
    recent_actions: activity.slice(0, 20),
    recent_collaboration: activity.filter((item) => COLLABORATION_ACTIONS.has(item.action)).slice(0, 20),
  };
}
