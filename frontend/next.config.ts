import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use standalone output for Docker builds; Vercel manages its own optimized serverless output
  output: process.env.VERCEL === "1" ? undefined : "standalone",
  outputFileTracingRoot:
    process.env.VERCEL === "1" ? path.join(__dirname, "..") : undefined,
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    if (process.env.VERCEL === "1") {
      return [];
    }
    const backendOrigin = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
