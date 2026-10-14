import test from "node:test";
import assert from "node:assert/strict";
import worker, { createHtmlSecurityHeaders, hasAdsConsent, normalizeEmail, validateLeadPayload } from "../src/index.js";
test("normalizes email", () => assert.equal(normalizeEmail(" Sea@Example.COM "), "sea@example.com"));
test("accepts a valid lead", () => assert.equal(validateLeadPayload({ fullName:"Sea", email:"sea@example.com", interest:"enterprise", privacyConsent:true, locale:"th" }).valid, true));
test("rejects invalid and bot payloads", () => { const r=validateLeadPayload({ fullName:"S", email:"bad", interest:"other", privacyConsent:false, website:"spam" }); assert.equal(r.valid,false); assert.deepEqual(Object.keys(r.errors).sort(),["email","fullName","interest","privacyConsent","website"].sort()); });
test("enforces nonce-based strict CSP for HTML", () => { const csp=createHtmlSecurityHeaders("testnonce")["content-security-policy"]; assert.match(csp, /script-src \'nonce-testnonce\' \'strict-dynamic\' https:/); assert.match(csp, /frame-src https:/); assert.match(csp, /object-src \'none\'/); });
test("reads ads consent from cookies only", () => {
  const granted = { headers: { get: (n) => n === "cookie" ? "a=1; zeaz_ads_consent=granted; b=2" : null } };
  const denied = { headers: { get: (n) => n === "cookie" ? "zeaz_ads_consent=denied" : null } };
  const missing = { headers: { get: () => null } };
  assert.equal(hasAdsConsent(granted), true);
  assert.equal(hasAdsConsent(denied), false);
  assert.equal(hasAdsConsent(missing), false);
  assert.equal(hasAdsConsent(null), false);
});
test("loads AdSense only with consent, shows banner otherwise", async () => {
  const plain = await (await worker.fetch(new Request("https://www.zeaz.dev/"), {}, {})).text();
  assert.doesNotMatch(plain, /pagead2\.googlesyndication\.com/);
  assert.match(plain, /zeaz-consent/);
  const consented = await (await worker.fetch(new Request("https://www.zeaz.dev/", { headers: { cookie: "zeaz_ads_consent=granted" } }), {}, {})).text();
  assert.match(consented, /pagead2\.googlesyndication\.com/);
  assert.doesNotMatch(consented, /zeaz-consent/);
});
test("keeps ads off 404 and discloses Google processing on privacy page", async () => {
  const notFound = await worker.fetch(new Request("https://www.zeaz.dev/nope", { headers: { cookie: "zeaz_ads_consent=granted" } }), {}, {});
  assert.equal(notFound.status, 404);
  assert.doesNotMatch(await notFound.text(), /pagead2\.googlesyndication\.com/);
  const privacy = await (await worker.fetch(new Request("https://www.zeaz.dev/privacy"), {}, {})).text();
  assert.match(privacy, /Google AdSense/);
});
