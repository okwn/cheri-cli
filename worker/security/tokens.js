const BOOTSTRAP_WORDS = [
  "amber", "anchor", "apple", "atlas", "bamboo", "beacon", "berry", "birch",
  "candle", "cedar", "cloud", "cobalt", "coral", "copper", "dawn", "delta",
  "ember", "falcon", "field", "forest", "frost", "garden", "glow", "harbor",
  "hazel", "horizon", "island", "ivy", "juniper", "lagoon", "lantern", "linen",
  "maple", "meadow", "mesa", "mint", "mist", "moon", "moss", "nectar",
  "oak", "olive", "opal", "orbit", "pearl", "pine", "plaza", "quartz",
  "raven", "river", "saffron", "sage", "shore", "signal", "silver", "spruce",
  "stone", "summit", "sunrise", "timber", "topaz", "valley", "willow", "zephyr",
];

const TOKEN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function randomByte() {
  const buffer = new Uint8Array(1);
  crypto.getRandomValues(buffer);
  return buffer[0];
}

function randomIndex(maxExclusive) {
  if (!Number.isInteger(maxExclusive) || maxExclusive <= 0 || maxExclusive > 256) {
    throw new Error("randomIndex maxExclusive must be an integer between 1 and 256.");
  }
  const upperBound = Math.floor(256 / maxExclusive) * maxExclusive;
  while (true) {
    const value = randomByte();
    if (value < upperBound) {
      return value % maxExclusive;
    }
  }
}

function randomString(alphabet, length) {
  return Array.from({ length }, () => alphabet[randomIndex(alphabet.length)]).join("");
}

export function isoNow() {
  return new Date().toISOString();
}

export function createId(length = 16) {
  return randomString("0123456789abcdef", length);
}

export function createSessionToken(length = 40) {
  return randomString(TOKEN_ALPHABET, length);
}

export function createGrantToken(length = 48) {
  return randomString(TOKEN_ALPHABET, length);
}

export function createInviteCode() {
  return `CHR-TEAM-${randomString(INVITE_ALPHABET, 8)}`;
}

export function createBootstrapSecret(wordCount = 12) {
  return Array.from({ length: wordCount }, () => BOOTSTRAP_WORDS[randomIndex(BOOTSTRAP_WORDS.length)]).join(" ");
}

export async function sha256(text) {
  const buffer = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buffer)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function normalizeUsername(value) {
  return String(value || "").trim().toLowerCase();
}

export function normalizeWorkspaceName(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

export function slugify(value) {
  return normalizeWorkspaceName(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function normalizeFilename(value) {
  const parts = normalizeLogicalName(value).split("/").filter(Boolean);
  return (parts[parts.length - 1] || "file").slice(0, 160);
}

export function safeFilename(value) {
  return encodeURIComponent(normalizeFilename(value)).replace(/%20/g, "-");
}

export function normalizeLogicalName(value) {
  const normalized = String(value || "")
    .replace(/\\/g, "/")
    .split("/")
    .map((part) => part.trim())
    .filter((part) => part && part !== "." && part !== "..")
    .map((part) => part.slice(0, 160))
    .join("/");
  return normalized || "file";
}

export function safeLogicalName(value) {
  return normalizeLogicalName(value)
    .split("/")
    .map((part) => encodeURIComponent(part).replace(/%20/g, "-"))
    .join("/");
}
