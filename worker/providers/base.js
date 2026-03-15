import { HttpError } from "../lib/http.js";

export class BaseStorageProvider {
  constructor(env, providerConfig, definition) {
    this.env = env;
    this.providerConfig = providerConfig;
    this.definition = definition;
  }

  validationResult(overrides = {}) {
    return {
      state: "configured",
      available: false,
      errors: [],
      warnings: [],
      ...overrides,
    };
  }

  async validateConfig() {
    return this.validationResult({
      warnings: [`${this.definition.label} is scaffolded but not enabled in this deployment.`],
    });
  }

  unavailable(action) {
    throw new HttpError(503, `${this.definition.label} cannot ${action} in this deployment.`);
  }

  async putObject() {
    return this.unavailable("store files");
  }

  async getObject() {
    return this.unavailable("read files");
  }

  async deleteObject() {
    return this.unavailable("delete files");
  }

  async listObjects() {
    return this.unavailable("list objects");
  }

  async statObject() {
    return this.unavailable("inspect objects");
  }

  async generateUploadTarget({ providerObjectKey, providerObjectId }) {
    return {
      mode: "worker_proxy",
      provider_object_key: providerObjectKey,
      provider_object_id: providerObjectId || providerObjectKey,
      headers: {},
    };
  }

  async generateDownloadTarget({ providerObjectKey, providerObjectId }) {
    return {
      mode: "worker_proxy",
      provider_object_key: providerObjectKey,
      provider_object_id: providerObjectId || providerObjectKey,
      headers: {},
    };
  }
}
