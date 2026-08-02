import type { AuraViewerConfig } from '@vibelevel/aura-ui';

const CONFIGURED_SITE = (
  process.env.AURA_PUBLIC_WEB_URL || 'https://www.vibelevel.ai'
).replace(/\/$/, '');
const SITE =
  CONFIGURED_SITE === 'https://vibelevel.ai'
    ? 'https://www.vibelevel.ai'
    : CONFIGURED_SITE;

// Open Aura's viewer config: funnel local (and unsigned) users to the hosted
// site. Share opens the explicit publication destination because localhost
// profiles are not shareable. Activating it does not upload local data.
export const ossViewerConfig: AuraViewerConfig = {
  signInLabel: 'Sign in',
  signInHref: `${SITE}/login?persona=builder&source=aura-oss`,
  shareMode: 'signup',
  edition: 'local',
  hostedAuraHref: `${SITE}/aura?source=open-aura&intent=publish-profile`,
  publishProfileLabel: 'Publish with VibeLevel Aura',
  showHostedProfilePreview: true,
};
