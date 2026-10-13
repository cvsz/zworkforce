const assert = require("node:assert/strict");
const test = require("node:test");
const { YouTubePublishingProvider } = require("../src/providers/youtubePublishingProvider");

const media = { buffer: Buffer.from("test"), mimeType: "video/mp4", size: 4 };

test("YouTube rejects non-private upload before any network call", async () => {
  let calls = 0;
  const provider = new YouTubePublishingProvider({ http: async () => { calls++; } });
  await assert.rejects(
    provider.publish({ accessToken: "secret" }, {
      title: "Unsafe", media, privacyStatus: "public",
    }),
    /must start private/,
  );
  assert.equal(calls, 0);
});

test("YouTube private upload is enforced on outgoing metadata", async () => {
  const requests = [];
  const provider = new YouTubePublishingProvider({
    http: async (request) => {
      requests.push(request);
      return requests.length === 1
        ? { data: {}, headers: { location: "https://upload.example/session" } }
        : { data: { id: "video-1" }, headers: {} };
    },
  });
  await provider.publish({ accessToken: "secret" }, { title: "LALIN", media });
  assert.equal(requests[0].data.status.privacyStatus, "private");
});

test("visibility change fails closed without canonical verifier", async () => {
  let called = false;
  const provider = new YouTubePublishingProvider({
    http: async () => { called = true; },
  });
  await assert.rejects(provider.setVisibility({ accessToken: "secret" }, "video-1", {
    approved: true, videoId: "video-1", approverId: "user-1",
    auditId: "audit-1", privacyStatus: "public",
  }), /verification failed/);
  assert.equal(called, false);
});

test("canonical verifier controls approved visibility transition", async () => {
  const requests = [];
  const provider = new YouTubePublishingProvider({
    verifyPublicationApproval: async (approval) => approval.auditId === "accepted",
    http: async (request) => {
      requests.push(request);
      return { data: { id: "video-1" }, headers: {} };
    },
  });
  const base = {
    approved: true, videoId: "video-1", approverId: "human-1",
    privacyStatus: "public",
  };
  await assert.rejects(
    provider.setVisibility({ accessToken: "secret" }, "video-1", {
      ...base, auditId: "rejected",
    }), /verification failed/,
  );
  assert.equal(requests.length, 0);
  await provider.setVisibility({ accessToken: "secret" }, "video-1", {
    ...base, auditId: "accepted",
  });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].data.status.privacyStatus, "public");
});
