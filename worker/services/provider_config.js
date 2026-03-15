import { HttpError } from "../lib/http.js";
import { deleteProviderSecrets, loadProviderSecrets, saveProviderSecrets } from "../lib/storage.js";
import { isoNow } from "../security/tokens.js";
import { BackblazeB2StorageProvider } from "../providers/backblaze.js";
import { GoogleDriveStorageProvider } from "../providers/gdrive.js";
import { S3CompatibleStorageProvider } from "../providers/s3.js";
import { SystemStorageProvider } from "../providers/system.js";

const PROVIDER_DEFINITIONS = {
  "s3-compatible": {
    kind: "s3-compatible",
    label: "S3-compatible",
    description: "Use an S3-style bucket with explicit endpoint and credential fields.",
    recommended: false,
    temporary: false,
    selectable: false,
    comingSoon: true,
    experimental: true,
    resetPolicy: "",
    integrationStatus: "coming-soon",
    supportsDirectTransfers: false,
    supportsRemoteRevision: true,
    supportsChangeTracking: false,
    supportsIncrementalSync: true,
    fields: [
      { key: "endpoint", label: "Endpoint URL", required: true, secret: false },
      { key: "bucket", label: "Bucket name", required: true, secret: false },
      { key: "region", label: "Region", required: true, secret: false, default: "auto" },
      { key: "access_key_id", label: "Access key id", required: true, secret: false },
      { key: "secret_access_key", label: "Secret access key", required: true, secret: true },
    ],
  },
  "system": {
    kind: "system",
    label: "System (recommended)",
    description: "Worker-managed temporary storage for fast setup and testing.",
    recommended: true,
    temporary: true,
    selectable: true,
    comingSoon: false,
    experimental: false,
    resetPolicy: "daily",
    integrationStatus: "connected",
    supportsDirectTransfers: false,
    supportsRemoteRevision: true,
    supportsChangeTracking: false,
    supportsIncrementalSync: false,
    fields: [],
  },
  "google-drive": {
    kind: "google-drive",
    label: "Google Drive",
    description: "Store blobs in a shared Drive-backed workspace location.",
    recommended: false,
    temporary: false,
    selectable: false,
    comingSoon: true,
    experimental: true,
    resetPolicy: "",
    integrationStatus: "coming-soon",
    supportsDirectTransfers: false,
    supportsRemoteRevision: true,
    supportsChangeTracking: true,
    supportsIncrementalSync: true,
    fields: [
      { key: "drive_id", label: "Shared drive id", required: true, secret: false },
      { key: "folder_id", label: "Folder id", required: true, secret: false },
      { key: "service_account_email", label: "Service account email", required: true, secret: false },
      { key: "credential_reference", label: "Credential reference", required: true, secret: true },
    ],
  },
  "backblaze-b2": {
    kind: "backblaze-b2",
    label: "Backblaze B2",
    description: "Use a B2 bucket with explicit application key credentials.",
    recommended: false,
    temporary: false,
    selectable: false,
    comingSoon: true,
    experimental: true,
    resetPolicy: "",
    integrationStatus: "coming-soon",
    supportsDirectTransfers: false,
    supportsRemoteRevision: true,
    supportsChangeTracking: false,
    supportsIncrementalSync: true,
    fields: [
      { key: "bucket", label: "Bucket name", required: true, secret: false },
      { key: "key_id", label: "Application key id", required: true, secret: false },
      { key: "application_key", label: "Application key", required: true, secret: true },
    ],
  },
};

const PROVIDER_CLASSES = {
  "s3-compatible": S3CompatibleStorageProvider,
  "system": SystemStorageProvider,
  "google-drive": GoogleDriveStorageProvider,
  "backblaze-b2": BackblazeB2StorageProvider,
};

function experimentalProvidersEnabled(env) {
  return String(env?.CHERI_EXPERIMENTAL_PROVIDERS || "").trim() === "1";
}

function cloneFieldDefinition(field) {
  return {
    key: field.key,
    label: field.label,
    required: !!field.required,
    secret: !!field.secret,
    default: field.default || "",
  };
}

export function getProviderDefinition(kind) {
  const definition = PROVIDER_DEFINITIONS[kind];
  if (!definition) {
    throw new HttpError(400, `Unsupported storage provider: ${kind}`);
  }
  return definition;
}

function sanitizeSettings(definition, rawSettings = {}) {
  const normalized = {};
  for (const field of definition.fields) {
    const rawValue = rawSettings[field.key];
    if (typeof rawValue === "string") {
      normalized[field.key] = rawValue.trim();
    } else if (rawValue === undefined || rawValue === null) {
      normalized[field.key] = field.default || "";
    } else {
      normalized[field.key] = rawValue;
    }
  }
  return normalized;
}

function buildProviderMetadata(definition, options = {}) {
  return {
    description: definition.description,
    recommended: !!definition.recommended,
    temporary: !!definition.temporary,
    selectable: !!options.selectable,
    coming_soon: !!definition.comingSoon,
    experimental: !!definition.experimental,
    reset_policy: definition.resetPolicy || "",
    integration_status: definition.integrationStatus,
    supports_direct_transfers: !!definition.supportsDirectTransfers,
    supports_remote_revision: !!definition.supportsRemoteRevision,
    supports_change_tracking: !!definition.supportsChangeTracking,
    supports_incremental_sync: !!definition.supportsIncrementalSync,
    credential_fields: definition.fields.map(cloneFieldDefinition),
  };
}

function buildValidationState(overrides = {}) {
  return {
    state: overrides.state || "pending",
    available: !!overrides.available,
    checked_at: overrides.checked_at || isoNow(),
    warnings: overrides.warnings || [],
    errors: overrides.errors || [],
  };
}

function isSelectionAllowed(definition, env, allowExperimental) {
  if (definition.selectable) {
    return true;
  }
  return !!(definition.experimental && allowExperimental && experimentalProvidersEnabled(env));
}

function splitSecretSettings(definition, settings = {}) {
  const publicSettings = {};
  const secretSettings = {};
  for (const field of definition.fields) {
    const value = settings[field.key] || "";
    if (field.secret && value) {
      secretSettings[field.key] = value;
    } else if (!field.secret) {
      publicSettings[field.key] = value;
    }
  }
  return { publicSettings, secretSettings };
}

function providerCatalogEntry(definition, env, includeExperimental = false) {
  const experimentalSelectable = definition.experimental && includeExperimental && experimentalProvidersEnabled(env);
  return {
    kind: definition.kind,
    label: definition.label,
    description: definition.description,
    recommended: !!definition.recommended,
    temporary: !!definition.temporary,
    selectable: !!definition.selectable || experimentalSelectable,
    coming_soon: !!definition.comingSoon,
    experimental: !!definition.experimental,
    reset_policy: definition.resetPolicy || "",
    integration_status: definition.integrationStatus,
    supports_direct_transfers: !!definition.supportsDirectTransfers,
    supports_remote_revision: !!definition.supportsRemoteRevision,
    supports_change_tracking: !!definition.supportsChangeTracking,
    supports_incremental_sync: !!definition.supportsIncrementalSync,
    credential_fields: definition.fields.map(cloneFieldDefinition),
  };
}

export function instantiateStorageProvider(env, providerConfig) {
  const ProviderClass = PROVIDER_CLASSES[providerConfig.kind];
  if (!ProviderClass) {
    throw new HttpError(400, `Unsupported storage provider: ${providerConfig.kind}`);
  }
  return new ProviderClass(env, providerConfig, getProviderDefinition(providerConfig.kind));
}

export function normalizeProviderSelection(env, selection = {}, options = {}) {
  const allowExperimental = !!options.allowExperimental;
  const kind = String(selection.kind || "system").trim();
  const definition = getProviderDefinition(kind);
  if (!isSelectionAllowed(definition, env, allowExperimental || selection.experimental_acknowledged)) {
    throw new HttpError(400, `${definition.label} is coming soon and cannot be selected in the public setup flow yet.`);
  }
  const settings = sanitizeSettings(definition, selection.settings || selection.config || {});
  for (const field of definition.fields) {
    if (field.required && !String(settings[field.key] || "").trim()) {
      throw new HttpError(400, `${field.label} is required for ${definition.label}.`);
    }
  }
  if (kind === "system" && !selection.warning_acknowledged) {
    throw new HttpError(400, "System storage confirmation is required.");
  }
  return {
    kind,
    label: definition.label,
    temporary: !!definition.temporary,
    recommended: !!definition.recommended,
    selectable: !!definition.selectable,
    coming_soon: !!definition.comingSoon,
    experimental: !!definition.experimental,
    experimental_acknowledged: !!selection.experimental_acknowledged,
    warning_acknowledged: !!selection.warning_acknowledged,
    reset_policy: definition.resetPolicy || "",
    settings,
    secret_fields: [],
    secret_ref: "",
    metadata: buildProviderMetadata(definition, {
      selectable: isSelectionAllowed(definition, env, allowExperimental || selection.experimental_acknowledged),
    }),
    validation: buildValidationState(),
  };
}

export async function validateProviderSelection(env, selection = {}, options = {}) {
  const providerConfig = selection.metadata && selection.validation
    ? {
        ...selection,
        validation: buildValidationState(selection.validation),
      }
    : normalizeProviderSelection(env, selection, options);
  const provider = instantiateStorageProvider(env, providerConfig);
  const validation = await provider.validateConfig(providerConfig);
  providerConfig.validation = buildValidationState(validation);
  return providerConfig;
}

export async function prepareProviderForWorkspace(env, workspaceId, providerConfig) {
  const definition = getProviderDefinition(providerConfig.kind);
  const settings = sanitizeSettings(definition, providerConfig.settings || {});
  const { publicSettings, secretSettings } = splitSecretSettings(definition, settings);
  if (Object.keys(secretSettings).length > 0) {
    await saveProviderSecrets(env, workspaceId, providerConfig.kind, {
      secret_settings: secretSettings,
    });
  } else {
    await deleteProviderSecrets(env, workspaceId, providerConfig.kind);
  }
  return {
    ...providerConfig,
    settings: publicSettings,
    secret_fields: Object.keys(secretSettings),
    secret_ref: Object.keys(secretSettings).length > 0 ? `provider-secret:${workspaceId}:${providerConfig.kind}` : "",
  };
}

export async function resolveWorkspaceProviderConfig(env, workspace) {
  const providerConfig = getWorkspaceProviderConfig(workspace);
  if (!providerConfig) {
    return null;
  }
  if (!Array.isArray(providerConfig.secret_fields) || providerConfig.secret_fields.length === 0) {
    return providerConfig;
  }
  const secretRecord = await loadProviderSecrets(env, workspace.id, providerConfig.kind);
  return {
    ...providerConfig,
    settings: {
      ...(providerConfig.settings || {}),
      ...(secretRecord?.secret_settings || {}),
    },
  };
}

export async function createWorkspaceStorageState(env, workspaceId, providerConfig) {
  const storedProvider = await prepareProviderForWorkspace(env, workspaceId, providerConfig);
  return {
    provider: storedProvider,
    registry: {
      normalized_file_registry: true,
      conflict_detection_ready: true,
      version_comparison_ready: true,
      remote_revision_lookup_ready: true,
      incremental_sync_ready: true,
      provider_change_tracking_ready: !!storedProvider.metadata?.supports_change_tracking,
    },
    updated_at: isoNow(),
  };
}

export function getWorkspaceProviderConfig(workspace) {
  if (workspace?.storage?.provider) {
    return workspace.storage.provider;
  }
  if (workspace?.provider) {
    return workspace.provider;
  }
  return null;
}

export function redactProvider(providerConfig) {
  const definition = getProviderDefinition(providerConfig.kind);
  const redactedSettings = {};
  for (const field of definition.fields) {
    const value = providerConfig.settings?.[field.key];
    if (field.secret) {
      redactedSettings[field.key] = providerConfig.secret_fields?.includes(field.key) ? "***" : "";
    } else {
      redactedSettings[field.key] = value || "";
    }
  }
  return {
    kind: providerConfig.kind,
    label: providerConfig.label,
    temporary: !!providerConfig.temporary,
    recommended: !!providerConfig.recommended,
    selectable: !!providerConfig.selectable,
    coming_soon: !!providerConfig.coming_soon,
    experimental: !!providerConfig.experimental,
    warning_acknowledged: !!providerConfig.warning_acknowledged,
    reset_policy: providerConfig.reset_policy || "",
    settings: redactedSettings,
    secret_fields: providerConfig.secret_fields || [],
    metadata: providerConfig.metadata || buildProviderMetadata(definition, { selectable: providerConfig.selectable }),
    validation: providerConfig.validation || buildValidationState(),
  };
}

export function providerCatalog(env, options = {}) {
  const includeExperimental = !!options.includeExperimental;
  return Object.values(PROVIDER_DEFINITIONS).map((definition) => providerCatalogEntry(definition, env, includeExperimental));
}
