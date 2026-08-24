import assert from "node:assert/strict";
import { createServer } from "node:http";
import { afterEach, test } from "node:test";

import { POST as proxyChat } from "../api/chat.js";
import { GET as proxyHealth } from "../api/healthz.js";
import { proxyToLightning } from "../api/_proxy.js";
import viteConfig from "../vite.config.js";

const originalEnvironment = {
  baseUrl: process.env.LIGHTNING_API_BASE_URL,
  token: process.env.LIGHTNING_API_TOKEN,
};

afterEach(() => {
  if (originalEnvironment.baseUrl === undefined) delete process.env.LIGHTNING_API_BASE_URL;
  else process.env.LIGHTNING_API_BASE_URL = originalEnvironment.baseUrl;
  if (originalEnvironment.token === undefined) delete process.env.LIGHTNING_API_TOKEN;
  else process.env.LIGHTNING_API_TOKEN = originalEnvironment.token;
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

test("health proxy replaces client authorization and preserves the upstream response", async () => {
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
  process.env.LIGHTNING_API_BASE_URL = `${upstream.baseUrl}/`;
  process.env.LIGHTNING_API_TOKEN = "server-secret";

  try {
    const response = await proxyHealth(
      new Request("https://frontend.example/api/healthz", {
        headers: { Authorization: "Bearer browser-value" },
      }),
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
  process.env.LIGHTNING_API_BASE_URL = upstream.baseUrl;
  process.env.LIGHTNING_API_TOKEN = "server-secret";

  try {
    const response = await proxyChat(
      new Request("https://frontend.example/api/chat", {
        method: "POST",
        headers: {
          Authorization: "Bearer browser-value",
          "Content-Type": "application/json",
        },
        body: '{"message":"Xin chào","history":[]}',
      }),
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

test("proxy rejects unsupported methods without contacting Lightning", async () => {
  process.env.LIGHTNING_API_BASE_URL = "http://127.0.0.1:1";
  process.env.LIGHTNING_API_TOKEN = "server-secret";

  const response = await proxyToLightning(
    new Request("https://frontend.example/api/healthz", { method: "POST" }),
    { method: "GET", path: "/healthz" },
  );

  assert.equal(response.status, 405);
  assert.equal(response.headers.get("allow"), "GET");
  assert.deepEqual(await response.json(), { detail: "Method not allowed." });
});

test("proxy reports missing server configuration without exposing partial values", async () => {
  process.env.LIGHTNING_API_BASE_URL = "https://secret-host.example";
  delete process.env.LIGHTNING_API_TOKEN;

  const response = await proxyHealth(new Request("https://frontend.example/api/healthz"));
  const text = await response.text();

  assert.equal(response.status, 500);
  assert.equal(text.includes("secret-host"), false);
  assert.deepEqual(JSON.parse(text), { detail: "Proxy is not configured." });
});

test("proxy turns an upstream connection failure into a bounded 502", async () => {
  const unavailable = await listen((_request, response) => response.end());
  process.env.LIGHTNING_API_BASE_URL = unavailable.baseUrl;
  process.env.LIGHTNING_API_TOKEN = "server-secret";
  await unavailable.close();

  const response = await proxyHealth(new Request("https://frontend.example/api/healthz"));

  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { detail: "Could not reach the backend." });
});

test("Vite development rewrites same-origin API paths to the local backend", () => {
  const config = viteConfig({ command: "serve", mode: "development" });
  const proxy = config.server.proxy["/api"];

  assert.equal(proxy.target, "http://127.0.0.1:8000");
  assert.equal(proxy.rewrite("/api/healthz"), "/healthz");
  assert.equal(proxy.rewrite("/api/chat"), "/chat");
});
