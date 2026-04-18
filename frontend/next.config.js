/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // `/api/*` → `src/app/api/[[...path]]/route.ts` (évite le proxy `rewrites` ~30s → ERR_CONNECTION_CLOSED sur l’Atelier).
};

module.exports = nextConfig;
