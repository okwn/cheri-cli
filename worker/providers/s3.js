import { BaseStorageProvider } from "./base.js";

export class S3CompatibleStorageProvider extends BaseStorageProvider {
  async validateConfig() {
    const endpoint = String(this.providerConfig.settings?.endpoint || "");
    const warnings = [];
    if (!/^https?:\/\//i.test(endpoint)) {
      warnings.push("S3-compatible endpoint should include http:// or https://.");
    }
    warnings.push("S3-compatible transport is scaffolded but not enabled in this deployment.");
    return this.validationResult({
      state: "validated-config",
      available: false,
      warnings,
    });
  }
}
