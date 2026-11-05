import type { NextConfig } from "next";

// The browser talks to the API through this app (`/api/*`), so the session cookie is
// first-party and same-origin (Phase 5A). PREUVE_API_INTERNAL_URL is where the API runs as seen
// from the Next server; it's read when the server builds/starts.
const API = (process.env.PREUVE_API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Phase 5C: no framing (clickjacking on Settings), no MIME sniffing, a strict referrer policy,
// and powerful browser features off. A full script CSP would need per-request nonces; for now
// the CSP only covers framing, base URI, form targets and plugins.
const SECURITY_HEADERS = [
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
  },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  // The production image (Dockerfile) builds a self-contained server; local builds don't, since
  // standalone output can need symlink privileges on Windows.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

export default nextConfig;
