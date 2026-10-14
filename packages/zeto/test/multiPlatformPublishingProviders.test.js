const assert = require("node:assert/strict");
const test = require("node:test");

const {
  InstagramPublishingProvider,
} = require("../src/providers/instagramPublishingProvider");
const {
  YouTubePublishingProvider,
} = require("../src/providers/youtubePublishingProvider");
const {
  TikTokPublishingProvider,
} = require("../src/providers/tiktokPublishingProvider");
const { XPublishingProvider } = require("../src/providers/xPublishingProvider");
const {
  LinkedInPublishingProvider,
} = require("../src/providers/linkedinPublishingProvider");
const { ProviderRegistry } = require("../src/providers/providerRegistry");

test("Instagram publishes an image container and then publishes it", async () => {
  const calls = [];
  const provider = new InstagramPublishingProvider({
    apiVersion: "v99.0",
    http: async (request) => {
      calls.push(request);
      return {
        data: { id: calls.length === 1 ? "container-1" : "media-1" },
        headers: {},
      };
    },
  });
  const result = await provider.publish(
    { accountId: "ig-1", accessToken: "secret" },
    {
      kind: "image",
      text: "caption",
      mediaUrl: "https://cdn.example/image.jpg",
    },
  );
  assert.equal(calls[0].url, "https://graph.facebook.com/v99.0/ig-1/media");
  assert.equal(calls[0].data.image_url, "https://cdn.example/image.jpg");
  assert.equal(calls[1].data.creation_id, "container-1");
  assert.equal(result.providerPublicationId, "media-1");
});

test("YouTube uses a resumable upload session and does not put tokens in URLs", async () => {
  const calls = [];
  const provider = new YouTubePublishingProvider({
    http: async (request) => {
      calls.push(request);
      if (calls.length === 1)
        return { data: { items: [{ id: "channel-1" }] }, headers: {} };
      if (calls.length === 2)
        return {
          data: {},
          headers: { location: "https://upload.example/session" },
        };
      return { data: { id: "video-1" }, headers: {} };
    },
  });
  const credentials = { accessToken: "secret" };
  const auth = await provider.validateAuth(credentials);
  const result = await provider.publish(credentials, {
    kind: "video",
    text: "description",
    title: "Title",
    madeForKids: false,
    containsSyntheticMedia: false,
    media: { buffer: Buffer.from("video"), mimeType: "video/mp4", size: 5 },
  });
  assert.equal(auth.account.id, "channel-1");
  assert.equal(calls[1].params.uploadType, "resumable");
  assert.equal(calls[2].method, "PUT");
  assert.equal(
    calls.every((call) => !call.url.includes("secret")),
    true,
  );
  assert.equal(result.permalink, "https://www.youtube.com/watch?v=video-1");
});

test("TikTok validates creator choices before direct-post initialization", async () => {
  const calls = [];
  const provider = new TikTokPublishingProvider({
    http: async (request) => {
      calls.push(request);
      if (calls.length === 1)
        return {
          data: { data: { privacy_level_options: ["SELF_ONLY"] } },
          headers: {},
        };
      return { data: { data: { publish_id: "publish-1" } }, headers: {} };
    },
  });
  await assert.rejects(
    () =>
      provider.publish(
        { accessToken: "secret" },
        {
          kind: "video",
          mediaUrl: "https://cdn.example/video.mp4",
          privacyLevel: "PUBLIC_TO_EVERYONE",
          userConsent: true,
        },
      ),
    /privacy level/i,
  );
  calls.length = 0;
  const result = await provider.publish(
    { accessToken: "secret" },
    {
      kind: "video",
      text: "caption",
      mediaUrl: "https://cdn.example/video.mp4",
      privacyLevel: "SELF_ONLY",
      userConsent: true,
    },
  );
  assert.equal(calls[1].data.source_info.source, "PULL_FROM_URL");
  assert.equal(result.providerPublicationId, "publish-1");
});

test("X publishes text and parses rate-limit metadata", async () => {
  const calls = [];
  const provider = new XPublishingProvider({
    http: async (request) => {
      calls.push(request);
      return {
        data: { data: { id: "tweet-1", text: "hello" } },
        headers: { "x-rate-limit-remaining": "9", "x-rate-limit-reset": "123" },
      };
    },
  });
  const result = await provider.publish(
    { accessToken: "secret", username: "zato" },
    { kind: "text", text: "hello" },
  );
  assert.deepEqual(calls[0].data, { text: "hello" });
  assert.deepEqual(result.rateLimit, { remaining: 9, resetAt: 123 });
  assert.equal(result.permalink, "https://x.com/zato/status/tweet-1");
});

test("LinkedIn initializes and uploads an image before creating a post", async () => {
  const calls = [];
  const provider = new LinkedInPublishingProvider({
    linkedinVersion: "202606",
    http: async (request) => {
      calls.push(request);
      if (calls.length === 1)
        return {
          data: {
            value: {
              uploadUrl: "https://upload.example/image",
              image: "urn:li:image:1",
            },
          },
          headers: {},
        };
      if (calls.length === 2) return { data: {}, headers: {} };
      return { data: {}, headers: { "x-restli-id": "urn:li:share:1" } };
    },
  });
  const result = await provider.publish(
    { accessToken: "secret", authorUrn: "urn:li:person:1" },
    {
      kind: "image",
      text: "caption",
      media: { buffer: Buffer.from("image"), mimeType: "image/jpeg" },
    },
  );
  assert.match(calls[0].url, /images\?action=initializeUpload/);
  assert.equal(calls[1].url, "https://upload.example/image");
  assert.equal(calls[2].data.content.media.id, "urn:li:image:1");
  assert.equal(result.providerPublicationId, "urn:li:share:1");
});

test("registry rejects unknown providers, duplicates, and unsupported publications", () => {
  const provider = {
    capabilities: () => ({ text: true, image: false, video: false }),
  };
  const registry = new ProviderRegistry({ example: provider });
  assert.equal(registry.get("EXAMPLE"), provider);
  assert.throws(() => registry.get("missing"), /Unknown publishing provider/);
  assert.throws(
    () => registry.register("example", provider),
    /already registered/,
  );
  assert.throws(
    () => registry.validatePublication("example", { kind: "image" }),
    /does not support image/,
  );
});
