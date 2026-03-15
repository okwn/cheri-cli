import { BaseStorageProvider } from "./base.js";

function httpMetadataToContentType(metadata = {}) {
  return metadata.contentType || metadata.content_type || "application/octet-stream";
}

export class SystemStorageProvider extends BaseStorageProvider {
  async validateConfig() {
    if (!this.env?.HERMES_BUCKET) {
      return this.validationResult({
        state: "misconfigured",
        available: false,
        errors: ["HERMES_BUCKET is not configured in this deployment."],
      });
    }
    return this.validationResult({
      state: "ready",
      available: true,
      warnings: ["System storage is temporary. Files are reset daily."],
    });
  }

  async putObject({ providerObjectKey, body, contentType, metadata = {} }) {
    await this.env.HERMES_BUCKET.put(providerObjectKey, body, {
      httpMetadata: { contentType },
      customMetadata: metadata,
    });
    return {
      provider_object_key: providerObjectKey,
      provider_object_id: providerObjectKey,
    };
  }

  async getObject({ providerObjectKey }) {
    const object = await this.env.HERMES_BUCKET.get(providerObjectKey);
    if (!object) {
      return null;
    }
    return {
      body: object.body,
      size: object.size,
      content_type: httpMetadataToContentType(object.httpMetadata),
      etag: object.etag || "",
      uploaded_at: object.uploaded?.toISOString?.() || "",
      provider_object_key: providerObjectKey,
      provider_object_id: providerObjectKey,
    };
  }

  async deleteObject({ providerObjectKey }) {
    await this.env.HERMES_BUCKET.delete(providerObjectKey);
  }

  async listObjects({ prefix }) {
    const listed = await this.env.HERMES_BUCKET.list({ prefix });
    return (listed.objects || []).map((object) => ({
      provider_object_key: object.key,
      provider_object_id: object.key,
      size: object.size || 0,
      uploaded_at: object.uploaded?.toISOString?.() || "",
      etag: object.etag || "",
    }));
  }

  async statObject({ providerObjectKey }) {
    const head = await this.env.HERMES_BUCKET.head(providerObjectKey);
    if (!head) {
      return null;
    }
    return {
      provider_object_key: providerObjectKey,
      provider_object_id: providerObjectKey,
      size: head.size || 0,
      content_type: httpMetadataToContentType(head.httpMetadata),
      etag: head.etag || "",
      uploaded_at: head.uploaded?.toISOString?.() || "",
    };
  }
}
