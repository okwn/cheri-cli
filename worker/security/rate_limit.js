import { HttpError } from "../lib/http.js";
import { kvGet, kvSet } from "../lib/storage.js";
import { isoNow, sha256 } from "./tokens.js";

function clientFingerprint(request) {
  const forwarded = request.headers.get("CF-Connecting-IP")
    || request.headers.get("X-Forwarded-For")
    || request.headers.get("X-Real-IP")
    || "anonymous";
  const userAgent = request.headers.get("User-Agent") || "unknown";
  return `${forwarded}|${userAgent.slice(0, 160)}`;
}

export async function enforceRateLimit(request, env, scope, options = {}) {
  const limit = Number(options.limit || 30);
  const windowSeconds = Number(options.windowSeconds || 60);
  const scopeKey = String(scope || "default").trim() || "default";
  const bucket = Math.floor(Date.now() / (windowSeconds * 1000));
  const identityHash = await sha256(clientFingerprint(request));
  const key = `rate-limit:${scopeKey}:${identityHash}:${bucket}`;
  const current = (await kvGet(env, key)) || {
    scope: scopeKey,
    count: 0,
    first_seen_at: isoNow(),
  };
  current.count += 1;
  current.updated_at = isoNow();
  await kvSet(env, key, current, { expirationTtl: windowSeconds + 60 });
  if (current.count > limit) {
    throw new HttpError(429, "Too many requests. Try again soon.");
  }
}
