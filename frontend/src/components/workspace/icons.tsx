/**
 * The workspace's icon family — Lucide (owner instruction, 2026-09-09: "Use a
 * consistent icon system such as Lucide", "Don't invent random text controls
 * where a standard icon is clearer").
 *
 * This file used to carry 26 hand-drawn inline SVGs. `lucide-react` was already
 * a dependency — the shell (`Chrome.tsx`), Configuration and Admin all import
 * from it directly — so the workspace was running a second, hand-maintained
 * icon set beside the one the rest of the app uses. The drawings are gone; the
 * names stay, because they are the workspace's vocabulary and every call site
 * already reads correctly with them.
 *
 * Two contracts this wrapper keeps, and the reason it is a wrapper rather than
 * a re-export:
 *
 *  1. DECORATIVE BY DEFAULT. Every icon here sits beside visible text, so it
 *     carries `aria-hidden` and the accessible name lives on the control that
 *     uses it. `lucide-react` does NOT do this on its own, so a bare re-export
 *     would put 26 unnamed graphics into the accessibility tree.
 *  2. `currentColor` stroke, so the status hues keep coming from the token the
 *     parent already carries (`--ws-ok`, `--ws-warn`, `--ws-bad`).
 *
 * Metrics are unchanged from the hand-drawn set — 24px viewBox, 2px stroke,
 * round caps and joins — which is Lucide's own default, so nothing shifts
 * visually beyond the glyph shapes themselves. No emoji anywhere (house rule).
 */

import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  CircleX,
  Clock,
  Download,
  ExternalLink,
  FileCheck,
  FileText,
  History,
  Link2,
  Lock,
  Maximize2,
  RefreshCw,
  Scale,
  ScanText,
  Search,
  Send,
  Sparkles,
  Tag,
  UploadCloud,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";

/** Decorative by default: `aria-hidden`, `focusable="false"`, inherited colour. */
function decorative(Glyph: LucideIcon) {
  return function Icon({ size = 16 }: { size?: number }) {
    return <Glyph size={size} aria-hidden focusable="false" />;
  };
}

export const IconCheckCircle = decorative(CircleCheck);
export const IconAlertCircle = decorative(CircleAlert);
export const IconXCircle = decorative(CircleX);
export const IconSearch = decorative(Search);
/** Client Profiles' page mark (2026-09-10) — the section is about companies. */
export const IconUsers = decorative(Users);
export const IconChevronUp = decorative(ChevronUp);
export const IconChevronDown = decorative(ChevronDown);
export const IconChevronRight = decorative(ChevronRight);
export const IconMaximize = decorative(Maximize2);
export const IconRefresh = decorative(RefreshCw);
export const IconDownload = decorative(Download);
export const IconLink = decorative(Link2);
export const IconArrowLeft = decorative(ArrowLeft);
export const IconArrowRight = decorative(ArrowRight);
export const IconSparkle = decorative(Sparkles);
export const IconSend = decorative(Send);
export const IconHistory = decorative(History);
export const IconFile = decorative(FileText);
export const IconClock = decorative(Clock);
export const IconUploadCloud = decorative(UploadCloud);
export const IconScanText = decorative(ScanText);
export const IconTag = decorative(Tag);
export const IconScale = decorative(Scale);
export const IconFileCheck = decorative(FileCheck);
export const IconLock = decorative(Lock);
export const IconExternal = decorative(ExternalLink);
export const IconX = decorative(X);
