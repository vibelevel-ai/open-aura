// VibeLevel Aura — score-levels + archetype taxonomy (the user-facing legend).
// Mirrors the backend scoring models (aura_model_coding.py / aura_model_writing.py)
// — keep in lockstep. Display-only; no scoring logic here.

export interface AuraLevel {
  name: string; // Emerging | Capable | Strong | Exceptional
  min: number;
  max: number;
  blurb: string;
}

// Bands from get_aura_label() — identical for coding & writing.
export const AURA_LEVELS: AuraLevel[] = [
  { name: 'Emerging', min: 0, max: 3, blurb: 'Getting started — leaning on the AI, steering lightly.' },
  { name: 'Capable', min: 3, max: 6, blurb: 'Solid collaboration — steering and shaping the work.' },
  { name: 'Strong', min: 6, max: 8, blurb: 'High-craft pairing — clear intent and real contribution.' },
  { name: 'Exceptional', min: 8, max: 10, blurb: 'Peak human-AI collaboration — the AI is a pure force-multiplier.' },
];

export interface AuraArchetype {
  name: string;
  tagline: string;
}

// 7 per modality — a parallel set (coding ↔ writing share the idea, differ in name/voice).
export const AURA_ARCHETYPES: Record<'coding' | 'noncoding', AuraArchetype[]> = {
  coding: [
    { name: 'The Delegator', tagline: 'Hands the wheel to the AI, steers lightly, takes what it ships.' },
    { name: 'The Collaborator', tagline: "Pairs tightly with the AI — steers, redirects, and iterates until it's right." },
    { name: 'The Director', tagline: 'Sets crisp intent up front, frames the problem cleanly, lets the AI execute.' },
    { name: 'The Product Builder', tagline: 'Builds toward outcomes — every move serves the user, not just the output.' },
    { name: 'The Architect', tagline: 'Plans first, codifies decisions, builds scaffolding that compounds.' },
    { name: 'The Craftsperson', tagline: 'Shapes every detail — design and product taste applied to the smallest decision.' },
    { name: 'The Vibe Coder', tagline: 'Peak human contribution, balanced excellence — the AI is pure force-multiplier.' },
  ],
  noncoding: [
    { name: 'The Delegator', tagline: 'Hands the pen to the AI, steers lightly, takes what it drafts.' },
    { name: 'The Co-writer', tagline: 'Writes shoulder-to-shoulder with the AI — steers, redirects, and revises until it sings.' },
    { name: 'The Director', tagline: 'Sets crisp intent up front, frames the brief cleanly, lets the AI draft.' },
    { name: 'The Strategist', tagline: 'Thinks in audience and positioning — every word earns its place in the argument.' },
    { name: 'The Architect', tagline: 'Outlines first, imposes logical structure, turns the messy into the clear.' },
    { name: 'The Wordsmith', tagline: 'Shapes every sentence — structure and polish applied to the smallest phrase.' },
    { name: 'The Vibe Writer', tagline: 'Peak human contribution, balanced excellence — the AI is pure force-multiplier.' },
  ],
};

// The 0-10 dimensions a session is scored on (display labels for the profile).
export const AURA_DIMENSION_LABELS = [
  'Prompting',
  'AI Collaboration',
  'Product Thinking',
  'Design Sense',
  'You vs AI',
];

// Best-effort modality for the archetype tab: which modality the user works in most.
export function dominantModality(
  sessions: { modality?: string }[] | undefined,
): 'coding' | 'noncoding' {
  if (!sessions || sessions.length === 0) return 'coding';
  const coding = sessions.filter((s) => s.modality === 'coding').length;
  return coding * 2 >= sessions.length ? 'coding' : 'noncoding';
}
