import { appendTaskActivity, buildActivityFeed } from "./activity/service.js";
import { loginUser, logoutUser, registerUser } from "./auth/service.js";
import { completeUpload, consumeDownload, consumeUpload, createDownloadGrant, createUploadGrant, cleanupExpiredSystemFiles, listWorkspaceFiles } from "./files/service.js";
import { errorResponse, json, optionsResponse, parseJson } from "./lib/http.js";
import { requireUserSession, requireWorkspaceAccess } from "./lib/storage.js";
import { providerCatalog, redactProvider, validateProviderSelection } from "./providers/index.js";
import { listWorkspaceTasks, removeWorkspaceTask, upsertWorkspaceTask } from "./services/task_registry.js";
import { acceptWorkspaceInvite, createWorkspaceInvite, listTeamSnapshot, resetWorkspaceInvites } from "./teams/service.js";
import { buildSessionPayload, listAccessibleWorkspaces, selectWorkspace } from "./workspace/service.js";
import { enforceRateLimit } from "./security/rate_limit.js";
import { booleanFlag } from "./lib/validate.js";

const CLI_SURFACE = [
  "cheri register",
  "cheri login",
  "cheri logout",
  "cheri workspace create --name <name>",
  "cheri workspace list",
  "cheri workspace use <id-or-name>",
  "cheri workspace join <invite-code>",
  "cheri file upload <path>",
  "cheri file download <file-or-id>",
  "cheri file list",
  "cheri teams invite",
  "cheri teams list",
  "cheri teams invite-reset",
  "cheri activity",
  "cheri task create",
  "cheri task list",
  "cheri task watch --all",
  "cheri help",
];

const LEGACY_WEB_ROUTE_PATTERNS = [
  /^\/dashboard(?:\/.*)?$/,
  /^\/invite(?:\/.*)?$/,
  /^\/approve(?:\/.*)?$/,
  /^\/device(?:\/.*)?$/,
  /^\/auth\/approve(?:\/.*)?$/,
  /^\/app(?:\/.*)?$/,
];

function apiManifest(env) {
  return {
    product: "Cheri CLI API",
    mode: "api_only",
    cli_surface: CLI_SURFACE,
    storage: {
      worker: "api_backend",
      blob_storage: "cloudflare_r2",
      registry_storage: "cloudflare_kv",
    },
    routes: {
      auth: ["/v1/auth/register", "/v1/auth/login", "/v1/auth/logout", "/v1/session"],
      workspaces: ["/v1/workspaces", "/v1/workspaces/select"],
      files: ["/v1/files", "/v1/files/upload-grant", "/v1/files/:id/complete", "/v1/files/:id/download-grant"],
      teams: ["/v1/teams", "/v1/teams/invites", "/v1/teams/invites/reset", "/v1/teams/invites/accept"],
      activity: ["/v1/activity", "/v1/task-events"],
      tasks: ["/v1/tasks", "/v1/tasks/:id"],
      providers: ["/v1/providers", "/v1/providers/validate"],
    },
    deprecated_web_surface: [
      "/dashboard",
      "/invite",
      "/approve",
      "/device",
      "/auth/approve",
      "/app",
    ],
    providers: providerCatalog(env),
  };
}

function isLegacyWebRoute(path) {
  return LEGACY_WEB_ROUTE_PATTERNS.some((pattern) => pattern.test(path));
}

function legacyWebRouteResponse(path, request, env) {
  return json(
    {
      error: "Legacy web and dashboard routes have been removed from Cheri's active product surface.",
      mode: "api_only",
      path,
      use_cli: true,
      guidance: [
        "Use the Cheri CLI instead of a browser dashboard.",
        "Run `cheri help` to discover the supported command groups.",
      ],
      backend_foundation: {
        worker: "api_backend",
        blob_storage: "cloudflare_r2",
        registry_storage: "cloudflare_kv",
      },
    },
    410,
    request,
    env,
  );
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return optionsResponse(request, env);
    }

    try {
      if (isLegacyWebRoute(path)) {
        return legacyWebRouteResponse(path, request, env);
      }

      if ((path === "/" || path === "/v1") && request.method === "GET") {
        return json(apiManifest(env), 200, request, env);
      }

      if (path === "/healthz" && request.method === "GET") {
        return json({
          ok: true,
          product: "Cheri CLI API",
          mode: "api_only",
          backend_foundation: {
            worker: "api_backend",
            blob_storage: "cloudflare_r2",
            registry_storage: "cloudflare_kv",
          },
        }, 200, request, env);
      }

      if (path === "/v1/providers" && request.method === "GET") {
        const includeExperimental = url.searchParams.get("include_experimental") === "1";
        return json({ providers: providerCatalog(env, { includeExperimental }) }, 200, request, env);
      }

      if (path === "/v1/providers/validate" && request.method === "POST") {
        const body = await parseJson(request);
        const provider = await validateProviderSelection(env, body?.provider || body, {
          allowExperimental: booleanFlag(body?.allow_experimental, false),
        });
        return json({ provider: redactProvider(provider) }, 200, request, env);
      }

      if (path === "/v1/auth/register" && request.method === "POST") {
        await enforceRateLimit(request, env, "auth-register", { limit: 8, windowSeconds: 15 * 60 });
        return json(await registerUser(env, await parseJson(request)), 201, request, env);
      }

      if (path === "/v1/auth/login" && request.method === "POST") {
        await enforceRateLimit(request, env, "auth-login", { limit: 12, windowSeconds: 15 * 60 });
        return json(await loginUser(env, await parseJson(request)), 200, request, env);
      }

      if (path === "/v1/auth/logout" && request.method === "POST") {
        const auth = await requireUserSession(request, env);
        await logoutUser(env, auth);
        return json({ ok: true }, 200, request, env);
      }

      if (path === "/v1/session" && request.method === "GET") {
        const auth = await requireUserSession(request, env);
        return json(await buildSessionPayload(env, auth.user, auth.user.last_active_workspace_id), 200, request, env);
      }

      if (path === "/v1/workspaces" && request.method === "GET") {
        const auth = await requireUserSession(request, env);
        return json({ workspaces: await listAccessibleWorkspaces(env, auth.user) }, 200, request, env);
      }

      if (path === "/v1/workspaces/select" && request.method === "POST") {
        const auth = await requireUserSession(request, env);
        return json(await selectWorkspace(env, auth.user, await parseJson(request)), 200, request, env);
      }

      if (path === "/v1/files" && request.method === "GET") {
        const access = await requireWorkspaceAccess(request, env);
        return json({ files: await listWorkspaceFiles(env, access.workspace.id) }, 200, request, env);
      }

      if (path === "/v1/files/upload-grant" && request.method === "POST") {
        await enforceRateLimit(request, env, "file-upload-grant", { limit: 120, windowSeconds: 5 * 60 });
        const access = await requireWorkspaceAccess(request, env);
        return json(await createUploadGrant(env, access.workspace, access.user, await parseJson(request), url.origin), 201, request, env);
      }

      if (path.startsWith("/v1/transfers/upload/") && request.method === "PUT") {
        return json(await consumeUpload(env, path.split("/")[4], request), 200, request, env);
      }

      if (path.match(/^\/v1\/files\/[^/]+\/complete$/) && request.method === "POST") {
        const access = await requireWorkspaceAccess(request, env);
        const file = await completeUpload(env, access.workspace, access.user, path.split("/")[3]);
        if (!file) {
          return json({ error: "File not found." }, 404, request, env);
        }
        return json({ ok: true, file }, 200, request, env);
      }

      if (path.match(/^\/v1\/files\/[^/]+\/download-grant$/) && request.method === "GET") {
        await enforceRateLimit(request, env, "file-download-grant", { limit: 120, windowSeconds: 5 * 60 });
        const access = await requireWorkspaceAccess(request, env);
        const grant = await createDownloadGrant(env, access.workspace, access.user, path.split("/")[3], url.origin);
        if (!grant) {
          return json({ error: "File not found." }, 404, request, env);
        }
        return json(grant, 200, request, env);
      }

      if (path.startsWith("/v1/transfers/download/") && request.method === "GET") {
        return consumeDownload(env, path.split("/")[4]);
      }

      if (path === "/v1/teams" && request.method === "GET") {
        const access = await requireWorkspaceAccess(request, env);
        return json(await listTeamSnapshot(env, access.workspace, access.user, access.membership), 200, request, env);
      }

      if (path === "/v1/teams/invites" && request.method === "POST") {
        await enforceRateLimit(request, env, "invite-create", { limit: 20, windowSeconds: 10 * 60 });
        const access = await requireWorkspaceAccess(request, env, { admin: true });
        const body = await parseJson(request);
        return json({ invite: await createWorkspaceInvite(env, access.workspace, access.user, body.label || "") }, 201, request, env);
      }

      if (path === "/v1/teams/invites/reset" && request.method === "POST") {
        await enforceRateLimit(request, env, "invite-reset", { limit: 10, windowSeconds: 10 * 60 });
        const access = await requireWorkspaceAccess(request, env, { admin: true });
        return json(await resetWorkspaceInvites(env, access.workspace, access.user, await parseJson(request)), 200, request, env);
      }

      if (path === "/v1/teams/invites/accept" && request.method === "POST") {
        await enforceRateLimit(request, env, "invite-accept", { limit: 30, windowSeconds: 15 * 60 });
        const auth = await requireUserSession(request, env);
        const body = await parseJson(request);
        return json(await acceptWorkspaceInvite(env, auth.user, body.invite_code), 200, request, env);
      }

      if (path === "/v1/activity" && request.method === "GET") {
        const access = await requireWorkspaceAccess(request, env);
        return json(await buildActivityFeed(env, access.workspace.id), 200, request, env);
      }

      if (path === "/v1/tasks" && request.method === "GET") {
        const access = await requireWorkspaceAccess(request, env);
        return json({ tasks: await listWorkspaceTasks(env, access.workspace) }, 200, request, env);
      }

      if (path === "/v1/tasks" && request.method === "POST") {
        const access = await requireWorkspaceAccess(request, env);
        return json({ task: await upsertWorkspaceTask(env, access.workspace, access.user, await parseJson(request)) }, 201, request, env);
      }

      if (path.match(/^\/v1\/tasks\/[^/]+$/) && request.method === "DELETE") {
        const access = await requireWorkspaceAccess(request, env);
        return json({ task: await removeWorkspaceTask(env, access.workspace, access.user, path.split("/")[3]) }, 200, request, env);
      }

      if (path === "/v1/task-events" && request.method === "POST") {
        const access = await requireWorkspaceAccess(request, env);
        await appendTaskActivity(env, access.workspace.id, access.user.username, await parseJson(request));
        return json({ ok: true }, 200, request, env);
      }

      return json({ error: `Unknown route: ${request.method} ${path}` }, 404, request, env);
    } catch (error) {
      return errorResponse(error, request, env);
    }
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(cleanupExpiredSystemFiles(env));
  },
};
