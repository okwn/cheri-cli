import { appendActivity } from "../activity/service.js";
import { loadTaskRecord, saveTaskRecord, listTasksByWorkspace, deleteTaskRecord } from "../lib/storage.js";
import { HttpError } from "../lib/http.js";
import { isoNow } from "../security/tokens.js";

const SUPPORTED_TASK_MODES = new Set(["interval", "on-change", "instant", "hybrid"]);
const SUPPORTED_TASK_DIRECTIONS = new Set(["upload-only"]);

function normalizePatternList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .slice(0, 32);
}

function sanitizeTargetLabel(value) {
  const raw = String(value || "").trim().replace(/\\/g, "/");
  if (!raw) {
    throw new HttpError(400, "task target_label is required.");
  }
  const sanitized = raw
    .split("/")
    .map((part) => part.trim())
    .filter((part) => part && part !== "." && part !== "..")
    .join("/");
  if (!sanitized) {
    throw new HttpError(400, "task target_label is invalid.");
  }
  return sanitized.slice(0, 240);
}

function sanitizeTaskError(value) {
  return String(value || "").trim().slice(0, 240);
}

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizeTaskRegistryRecord(workspace, actor, body = {}, existingRecord = null) {
  const now = isoNow();
  const id = String(body.id || existingRecord?.id || "").trim();
  if (!id) {
    throw new HttpError(400, "task id is required.");
  }
  const targetType = String(body.target_type || existingRecord?.target_type || "").trim();
  if (!["file", "directory"].includes(targetType)) {
    throw new HttpError(400, "task target_type must be file or directory.");
  }
  const syncMode = String(body.sync_mode || existingRecord?.sync_mode || "").trim();
  if (!SUPPORTED_TASK_MODES.has(syncMode)) {
    throw new HttpError(400, "task sync_mode must be interval, on-change, instant, or hybrid.");
  }
  const direction = String(body.direction || existingRecord?.direction || "upload-only").trim();
  if (!SUPPORTED_TASK_DIRECTIONS.has(direction)) {
    throw new HttpError(400, "task direction must be upload-only in this build.");
  }

  const createdAt = existingRecord?.created_at || String(body.created_at || "").trim() || now;
  const createdBy = existingRecord?.created_by || String(body.created_by || actor || "").trim() || actor;

  return {
    id,
    workspace_id: workspace.id,
    workspace_name: workspace.name,
    target_type: targetType,
    target_label: sanitizeTargetLabel(body.target_label || existingRecord?.target_label || ""),
    sync_mode: syncMode,
    interval_value: Math.max(toNumber(body.interval_value, existingRecord?.interval_value || 0), 0),
    interval_unit: String(body.interval_unit || existingRecord?.interval_unit || "").trim().slice(0, 16),
    enabled: body.enabled !== undefined ? !!body.enabled : existingRecord?.enabled !== false,
    debounce_seconds: Math.max(toNumber(body.debounce_seconds, existingRecord?.debounce_seconds || 0), 0),
    recursive: body.recursive !== undefined ? !!body.recursive : existingRecord?.recursive !== false,
    include_patterns: normalizePatternList(body.include_patterns ?? existingRecord?.include_patterns),
    exclude_patterns: normalizePatternList(body.exclude_patterns ?? existingRecord?.exclude_patterns),
    status: String(body.status || existingRecord?.status || "idle").trim().slice(0, 32),
    last_run_at: String(body.last_run_at || existingRecord?.last_run_at || "").trim(),
    last_success_at: String(body.last_success_at || existingRecord?.last_success_at || "").trim(),
    last_error: sanitizeTaskError(body.last_error || existingRecord?.last_error || ""),
    created_by: createdBy,
    created_at: createdAt,
    updated_at: now,
    direction,
    conflict_strategy: String(body.conflict_strategy || existingRecord?.conflict_strategy || "manual-placeholder").trim().slice(0, 64),
    watch_poll_seconds: Math.max(toNumber(body.watch_poll_seconds, existingRecord?.watch_poll_seconds || 2), 0.5),
    source: "cheri_cli",
    last_synced_by: actor,
    last_synced_at: now,
  };
}

export function serializeTaskRegistryRecord(task = {}) {
  return {
    id: task.id || "",
    workspace_id: task.workspace_id || "",
    workspace_name: task.workspace_name || "",
    target_type: task.target_type || "file",
    target_label: task.target_label || "",
    sync_mode: task.sync_mode || "on-change",
    interval_value: Number(task.interval_value || 0),
    interval_unit: task.interval_unit || "",
    enabled: task.enabled !== false,
    debounce_seconds: Number(task.debounce_seconds || 0),
    recursive: task.recursive !== false,
    include_patterns: Array.isArray(task.include_patterns) ? task.include_patterns : [],
    exclude_patterns: Array.isArray(task.exclude_patterns) ? task.exclude_patterns : [],
    status: task.status || "idle",
    last_run_at: task.last_run_at || "",
    last_success_at: task.last_success_at || "",
    last_error: task.last_error || "",
    created_by: task.created_by || "",
    created_at: task.created_at || "",
    updated_at: task.updated_at || "",
    direction: task.direction || "upload-only",
    conflict_strategy: task.conflict_strategy || "manual-placeholder",
    watch_poll_seconds: Number(task.watch_poll_seconds || 2),
    source: task.source || "cheri_cli",
    last_synced_by: task.last_synced_by || "",
    last_synced_at: task.last_synced_at || "",
  };
}

export async function listWorkspaceTasks(env, workspace) {
  const tasks = await listTasksByWorkspace(env, workspace.id);
  return tasks
    .map(serializeTaskRegistryRecord)
    .sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
}

export async function upsertWorkspaceTask(env, workspace, user, body = {}) {
  const existingRecord = body?.id ? await loadTaskRecord(env, workspace.id, String(body.id).trim()) : null;
  const task = normalizeTaskRegistryRecord(workspace, user.username, body, existingRecord);
  await saveTaskRecord(env, task);
  await appendActivity(
    env,
    workspace.id,
    user.username,
    existingRecord ? "task_registry_updated" : "task_registry_created",
    `Task ${task.id} synced`,
    {
      task_id: task.id,
      target: task.target_label,
      mode: task.sync_mode,
      enabled: task.enabled,
      status: task.status,
    },
  );
  return serializeTaskRegistryRecord(task);
}

export async function removeWorkspaceTask(env, workspace, user, taskId) {
  const existingRecord = await loadTaskRecord(env, workspace.id, taskId);
  if (!existingRecord) {
    throw new HttpError(404, "Task record not found.");
  }
  await deleteTaskRecord(env, workspace.id, taskId);
  await appendActivity(
    env,
    workspace.id,
    user.username,
    "task_registry_removed",
    `Task ${taskId} removed`,
    {
      task_id: taskId,
      target: existingRecord.target_label || "",
    },
  );
  return serializeTaskRegistryRecord(existingRecord);
}
