const assert = require("node:assert/strict");
const test = require("node:test");

const token = process.env.YOUTUBE_OAUTH_TEST_ACCESS_TOKEN?.trim() || "";
const required = process.env.ZETO_REQUIRE_YOUTUBE_SCOPE_TEST === "1";
const scopeTest = token || required ? test : test.skip;

scopeTest(
  "configured YouTube OAuth token grants videos.update scope",
  async () => {
    assert.ok(
      token,
      "YOUTUBE_OAUTH_TEST_ACCESS_TOKEN is required for this verification",
    );
    assert.ok(
      token.length <= 16 * 1024,
      "YouTube OAuth test token exceeds the supported size",
    );

    let response;
    try {
      response = await fetch("https://oauth2.googleapis.com/tokeninfo", {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ access_token: token }),
        signal: AbortSignal.timeout(10_000),
      });
    } catch {
      throw new Error("Google token scope verification request failed");
    }

    assert.equal(
      response.ok,
      true,
      `Google tokeninfo returned HTTP ${response.status}`,
    );

    let tokenInfo;
    try {
      tokenInfo = await response.json();
    } catch {
      throw new Error("Google tokeninfo returned an invalid response");
    }

    const grantedScopes = new Set(
      String(tokenInfo.scope || "")
        .split(/\s+/)
        .filter(Boolean),
    );
    const visibilityScopes = [
      "https://www.googleapis.com/auth/youtubepartner",
      "https://www.googleapis.com/auth/youtube",
      "https://www.googleapis.com/auth/youtube.force-ssl",
    ];
    assert.equal(
      visibilityScopes.some((scope) => grantedScopes.has(scope)),
      true,
      "YouTube access token must grant a scope accepted by videos.update; scope values are not logged",
    );
  },
);
