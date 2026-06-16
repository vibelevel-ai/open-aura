// Edition knobs for the shared viewer. The DEFAULTS are the hosted SaaS
// behavior, so the SaaS renders exactly as today without passing anything; the
// OSS host overrides these to funnel local (and unsigned) users to vibelevel.ai.
// Keep this dependency-free so PublicAuraShell stays a server-safe component.

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
