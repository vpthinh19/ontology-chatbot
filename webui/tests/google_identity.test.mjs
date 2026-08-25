import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { createGoogleIdTokenProvider } from "../api/_google_identity.js";

const CONFIGURATION_NAMES = [
  "CLOUD_RUN_SERVICE_URL",
  "GCP_PROJECT_NUMBER",
  "GCP_SERVICE_ACCOUNT_EMAIL",
  "GCP_WORKLOAD_IDENTITY_POOL_ID",
  "GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID",
  "VERCEL_OIDC_TOKEN",
];
const originalEnvironment = Object.fromEntries(
  CONFIGURATION_NAMES.map((name) => [name, process.env[name]]),
);

afterEach(() => {
  for (const name of CONFIGURATION_NAMES) {
    const original = originalEnvironment[name];
    if (original === undefined) delete process.env[name];
    else process.env[name] = original;
  }
});

const configure = () => {
  process.env.CLOUD_RUN_SERVICE_URL = "https://chatbot-abc.asia-southeast1.run.app";
  process.env.GCP_PROJECT_NUMBER = "123456789";
  process.env.GCP_SERVICE_ACCOUNT_EMAIL =
    "vercel-cloud-run@ontology-project.iam.gserviceaccount.com";
  process.env.GCP_WORKLOAD_IDENTITY_POOL_ID = "vercel";
  process.env.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID = "vercel-production";
};

const vercelRequest = () =>
  new Request("https://frontend.example/api/healthz", {
    headers: { "x-vercel-oidc-token": "vercel-assertion" },
  });

const successfulGoogleFetch = (calls) => async (url, options) => {
  calls.push({ url: String(url), options });
  if (String(url) === "https://sts.googleapis.com/v1/token") {
    return Response.json({
      access_token: "federated-access-token",
      expires_in: 3600,
      issued_token_type: "urn:ietf:params:oauth:token-type:access_token",
      token_type: "Bearer",
    });
  }
  return Response.json({ token: "google-id-token" });
};

test("exchanges Vercel OIDC for one cached Cloud Run ID token", async () => {
  configure();
  const calls = [];
  const provider = createGoogleIdTokenProvider({
    fetchImpl: successfulGoogleFetch(calls),
    now: () => 1_000,
  });

  assert.equal(await provider(vercelRequest()), "google-id-token");
  assert.equal(await provider(vercelRequest()), "google-id-token");
  assert.equal(calls.length, 2);

  const sts = calls[0];
  assert.equal(sts.url, "https://sts.googleapis.com/v1/token");
  assert.equal(sts.options.method, "POST");
  assert.equal(sts.options.headers["Content-Type"], "application/x-www-form-urlencoded");
  assert.deepEqual(Object.fromEntries(new URLSearchParams(sts.options.body)), {
    audience:
      "//iam.googleapis.com/projects/123456789/locations/global/" +
      "workloadIdentityPools/vercel/providers/vercel-production",
    grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
    requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
    scope: "https://www.googleapis.com/auth/cloud-platform",
    subject_token: "vercel-assertion",
    subject_token_type: "urn:ietf:params:oauth:token-type:jwt",
  });

  const iam = calls[1];
  assert.equal(
    iam.url,
    "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/" +
      "vercel-cloud-run%40ontology-project.iam.gserviceaccount.com:generateIdToken",
  );
  assert.equal(iam.options.headers.Authorization, "Bearer federated-access-token");
  assert.deepEqual(JSON.parse(iam.options.body), {
    audience: "https://chatbot-abc.asia-southeast1.run.app",
    includeEmail: true,
  });
});

test("concurrent cold requests share one Google token exchange", async () => {
  configure();
  const calls = [];
  let releaseSts;
  const stsMayFinish = new Promise((resolve) => {
    releaseSts = resolve;
  });
  const baseFetch = successfulGoogleFetch(calls);
  const provider = createGoogleIdTokenProvider({
    fetchImpl: async (url, options) => {
      if (String(url).includes("sts.googleapis.com")) await stsMayFinish;
      return baseFetch(url, options);
    },
    now: () => 1_000,
  });

  const pending = Array.from({ length: 20 }, () => provider(vercelRequest()));
  releaseSts();

  assert.deepEqual(await Promise.all(pending), Array(20).fill("google-id-token"));
  assert.equal(calls.length, 2);
});

test("a failed Google exchange is not cached", async () => {
  configure();
  let calls = 0;
  const provider = createGoogleIdTokenProvider({
    fetchImpl: async (url) => {
      calls += 1;
      if (calls === 1) return new Response("temporary failure", { status: 503 });
      if (String(url).includes("sts.googleapis.com")) {
        return Response.json({ access_token: "recovered-access-token" });
      }
      return Response.json({ token: "recovered-id-token" });
    },
    now: () => 1_000,
  });

  await assert.rejects(provider(vercelRequest()), /authenticate the backend/);
  assert.equal(await provider(vercelRequest()), "recovered-id-token");
  assert.equal(calls, 3);
});

test("a missing Vercel assertion fails before contacting Google", async () => {
  configure();
  delete process.env.VERCEL_OIDC_TOKEN;
  let calls = 0;
  const provider = createGoogleIdTokenProvider({
    fetchImpl: async () => {
      calls += 1;
      return Response.json({});
    },
  });

  await assert.rejects(
    provider(new Request("https://frontend.example/api/healthz")),
    /identity is unavailable/,
  );
  assert.equal(calls, 0);
});
