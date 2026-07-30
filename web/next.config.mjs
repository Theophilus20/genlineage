/** @type {import('next').NextConfig} */
const API = process.env.GENLINEAGE_API || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/ws/:path*", destination: `${API}/ws/:path*` },
    ];
  },
};

export default nextConfig;
