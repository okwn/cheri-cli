import { BaseStorageProvider } from "./base.js";

export class BackblazeB2StorageProvider extends BaseStorageProvider {
  async validateConfig() {
    return this.validationResult({
      state: "validated-config",
      available: false,
      warnings: ["Backblaze B2 transport is scaffolded but not enabled in this deployment."],
    });
  }
}
