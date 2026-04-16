/** @type {import('next').NextConfig} */
const backendBase =
  (process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );

const nextConfig = {
  output: "standalone",
  // Rewrites passent par un proxy http avec timeout par défaut de 30s ; les recherches
  // chat (SIRENE / Google Places) peuvent dépasser ce délai → ECONNRESET et 500 côté Next.
  experimental: {
    proxyTimeout: 300_000, // 5 min (ms)
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendBase}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
