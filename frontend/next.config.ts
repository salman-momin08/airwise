import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use standalone output for Docker builds; Vercel manages its own optimized serverless output
  output: process.env.VERCEL === "1" ? undefined : "standalone",
  outputFileTracingRoot:
    process.env.VERCEL === "1" ? path.join(__dirname, "..") : path.resolve(__dirname),
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    optimizePackageImports: ["recharts", "lucide-react"],
  },
  async headers() {
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
      {
        key: "Content-Security-Policy",
        value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'",
      },
      {
        key: "Permissions-Policy",
        value: "geolocation=(self), camera=(), microphone=(), payment=()",
      },
      { key: "X-DNS-Prefetch-Control", value: "on" },
    ];
    if (process.env.NODE_ENV === "production") {
      securityHeaders.push({
        key: "Strict-Transport-Security",
        value: "max-age=63072000; includeSubDomains",
      });
    }
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
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
