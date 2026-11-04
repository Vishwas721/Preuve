import type { NextConfig } from "next";

// The browser talks to the API through this app (`/api/*`), so the session cookie is
// first-party and same-origin (Phase 5A). PREUVE_API_INTERNAL_URL is where the API runs as seen
// from the Next server; it's read when the server builds/starts.
const API = (process.env.PREUVE_API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

export default nextConfig;
