import test from "node:test";
import assert from "node:assert/strict";
import { normalizeEmail, validateLeadPayload } from "../src/index.js";
test("normalizes email", () => assert.equal(normalizeEmail(" Sea@Example.COM "), "sea@example.com"));
test("accepts a valid lead", () => assert.equal(validateLeadPayload({ fullName:"Sea", email:"sea@example.com", interest:"enterprise", privacyConsent:true, locale:"th" }).valid, true));
test("rejects invalid and bot payloads", () => { const r=validateLeadPayload({ fullName:"S", email:"bad", interest:"other", privacyConsent:false, website:"spam" }); assert.equal(r.valid,false); assert.deepEqual(Object.keys(r.errors).sort(),["email","fullName","interest","privacyConsent","website"].sort()); });
