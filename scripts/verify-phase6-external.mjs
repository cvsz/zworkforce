#!/usr/bin/env node
import { createHash, randomUUID } from "node:crypto";

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function authHeaders(json = false) {
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${required("STAGING_BEARER_TOKEN")}`,
  };
  if (process.env.STAGING_CF_ACCESS_CLIENT_ID && process.env.STAGING_CF_ACCESS_CLIENT_SECRET) {
    headers["CF-Access-Client-Id"] = process.env.STAGING_CF_ACCESS_CLIENT_ID;
    headers["CF-Access-Client-Secret"] = process.env.STAGING_CF_ACCESS_CLIENT_SECRET;
  }
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

function externalUrl(name) {
  const url = new URL(required(name));
  if (url.protocol !== "https:" || url.username || url.password || !url.hostname.includes(".")) {
    throw new Error(`${name} must be an external HTTPS URL without embedded credentials`);
  }
  return url;
}

async function jsonResponse(response, operation) {
  if (!response.ok) throw new Error(`${operation} returned HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || typeof payload !== "object") throw new Error(`${operation} returned an invalid response`);
  return payload;
}

export async function verifyAlert() {
  const marker = `phase6-${randomUUID()}`;
  const create = await jsonResponse(await fetch(externalUrl("ALERT_TEST_URL"), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ marker, message: "Phase 6 external alert delivery verification" }),
    redirect: "error",
  }), "alert trigger");
  if (create.marker !== marker || create.delivered !== true) throw new Error("alert trigger was not accepted");
  const statusUrl = externalUrl("ALERT_DELIVERY_STATUS_URL");
  statusUrl.searchParams.set("marker", marker);
  const status = await jsonResponse(await fetch(statusUrl, { headers: authHeaders(), redirect: "error" }), "alert delivery status");
  if (status.marker !== marker || status.delivered !== true) throw new Error("alert delivery was not confirmed");
  return { status: "verified", markerHash: createHash("sha256").update(marker).digest("hex"), deliveredAt: status.deliveredAt ?? create.deliveredAt ?? null };
}

export async function verifyUpload() {
  const content = Buffer.from(`phase6 external upload ${randomUUID()}\n`, "utf8");
  const form = new FormData();
  form.set("file", new Blob([content], { type: "text/plain" }), "phase6-evidence.txt");
  const payload = await jsonResponse(await fetch(externalUrl("AI_UPLOAD_URL"), {
    method: "POST",
    headers: authHeaders(),
    body: form,
    redirect: "error",
  }), "AI upload");
  const expectedDigest = createHash("sha256").update(content).digest("hex");
  if (payload.status !== "verified" || payload.sha256 !== expectedDigest || payload.size !== content.length) throw new Error("AI upload integrity was not verified");
  if (typeof payload.provider !== "string" || !payload.provider || typeof payload.requestId !== "string" || !payload.requestId) throw new Error("AI upload lacks external provider request evidence");
  return { status: "verified", provider: payload.provider, requestIdHash: createHash("sha256").update(payload.requestId).digest("hex"), sha256: payload.sha256, size: payload.size };
}

async function main() {
  const operation = process.argv[2];
  const result = operation === "alert" ? await verifyAlert() : operation === "upload" ? await verifyUpload() : null;
  if (!result) throw new Error("usage: verify-phase6-external.mjs {alert|upload}");
  console.log(JSON.stringify(result));
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => { console.error(`phase6 external verification failed: ${error.message}`); process.exitCode = 1; });
}
