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
  const currentStatus = {
    privacyStatus: "private",
    license: "youtube",
    embeddable: true,
    selfDeclaredMadeForKids: false,
    publishAt: "2026-12-01T00:00:00Z",
    madeForKids: false,
  };
  const provider = new YouTubePublishingProvider({
    verifyPublicationApproval: async (approval) => approval.auditId === "accepted",
    finalizePublicationApproval: async () => {},
    http: async (request) => {
      requests.push(request);
      if (request.method === "GET") {
        return { data: { items: [{ id: "video-1", etag: "etag-1", status: { ...currentStatus } }] }, headers: {} };
      }
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
  // Confirmation GET still reports private, so the transition must fail closed.
  await assert.rejects(
    provider.setVisibility({ accessToken: "secret" }, "video-1", {
      ...base, auditId: "accepted",
    }), /did not confirm/,
  );
  const put = requests.find((request) => request.method === "PUT");
  assert.equal(put.data.status.privacyStatus, "public");
  assert.equal(put.data.status.license, "youtube");
  assert.equal(put.data.status.embeddable, true);
  assert.equal(put.data.status.selfDeclaredMadeForKids, false);
  assert.ok(!("publishAt" in put.data.status));
  assert.ok(!("madeForKids" in put.data.status));
  assert.equal(put.headers["If-Match"], "etag-1");
});

test("approved visibility is confirmed and finalized after mutation", async () => {
  const requests = [];
  let finalized = 0;
  const provider = new YouTubePublishingProvider({
    verifyPublicationApproval: async () => true,
    finalizePublicationApproval: async () => { finalized++; },
    http: async (request) => {
      requests.push(request);
      if (request.method === "GET") {
        const applied = requests.some((seen) => seen.method === "PUT");
        return {
          data: { items: [{ id: "video-1", status: { privacyStatus: applied ? "public" : "private" } }] },
          headers: {},
        };
      }
      return { data: { id: "video-1" }, headers: {} };
    },
  });
  const result = await provider.setVisibility({ accessToken: "secret" }, "video-1", {
    approved: true, videoId: "video-1", approverId: "human-1",
    auditId: "accepted", privacyStatus: "public",
  });
  assert.equal(result.publication.status.privacyStatus, "public");
  assert.equal(finalized, 1);
});

test("visibility change requires a finalizer so approvals cannot replay", async () => {
  const requests = [];
  const provider = new YouTubePublishingProvider({
    verifyPublicationApproval: async () => true,
    http: async (request) => {
      requests.push(request);
      if (request.method === "GET") {
        return {
          data: { items: [{ id: "video-1", status: { privacyStatus: "public" } }] },
          headers: {},
        };
      }
      return { data: { id: "video-1" }, headers: {} };
    },
  });
  await assert.rejects(
    provider.setVisibility({ accessToken: "secret" }, "video-1", {
      approved: true, videoId: "video-1", approverId: "human-1",
      auditId: "accepted", privacyStatus: "public",
    }), /finalizer is required/,
  );
  assert.equal(requests.length, 0);
});

test("concurrent status change fails closed instead of overwriting", async () => {
  const provider = new YouTubePublishingProvider({
    verifyPublicationApproval: async () => true,
    finalizePublicationApproval: async () => {},
    http: async (request) => {
      if (request.method === "GET") {
        return {
          data: { items: [{ id: "video-1", etag: "etag-1", status: { privacyStatus: "private" } }] },
          headers: {},
        };
      }
      const error = new Error("precondition failed");
      error.response = { status: 412, headers: {} };
      throw error;
    },
  });
  await assert.rejects(
    provider.setVisibility({ accessToken: "secret" }, "video-1", {
      approved: true, videoId: "video-1", approverId: "human-1",
      auditId: "accepted", privacyStatus: "public",
    }), /changed concurrently/,
  );
});
