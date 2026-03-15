function parseAllowedOrigins(env) {
  return String(env?.CHERI_CORS_ORIGINS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

export class HttpError extends Error {
  constructor(status, message, extra = {}) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.extra = extra;
  }
}

export function corsHeaders(request, env) {
  const origin = request?.headers?.get("Origin") || "";
  const allowedOrigins = parseAllowedOrigins(env);
  if (!origin || allowedOrigins.length === 0) {
    return {};
  }
  if (!(allowedOrigins.includes("*") || allowedOrigins.includes(origin))) {
    return {};
  }
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Authorization,Content-Type,X-Workspace-ID",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

export function securityHeaders(request, env, extra = {}) {
  return {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    ...corsHeaders(request, env),
    ...extra,
  };
}

export function json(data, status = 200, request = null, env = null) {
  return new Response(JSON.stringify(data), {
    status,
    headers: securityHeaders(request, env, {
      "Content-Type": "application/json",
    }),
  });
}

export function errorResponse(error, request = null, env = null) {
  if (error instanceof HttpError) {
    return json({ error: error.message, ...error.extra }, error.status, request, env);
  }
  return json({ error: "Internal server error." }, 500, request, env);
}

export function optionsResponse(request, env) {
  const headers = corsHeaders(request, env);
  if (!Object.keys(headers).length) {
    return new Response(null, { status: 403, headers: securityHeaders(request, env) });
  }
  return new Response(null, { status: 204, headers });
}

export async function parseJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}
