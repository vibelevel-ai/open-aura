/** @type {import('next').NextConfig} */
// The viewer host. /api/aura/* is proxied to the backend at RUNTIME by the
// route handler in app/api/aura/[...slug] (a build-time rewrite would bake in
// localhost). Here we only redirect the shared components' SaaS-relative funnel
// links (/login, /aura/*, /u/*) out to vibelevel.ai.
const SITE = (process.env.AURA_PUBLIC_WEB_URL || 'https://vibelevel.ai').replace(/\/$/, '');

module.exports = {
  reactStrictMode: true,
  transpilePackages: ['@vibelevel/aura-ui'],
  async redirects() {
    return [
      { source: '/login', destination: `${SITE}/login?persona=builder&source=aura-oss`, permanent: false },
      { source: '/aura/:path*', destination: `${SITE}/aura/:path*`, permanent: false },
      { source: '/u/:handle', destination: `${SITE}/u/:handle`, permanent: false },
    ];
  },
};
