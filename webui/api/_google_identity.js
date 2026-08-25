const STS_URL = "https://sts.googleapis.com/v1/token";
const IAM_CREDENTIALS_URL = "https://iamcredentials.googleapis.com/v1";
const TOKEN_CACHE_MS = 50 * 60 * 1_000;

const requiredEnvironment = (name) => {
  const value = (process.env[name] || "").trim();
  if (!value) throw new Error("Proxy identity is not configured.");
  return value;
};

const readConfiguration = () => ({
  serviceUrl: requiredEnvironment("CLOUD_RUN_SERVICE_URL").replace(/\/+$/, ""),
  projectNumber: requiredEnvironment("GCP_PROJECT_NUMBER"),
  serviceAccountEmail: requiredEnvironment("GCP_SERVICE_ACCOUNT_EMAIL"),
  poolId: requiredEnvironment("GCP_WORKLOAD_IDENTITY_POOL_ID"),
  providerId: requiredEnvironment("GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID"),
});

const responseToken = async (response, field) => {
  if (!response.ok) throw new Error("Could not authenticate the backend.");
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("Could not authenticate the backend.");
  }
  if (typeof payload[field] !== "string" || !payload[field]) {
    throw new Error("Could not authenticate the backend.");
  }
  return payload[field];
};

const mintGoogleIdToken = async (subjectToken, fetchImpl) => {
  const configuration = readConfiguration();
  const audience =
    `//iam.googleapis.com/projects/${configuration.projectNumber}/locations/global/` +
    `workloadIdentityPools/${configuration.poolId}/providers/${configuration.providerId}`;
  const stsBody = new URLSearchParams({
    audience,
    grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
    requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
    scope: "https://www.googleapis.com/auth/cloud-platform",
    subject_token: subjectToken,
    subject_token_type: "urn:ietf:params:oauth:token-type:jwt",
  });

  let accessToken;
  try {
    const stsResponse = await fetchImpl(STS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: stsBody,
    });
    accessToken = await responseToken(stsResponse, "access_token");
  } catch (error) {
    if (error.message === "Could not authenticate the backend.") throw error;
    throw new Error("Could not authenticate the backend.");
  }

  const serviceAccount = encodeURIComponent(configuration.serviceAccountEmail);
  const tokenUrl =
    `${IAM_CREDENTIALS_URL}/projects/-/serviceAccounts/${serviceAccount}` +
    ":generateIdToken";
  try {
    const tokenResponse = await fetchImpl(tokenUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        audience: configuration.serviceUrl,
        includeEmail: true,
      }),
    });
    return await responseToken(tokenResponse, "token");
  } catch (error) {
    if (error.message === "Could not authenticate the backend.") throw error;
    throw new Error("Could not authenticate the backend.");
  }
};

export const createGoogleIdTokenProvider = ({
  fetchImpl = globalThis.fetch,
  now = Date.now,
} = {}) => {
  let cachedToken;
  let cachedUntil = 0;
  let inFlight;

  return async (request) => {
    const subjectToken =
      request.headers.get("x-vercel-oidc-token") ||
      (process.env.VERCEL_OIDC_TOKEN || "").trim();
    if (!subjectToken) throw new Error("Vercel workload identity is unavailable.");
    if (cachedToken && now() < cachedUntil) return cachedToken;
    if (!inFlight) {
      inFlight = mintGoogleIdToken(subjectToken, fetchImpl)
        .then((token) => {
          cachedToken = token;
          cachedUntil = now() + TOKEN_CACHE_MS;
          return token;
        })
        .finally(() => {
          inFlight = undefined;
        });
    }
    return inFlight;
  };
};

export const getCloudRunIdentityToken = createGoogleIdTokenProvider();
