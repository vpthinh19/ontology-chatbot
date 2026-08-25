import assert from "node:assert/strict";
import { createServer } from "node:http";
import { afterEach, test } from "node:test";

import { proxyToBackend } from "../api/_proxy.js";
import viteConfig from "../vite.config.js";

const originalEnvironment = {
  serviceUrl: process.env.CLOUD_RUN_SERVICE_URL,
  backendToken: process.env.BACKEND_API_TOKEN,
};

afterEach(() => {
  if (originalEnvironment.serviceUrl === undefined) delete process.env.CLOUD_RUN_SERVICE_URL;
  else process.env.CLOUD_RUN_SERVICE_URL = originalEnvironment.serviceUrl;
  if (originalEnvironment.backendToken === undefined) delete process.env.BACKEND_API_TOKEN;
  else process.env.BACKEND_API_TOKEN = originalEnvironment.backendToken;
});

const listen = (handler) =>
  new Promise((resolve, reject) => {
    const server = createServer(handler);
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({
        baseUrl: `http://127.0.0.1:${port}`,
        close: () => new Promise((done) => server.close(done)),
      });
    });
  });

const readBody = (request) =>
  new Promise((resolve, reject) => {
    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => resolve(body));
    request.on("error", reject);
  });

test("health proxy replaces browser authorization with the server-side token", async () => {
  let seenAuthorization;
  const upstream = await listen((request, response) => {
    seenAuthorization = request.headers.authorization;
    response.writeHead(503, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
      "X-Upstream-Private": "must-not-leak",
    });
    response.end('{"status":"waking"}');
  });
  process.env.CLOUD_RUN_SERVICE_URL = `${upstream.baseUrl}/`;
  process.env.BACKEND_API_TOKEN = "server-secret";

  try {
    const response = await proxyToBackend(
      new Request("https://frontend.example/api/healthz", {
        headers: { Authorization: "Bearer browser-value" },
      }),
      { method: "GET", path: "/health" },
    );

    assert.equal(seenAuthorization, "Bearer server-secret");
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("content-type"), "application/json");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-accel-buffering"), "no");
    assert.equal(response.headers.has("x-upstream-private"), false);
    assert.equal(await response.text(), '{"status":"waking"}');
  } finally {
    await upstream.close();
  }
});

test("chat proxy forwards JSON and exposes the first SSE chunk before upstream completion", async () => {
  let seenAuthorization;
  let seenBody;
  let finishStream;
  const mayFinish = new Promise((resolve) => {
    finishStream = resolve;
  });
  const upstream = await listen(async (request, response) => {
    seenAuthorization = request.headers.authorization;
    seenBody = await readBody(request);
    response.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    });
    response.write('data: {"loai":"chu","noi_dung":"Xin"}\n\n');
    await mayFinish;
    response.end('data: {"loai":"xong","noi_dung":"Xin chào"}\n\n');
  });
  process.env.CLOUD_RUN_SERVICE_URL = upstream.baseUrl;
  process.env.BACKEND_API_TOKEN = "server-secret";

  try {
    const response = await proxyToBackend(
      new Request("https://frontend.example/api/chat", {
        method: "POST",
        headers: {
          Authorization: "Bearer browser-value",
          "Content-Type": "application/json",
        },
        body: '{"message":"Xin chào","history":[]}',
      }),
      { method: "POST", path: "/chat" },
    );
    const reader = response.body.getReader();
    const first = await reader.read();

    assert.equal(seenAuthorization, "Bearer server-secret");
    assert.equal(seenBody, '{"message":"Xin chào","history":[]}');
    assert.equal(new TextDecoder().decode(first.value), 'data: {"loai":"chu","noi_dung":"Xin"}\n\n');
    assert.equal(first.done, false);

    finishStream();
    const second = await reader.read();
    assert.equal(
      new TextDecoder().decode(second.value),
      'data: {"loai":"xong","noi_dung":"Xin chào"}\n\n',
    );
  } finally {
    finishStream();
    await upstream.close();
  }
});

test("proxy rejects unsupported methods before contacting the backend", async () => {
  process.env.CLOUD_RUN_SERVICE_URL = "http://127.0.0.1:1";
  process.env.BACKEND_API_TOKEN = "server-secret";

  const response = await proxyToBackend(
    new Request("https://frontend.example/api/healthz", { method: "POST" }),
    { method: "GET", path: "/health" },
  );

  assert.equal(response.status, 405);
  assert.equal(response.headers.get("allow"), "GET");
  assert.deepEqual(await response.json(), { detail: "Method not allowed." });
});

test("proxy reports incomplete server configuration without exposing partial values", async () => {
  process.env.CLOUD_RUN_SERVICE_URL = "https://backend.example";
  delete process.env.BACKEND_API_TOKEN;

  const response = await proxyToBackend(
    new Request("https://frontend.example/api/healthz"),
    { method: "GET", path: "/health" },
  );
  const text = await response.text();

  assert.equal(response.status, 500);
  assert.deepEqual(JSON.parse(text), { detail: "Proxy is not configured." });
});

test("proxy turns an upstream connection failure into a bounded 502", async () => {
  const unavailable = await listen((_request, response) => response.end());
  process.env.CLOUD_RUN_SERVICE_URL = unavailable.baseUrl;
  process.env.BACKEND_API_TOKEN = "server-secret";
  await unavailable.close();

  const response = await proxyToBackend(
    new Request("https://frontend.example/api/healthz"),
    { method: "GET", path: "/health" },
  );

  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { detail: "Could not reach the backend." });
});

test("Vite development rewrites same-origin API paths to the local backend", () => {
  process.env.BACKEND_API_TOKEN = "server-secret";
  const config = viteConfig({ command: "serve", mode: "development" });
  const proxy = config.server.proxy["/api"];

  assert.equal(proxy.target, "http://127.0.0.1:8000");
  assert.equal(proxy.headers.Authorization, "Bearer server-secret");
  assert.equal(proxy.rewrite("/api/healthz"), "/health");
  assert.equal(proxy.rewrite("/api/chat"), "/chat");
});
