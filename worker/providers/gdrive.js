import { BaseStorageProvider } from "./base.js";

export class GoogleDriveStorageProvider extends BaseStorageProvider {
  async validateConfig() {
    return this.validationResult({
      state: "validated-config",
      available: false,
      warnings: ["Google Drive transport is scaffolded but not enabled in this deployment."],
    });
  }
}
