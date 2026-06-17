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
}

export const DEFAULT_VIEWER_CONFIG: Required<AuraViewerConfig> = {
  signInLabel: 'Reveal your Aura →',
  signInHref: '/login?persona=builder&source=aura',
  shareMode: 'link',
};

export function resolveViewerConfig(c?: AuraViewerConfig): Required<AuraViewerConfig> {
  return { ...DEFAULT_VIEWER_CONFIG, ...(c ?? {}) };
}
