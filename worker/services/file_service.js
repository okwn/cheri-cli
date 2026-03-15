import { appendActivity } from "../activity/service.js";
import { HttpError, securityHeaders } from "../lib/http.js";
import {
  deleteDownloadGrant,
  deleteFileRecord,
  deleteUploadGrant,
  getFileByName,
  listFilesByWorkspace,
  loadDownloadGrant,
  loadFileRecord,
  loadUploadGrant,
  loadWorkspace,
  saveDownloadGrant,
  saveFileRecord,
  saveUploadGrant,
  listJsonByPrefix,
} from "../lib/storage.js";
import { instantiateStorageProvider, getWorkspaceProviderConfig, resolveWorkspaceProviderConfig } from "./provider_config.js";
import {
  applyProviderStatToFileRecord,
  createFileRegistryRecord,
  finalizeFileRegistryRecord,
  normalizeStoredFileRecord,
  serializeFileRecord,
  sortFileRegistry,
} from "./storage_registry.js";
import { createGrantToken } from "../security/tokens.js";
import { optionalString, requiredString } from "../lib/validate.js";

async function getWorkspaceStorageProvider(env, workspace) {
  const providerConfig = await resolveWorkspaceProviderConfig(env, workspace);
  if (!providerConfig) {
    throw new HttpError(500, "Workspace storage provider is not configured.");
  }
  return instantiateStorageProvider(env, providerConfig);
}

export async function listWorkspaceFiles(env, workspaceId) {
  const files = await listFilesByWorkspace(env, workspaceId);
  return sortFileRegistry(files.map(normalizeStoredFileRecord))
    .filter((file) => file.status === "available")
    .map(serializeFileRecord);
}

export async function createUploadGrant(env, workspace, user, body, origin) {
  const logicalName = requiredString(body?.filename, "filename", { minLength: 1, maxLength: 320 });
  const size = Number(body?.size || 0);
  if (!Number.isFinite(size) || size < 0 || size > 1024 * 1024 * 1024) {
    throw new HttpError(400, "size must be a non-negative number below 1 GB.");
  }

  const provider = await getWorkspaceStorageProvider(env, workspace);
  const providerValidation = await provider.validateConfig();
  const providerConfig = getWorkspaceProviderConfig(workspace);
  if (!providerValidation.available) {
    throw new HttpError(503, `${providerConfig?.label || "Workspace storage"} is not available for file transfers in this deployment.`);
  }

  const existingFileRecord = await getFileByName(env, workspace.id, logicalName);
  const existingFile = existingFileRecord ? normalizeStoredFileRecord(existingFileRecord) : null;
  const file = createFileRegistryRecord({
    workspace,
    actorUsername: user.username,
    filename: logicalName,
    size,
    contentType: optionalString(body?.mime_type, "mime_type", { minLength: 0, maxLength: 120 }) || "application/octet-stream",
    checksum: optionalString(body?.checksum, "checksum", { minLength: 0, maxLength: 128 }),
    localModifiedAt: optionalString(body?.local_modified_at, "local_modified_at", { minLength: 0, maxLength: 64 }),
    existingFile,
  });
  await saveFileRecord(env, file);

  const uploadToken = createGrantToken();
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();
  const uploadTarget = await provider.generateUploadTarget({
    workspace,
    file,
    expires_at: expiresAt,
  });
  await saveUploadGrant(env, uploadToken, {
    workspace_id: workspace.id,
    file_id: file.id,
    provider_kind: file.provider_kind,
    provider_object_key: file.provider_object_key,
    provider_object_id: file.provider_object_id,
    content_type: file.content_type,
    expires_at: expiresAt,
    requested_by: user.username,
    target: uploadTarget,
  }, 10 * 60);

  return {
    file_id: file.id,
    provider: {
      kind: file.provider_kind,
      object_key: file.provider_object_key,
      object_id: file.provider_object_id,
    },
    upload_url: `${origin}/v1/transfers/upload/${uploadToken}`,
    expires_at: expiresAt,
  };
}

export async function consumeUpload(env, token, request) {
  const grant = await loadUploadGrant(env, token);
  if (!grant) {
    throw new HttpError(403, "Invalid or expired upload grant.");
  }
  const workspace = await loadWorkspace(env, grant.workspace_id);
  if (!workspace) {
    throw new HttpError(404, "Workspace not found.");
  }
  const storedFile = await loadFileRecord(env, grant.workspace_id, grant.file_id);
  const file = storedFile ? normalizeStoredFileRecord(storedFile) : null;
  if (!file) {
    throw new HttpError(404, "File record not found.");
  }

  const provider = await getWorkspaceStorageProvider(env, workspace);
  await provider.putObject({
    providerObjectKey: grant.provider_object_key,
    providerObjectId: grant.provider_object_id,
    body: request.body,
    contentType: file.content_type,
    metadata: {
      workspace_id: grant.workspace_id,
      file_id: file.id,
      version: String(file.version),
    },
  });

  const providerStat = await provider.statObject({
    providerObjectKey: grant.provider_object_key,
    providerObjectId: grant.provider_object_id,
  });
  const updatedFileRecord = applyProviderStatToFileRecord(file, providerStat || {});
  await saveFileRecord(env, updatedFileRecord);
  await deleteUploadGrant(env, token);
  return { ok: true, file_id: file.id };
}

export async function completeUpload(env, workspace, user, fileId) {
  const storedFile = await loadFileRecord(env, workspace.id, fileId);
  const file = storedFile ? normalizeStoredFileRecord(storedFile) : null;
  if (!file) {
    return null;
  }
  if (file.status !== "uploaded" && file.status !== "available") {
    throw new HttpError(409, "Upload has not completed yet.");
  }
  const finalizedFile = finalizeFileRegistryRecord(file);
  await saveFileRecord(env, finalizedFile);
  await appendActivity(
    env,
    workspace.id,
    user.username,
    finalizedFile.version > 1 ? "file_modified" : "file_uploaded",
    finalizedFile.logical_name,
    {
      file_id: finalizedFile.id,
      provider: finalizedFile.provider_kind,
      provider_object_id: finalizedFile.provider_object_id,
      revision_marker: finalizedFile.revision_marker,
      version: finalizedFile.version,
      sync_status: finalizedFile.sync_status,
    },
  );
  return serializeFileRecord(finalizedFile);
}

export async function createDownloadGrant(env, workspace, user, fileId, origin) {
  const storedFile = await loadFileRecord(env, workspace.id, fileId);
  const file = storedFile ? normalizeStoredFileRecord(storedFile) : null;
  if (!file || file.status !== "available") {
    return null;
  }

  const provider = await getWorkspaceStorageProvider(env, workspace);
  const downloadToken = createGrantToken();
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();
  const downloadTarget = await provider.generateDownloadTarget({
    workspace,
    file,
    expires_at: expiresAt,
  });
  await saveDownloadGrant(env, downloadToken, {
    workspace_id: workspace.id,
    file_id: file.id,
    provider_kind: file.provider_kind,
    provider_object_key: file.provider_object_key,
    provider_object_id: file.provider_object_id,
    expires_at: expiresAt,
    requested_by: user.username,
    target: downloadTarget,
  }, 10 * 60);

  return {
    file_id: file.id,
    filename: file.logical_name,
    provider: {
      kind: file.provider_kind,
      object_key: file.provider_object_key,
      object_id: file.provider_object_id,
    },
    download_url: `${origin}/v1/transfers/download/${downloadToken}`,
    expires_at: expiresAt,
  };
}

export async function consumeDownload(env, token) {
  const grant = await loadDownloadGrant(env, token);
  if (!grant) {
    throw new HttpError(403, "Invalid or expired download grant.");
  }
  const workspace = await loadWorkspace(env, grant.workspace_id);
  if (!workspace) {
    throw new HttpError(404, "Workspace not found.");
  }
  const storedFile = await loadFileRecord(env, grant.workspace_id, grant.file_id);
  const file = storedFile ? normalizeStoredFileRecord(storedFile) : null;
  if (!file || file.status !== "available") {
    throw new HttpError(404, "File not found.");
  }

  const provider = await getWorkspaceStorageProvider(env, workspace);
  const object = await provider.getObject({
    providerObjectKey: grant.provider_object_key,
    providerObjectId: grant.provider_object_id,
  });
  if (!object) {
    throw new HttpError(404, "File blob missing.");
  }

  await appendActivity(
    env,
    workspace.id,
    grant.requested_by || "session_member",
    "file_downloaded",
    file.logical_name,
    {
      file_id: file.id,
      provider: file.provider_kind,
      revision_marker: file.revision_marker,
      version: file.version,
    },
  );
  await deleteDownloadGrant(env, token);
  return new Response(object.body, {
    headers: {
      "Content-Type": object.content_type || file.content_type,
      "Content-Disposition": `attachment; filename="${file.logical_name.replace(/"/g, "")}"`,
      ...securityHeaders(null, null),
    },
  });
}

export async function cleanupExpiredSystemFiles(env) {
  const workspaces = await listJsonByPrefix(env, "workspace:");
  for (const workspace of workspaces) {
    const providerConfig = getWorkspaceProviderConfig(workspace);
    if (!providerConfig || providerConfig.kind !== "system") {
      continue;
    }
    const provider = instantiateStorageProvider(env, providerConfig);
    const files = (await listFilesByWorkspace(env, workspace.id)).map(normalizeStoredFileRecord);
    let removedCount = 0;
    for (const file of files) {
      const updatedAt = Date.parse(file.updated_at || file.uploaded_at || file.created_at || "");
      if (!updatedAt || (Date.now() - updatedAt) < 24 * 3600 * 1000) {
        continue;
      }
      try {
        await provider.deleteObject({
          providerObjectKey: file.provider_object_key,
          providerObjectId: file.provider_object_id,
        });
      } catch {
        // Ignore missing blobs during cleanup.
      }
      await deleteFileRecord(env, file);
      removedCount += 1;
    }
    if (removedCount > 0) {
      await appendActivity(env, workspace.id, "SYSTEM", "system_storage_reset", `Removed ${removedCount} expired file(s).`);
    }
  }
}
