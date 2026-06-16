/** @type {import('next').NextConfig} */
// The viewer host. Two roles:
//  · /api/aura/* is proxied (rewritten) to the local FastAPI backend, so the
//    shared @vibelevel/aura-ui components' relative fetches reach it.
//  · The shared components carry SaaS-relative funnel links (/login, /aura/*,
//    /u/*); in the OSS host we redirect those out to vibelevel.ai.
const BACKEND = process.env.INTERNAL_API_URL || 'http://localhost:8090';
const SITE = (process.env.AURA_PUBLIC_WEB_URL || 'https://vibelevel.ai').replace(/\/$/, '');

module.exports = {
  reactStrictMode: true,
  transpilePackages: ['@vibelevel/aura-ui'],
  async rewrites() {
    return [{ source: '/api/aura/:path*', destination: `${BACKEND}/api/aura/:path*` }];
  },
  async redirects() {
    return [
      { source: '/login', destination: `${SITE}/login?persona=builder&source=aura-oss`, permanent: false },
      { source: '/aura/:path*', destination: `${SITE}/aura/:path*`, permanent: false },
      { source: '/u/:handle', destination: `${SITE}/u/:handle`, permanent: false },
    ];
  },
};
