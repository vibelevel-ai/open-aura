import React from "react";

export function AuraPublishCta({ href, label }: { href: string; label: string }) {
  return (
    <section className="mt-10 overflow-hidden rounded-[22px] border border-[rgba(0,230,118,.22)] bg-[#07140f] p-6 text-center md:p-10">
      <h2 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">
        Turn your local Aura into a profile worth sharing
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-[rgba(255,255,255,.62)] md:text-base">
        Your Aura stays local. Open VibeLevel Aura to publish a recruiter-facing profile with projects, hiring details, and verified evidence. Nothing is uploaded automatically.
      </p>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-6 inline-flex rounded-xl bg-white px-5 py-3 text-sm font-semibold text-[#07110b] transition-colors hover:bg-[#e8eef8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#07140f]"
      >
        {label} →
      </a>
    </section>
  );
}
