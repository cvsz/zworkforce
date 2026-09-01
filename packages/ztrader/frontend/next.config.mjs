import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "../../..");

/** @type {import("next").NextConfig} */
const nextConfig = {
  output: 'standalone',
  outputFileTracingRoot: repoRoot,
  experimental: {
    turbo: {
      resolveAlias: {
        next: path.resolve(frontendRoot, "node_modules/next"),
      },
    },
  },
};

export default nextConfig;
