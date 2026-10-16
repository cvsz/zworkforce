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
    for (const field of ["madeForKids", "containsSyntheticMedia"]) {
      if (typeof publication[field] !== "boolean") {
        throw new Error(`YouTube upload requires an explicit boolean ${field} disclosure`);
      }
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
        status: {
          privacyStatus: "private",
          selfDeclaredMadeForKids: publication.madeForKids,
          containsSyntheticMedia: publication.containsSyntheticMedia,
        },
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
        !approval.approverId || !approval.auditId || !approval.expectedEtag) {
      throw new Error("A bound, auditable human approval is required for YouTube visibility changes");
    }
    if (approval.privacyStatus !== "public" && approval.privacyStatus !== "unlisted") {
      throw new Error("Unsupported approved visibility");
    }
    // Check both callbacks before invoking the verifier: verification may
    // reserve or claim approval state and must not run without a finalizer.
    if (typeof this.finalizePublicationApproval !== "function") {
      throw new Error("A publication finalizer is required for YouTube visibility changes");
    }
    if (typeof this.verifyPublicationApproval !== "function") {
      throw new Error("Canonical server-side approval verifier is required");
    }
    if (await this.verifyPublicationApproval(approval) !== true) {
      throw new Error("Canonical server-side approval verification failed");
    }
    // P1: read current status first so videos.update does not reset other
    // mutable status fields (license, embeddable, selfDeclaredMadeForKids).
    const current = await this.status(credentials, publicationId);
    // The approval is bound to the exact revision the human reviewed:
    // any title/description/thumbnail/status edit after approval
    // changes the ETag and invalidates it.
    let confirmed;
    if (current.publication?.etag === approval.expectedEtag) {
      confirmed = await this.reconcileTransition(credentials, publicationId, approval, current);
    } else if (current.publication?.status?.privacyStatus === approval.privacyStatus) {
      // Visibility alone is not evidence that this job performed the write.
      // An external API client may have changed the resource after approval.
      // Fail closed until a durable, atomically claimed outcome is available.
      throw new Error("Stale approval: visibility matches without a verified durable transition claim");
    } else {
      throw new Error("Stale approval: video revision changed since human approval");
    }
    // P2: consumption/finalization happens only after a confirmed mutation.
    await this.finalizePublicationApproval(approval, confirmed.publication);
    return { publication: confirmed.publication, rateLimit: standardRateLimit(confirmed.publication?.rateLimitHeaders || {}) };
  }

  async reconcileTransition(credentials, publicationId, approval, current) {
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
    confirmed.publication.rateLimitHeaders = response.headers;
    return confirmed;
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
