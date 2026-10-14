const {
  HttpPublishingProvider,
  standardRateLimit,
} = require("./httpPublishingProvider");

// Writable videos.status fields that must be round-tripped on
// videos.update so a visibility change does not reset them.
// madeForKids is read-only (only selfDeclaredMadeForKids is writable)
// and publishAt is valid only with privacyStatus=private, so neither
// is ever sent here.
const PRESERVED_STATUS_FIELDS = [
  "license",
  "embeddable",
  "publicStatsViewable",
  "selfDeclaredMadeForKids",
  "containsSyntheticMedia",
];

class YouTubePublishingProvider extends HttpPublishingProvider {
  constructor(options = {}) {
    super("youtube", options);
    this.verifyPublicationApproval = options.verifyPublicationApproval || null;
    this.finalizePublicationApproval = options.finalizePublicationApproval || null;
    this.apiUrl = "https://www.googleapis.com/youtube/v3";
    this.uploadUrl = "https://www.googleapis.com/upload/youtube/v3/videos";
  }

  capabilities() {
    return {
      text: false,
      image: false,
      video: true,
      delete: true,
      metrics: true,
    };
  }

  async validateAuth(credentials) {
    const response = await this.request({
      method: "GET",
      url: `${this.apiUrl}/channels`,
      headers: this.bearer(credentials?.accessToken),
      params: { part: "id,snippet", mine: true },
    });
    const channel = response.data.items?.[0];
    if (!channel)
      throw new Error("YouTube credential has no accessible channel");
    return {
      valid: true,
      account: channel,
      rateLimit: standardRateLimit(response.headers),
    };
  }

  async publish(credentials, publication) {
    if (publication.privacyStatus && publication.privacyStatus !== "private") {
      throw new Error("YouTube uploads must start private; publication requires separate human approval");
    }
    const media = publication.media;
    if (!Buffer.isBuffer(media?.buffer) || !media.mimeType)
      throw new Error(
        "YouTube publishing requires buffered video media and mimeType",
      );
    const headers = this.bearer(credentials?.accessToken, {
      "content-type": "application/json",
      "x-upload-content-type": media.mimeType,
      "x-upload-content-length": String(media.size ?? media.buffer.length),
    });
    const initialized = await this.request({
      method: "POST",
      url: this.uploadUrl,
      headers,
      params: { uploadType: "resumable", part: "snippet,status" },
      data: {
        snippet: {
          title: publication.title,
          description: publication.text || "",
          tags: publication.tags || [],
        },
        status: { privacyStatus: "private" },
      },
    });
    const location = initialized.headers?.location;
    if (!location)
      throw new Error("YouTube did not return a resumable upload location");
    const response = await this.request({
      method: "PUT",
      url: location,
      headers: {
        "content-type": media.mimeType,
        "content-length": String(media.size ?? media.buffer.length),
      },
      data: media.buffer,
      maxBodyLength: Infinity,
    });
    return {
      providerPublicationId: response.data.id,
      permalink: `https://www.youtube.com/watch?v=${response.data.id}`,
      rateLimit: standardRateLimit(response.headers),
    };
  }

  async setVisibility(credentials, publicationId, approval) {
    if (!approval || approval.approved !== true || approval.videoId !== publicationId ||
        !approval.approverId || !approval.auditId) {
      throw new Error("A bound, auditable human approval is required for YouTube visibility changes");
    }
    if (approval.privacyStatus !== "public" && approval.privacyStatus !== "unlisted") {
      throw new Error("Unsupported approved visibility");
    }
    if (typeof this.verifyPublicationApproval !== "function" ||
        await this.verifyPublicationApproval(approval) !== true) {
      throw new Error("Canonical server-side approval verification failed");
    }
    // Fail fast before any external mutation: without a wired finalizer
    // a published video would be left unaudited and replayable.
    if (typeof this.finalizePublicationApproval !== "function") {
      throw new Error("A publication finalizer is required for YouTube visibility changes");
    }
    // P1: read current status first so videos.update does not reset other
    // mutable status fields (license, embeddable, selfDeclaredMadeForKids).
    const current = await this.status(credentials, publicationId);
    const existing = current.publication?.status || {};
    const nextStatus = {};
    for (const field of PRESERVED_STATUS_FIELDS) {
      if (existing[field] !== undefined) nextStatus[field] = existing[field];
    }
    nextStatus.privacyStatus = approval.privacyStatus;
    // P2: guard the read-modify-write with the resource ETag so a
    // concurrent Studio/API edit is not silently overwritten.
    const headers = this.bearer(credentials?.accessToken);
    if (current.publication?.etag) headers["If-Match"] = current.publication.etag;
    const response = await this.guardedUpdate(headers, publicationId, nextStatus);
    // Reconcile: confirm YouTube applied the visibility change before any
    // single-use approval is consumed, keeping retries safe.
    let confirmed;
    try {
      confirmed = await this.status(credentials, publicationId);
    } catch (error) {
      if (error?.response?.status === 412 || error?.status === 412) {
        throw new Error("YouTube status changed concurrently; retry the approved transition");
      }
      throw error;
    }
    if (confirmed.publication?.status?.privacyStatus !== approval.privacyStatus) {
      throw new Error("YouTube did not confirm the approved visibility change");
    }
    // P2: consumption/finalization happens only after a confirmed mutation.
    await this.finalizePublicationApproval(approval, confirmed.publication);
    return { publication: confirmed.publication, rateLimit: standardRateLimit(response.headers) };
  }

  async guardedUpdate(headers, publicationId, nextStatus) {
    try {
      return await this.request({
        method: "PUT",
        url: `${this.apiUrl}/videos`,
        headers,
        params: { part: "status" },
        data: { id: publicationId, status: nextStatus },
      });
    } catch (error) {
      if (error?.status === 412 || error?.response?.status === 412) {
        throw new Error("YouTube status changed concurrently; retry the approved transition");
      }
      throw error;
    }
  }

  async delete(credentials, publicationId) {
    const response = await this.request({
      method: "DELETE",
      url: `${this.apiUrl}/videos`,
      headers: this.bearer(credentials?.accessToken),
      params: { id: publicationId },
    });
    return {
      deleted: response.status === 204 || response.status === 200,
      rateLimit: standardRateLimit(response.headers),
    };
  }

  async status(credentials, publicationId) {
    const response = await this.request({
      method: "GET",
      url: `${this.apiUrl}/videos`,
      headers: this.bearer(credentials?.accessToken),
      params: { id: publicationId, part: "id,status,processingDetails" },
    });
    return {
      publication: response.data.items?.[0] || null,
      rateLimit: standardRateLimit(response.headers),
    };
  }

  async metrics(credentials, publicationId) {
    const response = await this.request({
      method: "GET",
      url: `${this.apiUrl}/videos`,
      headers: this.bearer(credentials?.accessToken),
      params: { id: publicationId, part: "statistics" },
    });
    return {
      metrics: response.data.items?.[0]?.statistics || {},
      rateLimit: standardRateLimit(response.headers),
    };
  }
}

module.exports = { YouTubePublishingProvider };
