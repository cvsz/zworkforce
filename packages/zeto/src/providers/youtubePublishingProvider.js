const {
  HttpPublishingProvider,
  standardRateLimit,
} = require("./httpPublishingProvider");

class YouTubePublishingProvider extends HttpPublishingProvider {
  constructor(options = {}) {
    super("youtube", options);
    this.verifyPublicationApproval = options.verifyPublicationApproval || null;
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
    const response = await this.request({
      method: "PUT",
      url: `${this.apiUrl}/videos`,
      headers: this.bearer(credentials?.accessToken),
      params: { part: "status" },
      data: { id: publicationId, status: { privacyStatus: approval.privacyStatus } },
    });
    return { publication: response.data, rateLimit: standardRateLimit(response.headers) };
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
