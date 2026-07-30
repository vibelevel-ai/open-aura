// Edition knobs for Open Aura's viewer. Open Aura is local single-user, so the
// host passes its own config to funnel local (and unsigned) users to the hosted
// site at vibelevel.ai for the things local mode can't do (public profile,
// leaderboard listing, sharing). Keep this dependency-free so the shell stays a
// server-safe component.

export interface AuraViewerConfig {
  /** CTA label in the shell header + the public visitor CTA. */
  signInLabel?: string;
  /** Where that CTA points. Absolute for OSS (→ vibelevel.ai). */
  signInHref?: string;
  /**
   * Share-button behavior:
   *  - 'link'   : copy the public /u or /s link (hosted; needs a claimed handle).
   *  - 'signup' : funnel to VibeLevel sign-up — OSS-local profiles aren't shareable.
   */
  shareMode?: 'link' | 'signup';
  /** Product edition; local enables local-only evidence sections. */
  edition?: 'local' | 'hosted';
  /** Explicit hosted Aura destination for publication. */
  hostedAuraHref?: string;
  /** Label for the explicit hosted publication action. */
  publishProfileLabel?: string;
  /** Whether to render the hosted publication boundary section. */
  showHostedProfilePreview?: boolean;
}

export const DEFAULT_VIEWER_CONFIG: Required<AuraViewerConfig> = {
  signInLabel: 'Reveal your Aura →',
  signInHref: '/login?persona=builder&source=aura',
  shareMode: 'link',
  edition: 'hosted',
  hostedAuraHref: '/aura?source=open-aura&intent=publish-profile',
  publishProfileLabel: 'Publish with VibeLevel Aura',
  showHostedProfilePreview: false,
};

export function resolveViewerConfig(c?: AuraViewerConfig): Required<AuraViewerConfig> {
  return { ...DEFAULT_VIEWER_CONFIG, ...(c ?? {}) };
}
