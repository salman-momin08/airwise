import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use standalone output for Docker builds; Vercel manages its own optimized serverless output
  output: process.env.VERCEL === "1" ? undefined : "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
