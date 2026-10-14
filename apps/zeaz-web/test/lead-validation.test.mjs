import test from "node:test";
import assert from "node:assert/strict";
import worker, { adsEnabled, createHtmlSecurityHeaders, normalizeEmail, validateLeadPayload } from "../src/index.js";
test("normalizes email", () => assert.equal(normalizeEmail(" Sea@Example.COM "), "sea@example.com"));
test("accepts a valid lead", () => assert.equal(validateLeadPayload({ fullName:"Sea", email:"sea@example.com", interest:"enterprise", privacyConsent:true, locale:"th" }).valid, true));
test("rejects invalid and bot payloads", () => { const r=validateLeadPayload({ fullName:"S", email:"bad", interest:"other", privacyConsent:false, website:"spam" }); assert.equal(r.valid,false); assert.deepEqual(Object.keys(r.errors).sort(),["email","fullName","interest","privacyConsent","website"].sort()); });
test("enforces nonce-based strict CSP for HTML", () => { const csp=createHtmlSecurityHeaders("testnonce")["content-security-policy"]; assert.match(csp, /script-src \'nonce-testnonce\' \'strict-dynamic\' https:/); assert.match(csp, /frame-src https:/); assert.match(csp, /object-src \'none\'/); });
test("keeps AdSense disabled until certified CMP readiness is explicitly configured", async () => {
  assert.equal(adsEnabled({}), false);
  assert.equal(adsEnabled({ GOOGLE_CERTIFIED_CMP_READY: "false" }), false);
  assert.equal(adsEnabled({ GOOGLE_CERTIFIED_CMP_READY: "true" }), true);
  const disabled = await (await worker.fetch(new Request("https://www.zeaz.dev/"), {}, {})).text();
  assert.doesNotMatch(disabled, /pagead2\.googlesyndication\.com/);
  const enabled = await (await worker.fetch(new Request("https://www.zeaz.dev/"), { GOOGLE_CERTIFIED_CMP_READY: "true" }, {})).text();
  assert.match(enabled, /pagead2\.googlesyndication\.com/);
});
test("serves authorized-seller ads.txt", async () => {
  const res = await worker.fetch(new Request("https://www.zeaz.dev/ads.txt"), {}, {});
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type") || "", /text\/plain/);
  assert.equal((await res.text()).trim(), "google.com, pub-4971034675329740, DIRECT, f08c47fec0942fa0");
});
test("keeps ads off 404 and documents certified CMP processing on privacy page", async () => {
  const notFound = await worker.fetch(new Request("https://www.zeaz.dev/nope"), { GOOGLE_CERTIFIED_CMP_READY: "true" }, {});
  assert.equal(notFound.status, 404);
  assert.doesNotMatch(await notFound.text(), /pagead2\.googlesyndication\.com/);
  const privacy = await (await worker.fetch(new Request("https://www.zeaz.dev/privacy"), {}, {})).text();
  assert.match(privacy, /Google-certified consent management platform/);
  assert.match(privacy, /Google AdSense/);
});
