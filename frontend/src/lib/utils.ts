/**
 * `cn` — the class-name merger every shadcn/ui primitive imports (2026-09-15).
 *
 * `clsx` resolves conditionals; `tailwind-merge` then drops the earlier of two
 * conflicting Tailwind utilities, so a `className` passed by a call site wins
 * over the primitive's own default instead of depending on stylesheet order.
 *
 * Nothing but `src/components/ui/` should need this. LegalMind's own components
 * use the hand-authored class vocabulary (`.card`, `.btn`, `.field`, `.ws-*`),
 * and a template literal is the right tool there.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
