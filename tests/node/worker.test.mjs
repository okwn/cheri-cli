import assert from "node:assert/strict";

import worker from "../../worker/index.js";

class FakeKV {
  constructor() {
    this.store = new Map();
  }

  async get(key) {
    return this.store.get(key) ?? null;
  }

  async put(key, value) {
    this.store.set(key, value);
  }

  async delete(key) {
    this.store.delete(key);
  }

  async list(options = {}) {
    const prefix = options.prefix || "";
    const keys = [...this.store.keys()]
      .filter((key) => key.startsWith(prefix))
      .sort()
      .map((name) => ({ name }));
    return {
      keys,
      list_complete: true,
      cursor: "",
    };
  }
}

class FakeR2Bucket {
  constructor() {
    this.objects = new Map();
  }

  async put(key, body, options = {}) {
    const payload = Buffer.from(await new Response(body).arrayBuffer());
    this.objects.set(key, {
      key,
      body: payload,
      size: payload.length,
      httpMetadata: options.httpMetadata || {},
      customMetadata: options.customMetadata || {},
      etag: `etag-${crypto.randomUUID()}`,
      uploaded: new Date(),
    });
  }

  async get(key) {
    const object = this.objects.get(key);
    if (!object) {
      return null;
    }
    return {
      body: object.body,
      size: object.size,
      httpMetadata: object.httpMetadata,
      etag: object.etag,
      uploaded: object.uploaded,
    };
  }

  async head(key) {
    const object = this.objects.get(key);
    if (!object) {
      return null;
    }
    return {
      size: object.size,
      httpMetadata: object.httpMetadata,
      etag: object.etag,
      uploaded: object.uploaded,
    };
  }

  async delete(key) {
    this.objects.delete(key);
  }

  async list(options = {}) {
    const prefix = options.prefix || "";
    return {
      objects: [...this.objects.values()]
        .filter((object) => object.key.startsWith(prefix))
        .map((object) => ({
          key: object.key,
          size: object.size,
          uploaded: object.uploaded,
          etag: object.etag,
        })),
    };
  }
}

function makeEnv(overrides = {}) {
  return {
    HERMES_KV: new FakeKV(),
    HERMES_BUCKET: new FakeR2Bucket(),
    CHERI_CORS_ORIGINS: "",
    CHERI_EXPERIMENTAL_PROVIDERS: "",
    ...overrides,
  };
}

async function request(env, path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  if (options.workspaceId) {
    headers.set("X-Workspace-ID", options.workspaceId);
  }
  if (options.origin) {
    headers.set("Origin", options.origin);
  }
  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }
  return worker.fetch(
    new Request(`https://cheri.test${path}`, {
      method: options.method || "GET",
      headers,
      body,
    }),
    env,
    { waitUntil() {} },
  );
}

async function jsonResponse(env, path, options = {}) {
  const response = await request(env, path, options);
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : null;
  return { response, payload };
}

function systemProviderSelection() {
  return {
    kind: "system",
    warning_acknowledged: true,
    settings: {},
  };
}

async function runCase(name, fn) {
  await fn();
  console.log(`ok - ${name}`);
}

await runCase("provider catalog exposes system as ready and other providers as coming soon", async () => {
  const env = makeEnv();
  const { response, payload } = await jsonResponse(env, "/v1/providers");

  assert.equal(response.status, 200);
  assert.equal(payload.providers.find((provider) => provider.kind === "system").selectable, true);
  assert.equal(payload.providers.find((provider) => provider.kind === "system").coming_soon, false);
  assert.equal(payload.providers.find((provider) => provider.kind === "s3-compatible").selectable, false);
  assert.equal(payload.providers.find((provider) => provider.kind === "s3-compatible").coming_soon, true);
});

await runCase("provider catalog can expose experimental selectability when explicitly enabled", async () => {
  const env = makeEnv({ CHERI_EXPERIMENTAL_PROVIDERS: "1" });
  const { payload } = await jsonResponse(env, "/v1/providers?include_experimental=1");

  assert.equal(payload.providers.find((provider) => provider.kind === "google-drive").selectable, true);
  assert.equal(payload.providers.find((provider) => provider.kind === "backblaze-b2").experimental, true);
});

await runCase("register, login, logout, workspace selection, and invite join flows work end to end", async () => {
  const env = makeEnv();

  const registerAlice = await jsonResponse(env, "/v1/auth/register", {
    method: "POST",
    json: {
      username: "alice",
      workspace_name: "alice workspace",
      provider: systemProviderSelection(),
    },
  });
  assert.equal(registerAlice.response.status, 201);
  assert.equal(registerAlice.payload.identity.username, "alice");
  assert.equal(registerAlice.payload.bootstrap.secret.split(" ").length, 12);
  const aliceToken = registerAlice.payload.session.token;

  const createDocs = await jsonResponse(env, "/v1/workspaces/select", {
    method: "POST",
    token: aliceToken,
    json: {
      identifier: "docs",
      create_if_missing: true,
      provider: systemProviderSelection(),
    },
  });
  assert.equal(createDocs.response.status, 200);
  assert.equal(createDocs.payload.workspace_access.workspaces.length, 2);
  const docsWorkspace = createDocs.payload.workspace_access.workspaces.find((workspace) => workspace.name === "docs");
  assert.ok(docsWorkspace);

  const inviteCreated = await jsonResponse(env, "/v1/teams/invites", {
    method: "POST",
    token: aliceToken,
    workspaceId: docsWorkspace.id,
    json: { label: "contractor" },
  });
  assert.equal(inviteCreated.response.status, 201);
  assert.match(inviteCreated.payload.invite.code, /^CHR-TEAM-[A-Z2-9]{8}$/);

  const registerBob = await jsonResponse(env, "/v1/auth/register", {
    method: "POST",
    json: {
      username: "bob",
      workspace_name: "bob workspace",
      provider: systemProviderSelection(),
    },
  });
  const bobToken = registerBob.payload.session.token;

  const acceptInvite = await jsonResponse(env, "/v1/teams/invites/accept", {
    method: "POST",
    token: bobToken,
    json: { invite_code: inviteCreated.payload.invite.code },
  });
  assert.equal(acceptInvite.response.status, 200);
  assert.equal(acceptInvite.payload.workspace_access.active_workspace_id, docsWorkspace.id);

  const teamSnapshot = await jsonResponse(env, "/v1/teams", {
    token: aliceToken,
    workspaceId: docsWorkspace.id,
  });
  assert.equal(teamSnapshot.response.status, 200);
  assert.ok(teamSnapshot.payload.members.some((member) => member.username === "bob"));

  const logout = await jsonResponse(env, "/v1/auth/logout", {
    method: "POST",
    token: bobToken,
  });
  assert.equal(logout.response.status, 200);

  const sessionAfterLogout = await jsonResponse(env, "/v1/session", {
    token: bobToken,
  });
  assert.equal(sessionAfterLogout.response.status, 401);

  const loginAlice = await jsonResponse(env, "/v1/auth/login", {
    method: "POST",
    json: {
      username: "alice",
      bootstrap_secret: registerAlice.payload.bootstrap.secret,
    },
  });
  assert.equal(loginAlice.response.status, 200);
  assert.equal(loginAlice.payload.identity.username, "alice");
});

await runCase("file upload, list, download, and activity flows work through the system provider", async () => {
  const env = makeEnv();
  const register = await jsonResponse(env, "/v1/auth/register", {
    method: "POST",
    json: {
      username: "carol",
      workspace_name: "carol workspace",
      provider: systemProviderSelection(),
    },
  });
  const token = register.payload.session.token;
  const workspaceId = register.payload.workspace_access.active_workspace_id;

  const uploadGrant = await jsonResponse(env, "/v1/files/upload-grant", {
    method: "POST",
    token,
    workspaceId,
    json: {
      filename: "notes/hello.txt",
      size: 11,
      mime_type: "text/plain",
      checksum: "abc123",
      local_modified_at: new Date().toISOString(),
    },
  });
  assert.equal(uploadGrant.response.status, 201);

  const uploadResponse = await request(env, new URL(uploadGrant.payload.upload_url).pathname, {
    method: "PUT",
    body: Buffer.from("hello world", "utf-8"),
  });
  assert.equal(uploadResponse.status, 200);

  const complete = await jsonResponse(env, `/v1/files/${uploadGrant.payload.file_id}/complete`, {
    method: "POST",
    token,
    workspaceId,
    json: {},
  });
  assert.equal(complete.response.status, 200);
  assert.equal(complete.payload.file.logical_name, "notes/hello.txt");

  const fileList = await jsonResponse(env, "/v1/files", {
    token,
    workspaceId,
  });
  assert.equal(fileList.response.status, 200);
  assert.equal(fileList.payload.files.length, 1);

  const downloadGrant = await jsonResponse(env, `/v1/files/${uploadGrant.payload.file_id}/download-grant`, {
    token,
    workspaceId,
  });
  assert.equal(downloadGrant.response.status, 200);

  const downloaded = await request(env, new URL(downloadGrant.payload.download_url).pathname);
  assert.equal(downloaded.status, 200);
  assert.equal(await downloaded.text(), "hello world");

  const activity = await jsonResponse(env, "/v1/activity", {
    token,
    workspaceId,
  });
  assert.equal(activity.response.status, 200);
  assert.ok(activity.payload.recent_actions.some((entry) => entry.action === "file_uploaded"));
  assert.ok(activity.payload.recent_actions.some((entry) => entry.action === "file_downloaded"));
});

await runCase("task registry routes and security checks behave correctly", async () => {
  const env = makeEnv();
  const register = await jsonResponse(env, "/v1/auth/register", {
    method: "POST",
    json: {
      username: "dora",
      workspace_name: "ops",
      provider: systemProviderSelection(),
    },
  });
  const token = register.payload.session.token;
  const workspaceId = register.payload.workspace_access.active_workspace_id;

  const created = await jsonResponse(env, "/v1/tasks", {
    method: "POST",
    token,
    workspaceId,
    json: {
      id: "task_alpha",
      target_type: "directory",
      target_label: "src",
      sync_mode: "on-change",
      debounce_seconds: 3,
      recursive: true,
      direction: "upload-only",
    },
  });
  assert.equal(created.response.status, 201);
  assert.equal(created.payload.task.id, "task_alpha");

  const listed = await jsonResponse(env, "/v1/tasks", {
    token,
    workspaceId,
  });
  assert.equal(listed.response.status, 200);
  assert.equal(listed.payload.tasks.length, 1);

  const deleted = await jsonResponse(env, "/v1/tasks/task_alpha", {
    method: "DELETE",
    token,
    workspaceId,
  });
  assert.equal(deleted.response.status, 200);

  const unauthorizedFiles = await jsonResponse(env, "/v1/files");
  assert.equal(unauthorizedFiles.response.status, 401);

  const badTaskDirection = await jsonResponse(env, "/v1/tasks", {
    method: "POST",
    token,
    workspaceId,
    json: {
      id: "task_bad",
      target_type: "file",
      target_label: "notes.txt",
      sync_mode: "instant",
      direction: "bidirectional",
    },
  });
  assert.equal(badTaskDirection.response.status, 400);
});

await runCase("worker only returns CORS headers for explicitly allowed origins", async () => {
  const env = makeEnv({ CHERI_CORS_ORIGINS: "https://allowed.example" });
  const withoutOrigin = await request(env, "/healthz");
  assert.equal(withoutOrigin.headers.get("access-control-allow-origin"), null);

  const withAllowedOrigin = await request(env, "/healthz", {
    origin: "https://allowed.example",
  });
  assert.equal(withAllowedOrigin.headers.get("access-control-allow-origin"), "https://allowed.example");
});
