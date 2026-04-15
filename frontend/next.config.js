/** @type {import('next').NextConfig} */
const backendBase =
  (process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );

const nextConfig = {
  output: "standalone",
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
