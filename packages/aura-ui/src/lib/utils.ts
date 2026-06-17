import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// `cn` — the className merge helper the shadcn ui primitives use.
// (Slimmed from the source monorepo's lib/utils.ts: the package only needs
// this one helper, so the `ai`/logger/message-sanitization utilities that the
// full file carried are intentionally left out.)
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
