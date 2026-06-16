import type { AuraViewerConfig } from '@vibelevel/aura-ui';

const SITE = (process.env.AURA_PUBLIC_WEB_URL || 'https://vibelevel.ai').replace(/\/$/, '');

// OSS edition config for the shared viewer: funnel local (and unsigned VibeLevel)
// users to the hosted site, and make Share a sign-up funnel (local profiles
// aren't shareable). Passed as a prop into PublicAuraShell + AuraProfile.
export const ossViewerConfig: AuraViewerConfig = {
  signInLabel: 'Sign in',
  signInHref: `${SITE}/login?persona=builder&source=aura-oss`,
  shareMode: 'signup',
};
