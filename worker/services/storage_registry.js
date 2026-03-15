import { createId, isoNow, normalizeLogicalName, safeLogicalName } from "../security/tokens.js";
import { getWorkspaceProviderConfig } from "./provider_config.js";

export function buildProviderObjectReference({ workspaceId, fileId, version, logicalName }) {
  const providerObjectKey = `${workspaceId}/${fileId}/v${version}/${safeLogicalName(logicalName)}`;
  return {
    provider_object_key: providerObjectKey,
    provider_object_id: providerObjectKey,
  };
}

function nextHistoryEntry(file, fallbackModifiedAt) {
  return {
    version: file.version || 1,
    revision_marker: file.revision_marker || "",
    provider_object_key: file.provider_object_key || "",
    provider_object_id: file.provider_object_id || "",
    checksum: file.checksum || "",
    updated_at: file.updated_at || file.uploaded_at || fallbackModifiedAt,
    size: file.size || 0,
    last_modified_by: file.last_modified_by || file.uploaded_by || "",
    sync_status: file.sync_status || "synced",
  };
}

export function normalizeStoredFileRecord(file = {}) {
  const logicalName = file.logical_name || file.name || "";
  const version = Number(file.version || 1);
  const updatedAt = file.updated_at || file.modified_at || file.uploaded_at || file.created_at || "";
  const uploadedAt = file.uploaded_at || file.created_at || updatedAt;
  const createdAt = file.created_at || uploadedAt || updatedAt;
  const providerObjectKey = file.provider_object_key || file.storage_key || "";
  const providerObjectId = file.provider_object_id || providerObjectKey;
  const uploadedBy = file.uploaded_by || file.uploader || "";
  const lastModifiedBy = file.last_modified_by || file.editor || uploadedBy;
  const status = file.status || "available";
  const syncStatus = file.sync_status || (status === "available" ? "synced" : "pending");

  return {
    ...file,
    workspace_id: file.workspace_id || "",
    logical_name: logicalName,
    logical_name_key: file.logical_name_key || file.name_key || normalizeLogicalName(logicalName).toLowerCase(),
    provider_kind: file.provider_kind || "system",
    provider_object_key: providerObjectKey,
    provider_object_id: providerObjectId,
    size: Number(file.size || 0),
    content_type: file.content_type || file.mime_type || "application/octet-stream",
    created_at: createdAt,
    updated_at: updatedAt,
    uploaded_at: uploadedAt,
    uploaded_by: uploadedBy,
    last_modified_by: lastModifiedBy,
    version,
    revision_marker: file.revision_marker || `v${version}`,
    remote_revision: file.remote_revision || file.revision_marker || "",
    checksum: file.checksum || "",
    local_modified_at: file.local_modified_at || "",
    sync_status: syncStatus,
    conflict_state: file.conflict_state || "clear",
    status,
    history: Array.isArray(file.history) ? file.history : [],
  };
}

export function createFileRegistryRecord({
  workspace,
  actorUsername,
  filename,
  size,
  contentType,
  checksum,
  localModifiedAt,
  existingFile,
}) {
  const now = isoNow();
  const logicalName = normalizeLogicalName(filename);
  const logicalNameKey = logicalName.toLowerCase();
  const providerConfig = getWorkspaceProviderConfig(workspace);
  if (existingFile) {
    const nextVersion = Number(existingFile.version || 1) + 1;
    const objectReference = buildProviderObjectReference({
      workspaceId: workspace.id,
      fileId: existingFile.id,
      version: nextVersion,
      logicalName,
    });
    return {
      ...existingFile,
      logical_name: logicalName,
      logical_name_key: logicalNameKey,
      provider_kind: providerConfig.kind,
      size,
      content_type: contentType || "application/octet-stream",
      checksum: checksum || "",
      local_modified_at: localModifiedAt || "",
      updated_at: now,
      last_modified_by: actorUsername,
      version: nextVersion,
      revision_marker: `v${nextVersion}`,
      remote_revision: existingFile.remote_revision || existingFile.revision_marker || "",
      sync_status: "upload_pending",
      conflict_state: "clear",
      history: [
        ...(existingFile.history || []),
        nextHistoryEntry(existingFile, now),
      ],
      ...objectReference,
    };
  }

  const fileId = `file_${createId(12)}`;
  const objectReference = buildProviderObjectReference({
    workspaceId: workspace.id,
    fileId,
    version: 1,
    logicalName,
  });
  return {
    id: fileId,
    workspace_id: workspace.id,
    logical_name: logicalName,
    logical_name_key: logicalNameKey,
    provider_kind: providerConfig.kind,
    provider_object_key: objectReference.provider_object_key,
    provider_object_id: objectReference.provider_object_id,
    size,
    content_type: contentType || "application/octet-stream",
    created_at: now,
    updated_at: now,
    uploaded_at: "",
    uploaded_by: actorUsername,
    last_modified_by: actorUsername,
    version: 1,
    revision_marker: "v1",
    remote_revision: "",
    checksum: checksum || "",
    local_modified_at: localModifiedAt || "",
    sync_status: "upload_pending",
    conflict_state: "clear",
    status: "upload_pending",
    history: [],
  };
}

export function applyProviderStatToFileRecord(file, providerStat = {}) {
  const now = isoNow();
  return {
    ...file,
    provider_object_key: providerStat.provider_object_key || file.provider_object_key,
    provider_object_id: providerStat.provider_object_id || file.provider_object_id,
    size: providerStat.size ?? file.size,
    content_type: providerStat.content_type || file.content_type,
    uploaded_at: file.uploaded_at || providerStat.uploaded_at || now,
    updated_at: now,
    revision_marker: providerStat.etag || providerStat.revision_marker || file.revision_marker,
    remote_revision: providerStat.etag || providerStat.revision_marker || file.remote_revision || file.revision_marker,
    sync_status: "uploaded",
    status: "uploaded",
  };
}

export function finalizeFileRegistryRecord(file) {
  const normalized = normalizeStoredFileRecord(file);
  const now = isoNow();
  return {
    ...normalized,
    uploaded_at: normalized.uploaded_at || now,
    updated_at: now,
    sync_status: "synced",
    status: "available",
    conflict_state: normalized.conflict_state || "clear",
  };
}

export function serializeFileRecord(file) {
  const normalized = normalizeStoredFileRecord(file);
  return {
    id: normalized.id,
    workspace_id: normalized.workspace_id,
    logical_name: normalized.logical_name,
    name: normalized.logical_name,
    provider_kind: normalized.provider_kind,
    provider_object_key: normalized.provider_object_key,
    provider_object_id: normalized.provider_object_id,
    size: normalized.size,
    content_type: normalized.content_type,
    mime_type: normalized.content_type,
    created_at: normalized.created_at,
    updated_at: normalized.updated_at,
    uploaded_at: normalized.uploaded_at || normalized.updated_at,
    modified_at: normalized.updated_at,
    uploaded_by: normalized.uploaded_by,
    uploader: normalized.uploaded_by,
    last_modified_by: normalized.last_modified_by,
    editor: normalized.last_modified_by,
    version: normalized.version,
    revision_marker: normalized.revision_marker,
    remote_revision: normalized.remote_revision,
    checksum: normalized.checksum || "",
    local_modified_at: normalized.local_modified_at || "",
    sync_status: normalized.sync_status || "synced",
    conflict_state: normalized.conflict_state || "clear",
    status: normalized.status || "available",
  };
}

export function sortFileRegistry(files) {
  return [...files].sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
}
