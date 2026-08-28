#!/usr/bin/env node

import { pbkdf2Sync, randomBytes } from 'node:crypto';

const password = process.argv[2];
if (!password || password.length < 12) {
  console.error('Usage: node scripts/hash-password.mjs "a-password-at-least-12-chars"');
  process.exit(1);
}

const iterations = 310000;
const salt = randomBytes(16).toString('base64url');
const derivedKey = pbkdf2Sync(password, salt, iterations, 32, 'sha256').toString('base64url');
console.log(`pbkdf2_sha256$${iterations}$${salt}$${derivedKey}`);
