"use client";

/**
 * The Administration area's own furniture — one sub-navigation and the vocabulary
 * every screen in it shares.
 *
 * Why a shared component rather than four copies: the four screens are one
 * product surface, and the thing most likely to drift between them is what a
 * role is CALLED. The administrator never sees a role code as a label here
 * (`USER` is "Department User"); codes appear only as a `title` on the chip and
 * in the accessible name of the revoke control, where the exact value is the
 * point.
 *
 * Route note: a record id never appears in a path segment (AB-11 r2), so the
 * user and department detail panels are driven by `?user=` / `?department=`
 * on their own screens rather than by a dynamic route.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { RoleTier, User } from "@/lib/types";

export const ADMIN_SECTIONS = [
  { href: "/dashboard/admin", label: "Users" },
  { href: "/dashboard/admin/departments", label: "Departments" },
  { href: "/dashboard/admin/roles", label: "Roles & permissions" },
  { href: "/dashboard/admin/audit", label: "Audit log" },
] as const;

/** Business language for what kind of role a row is (AB-12 r10). */
export const TIER_LABEL: Record<RoleTier, string> = {
  department: "Department",
  platform: "Platform administration",
  break_glass: "Break-glass",
  future_legal: "Legal review (send for review)",
  custom: "Custom",
};

/**
 * Which tiers may be OFFERED when assigning a role to a person.
 *
 * `future_legal` is not here: since AB-100 (2026-10-21) its two roles are offered through
 * `offerable` below, to a caller who may grant them under S-8.
 */
export const ASSIGNABLE_TIERS: RoleTier[] = ["department", "platform", "break_glass", "custom"];

/** S-8's four guarded permissions: only a holder may grant them. */
const GUARDED = ["legal.decision", "legal.approve_customization", "role.manage", "platform.manage"];

/**
 * Whether THIS caller may be offered a role to grant (owner, 2026-10-21; AB-100): the
 * assignable tiers as before, and the two legal-review roles a contract's owner sends a
 * Review to — each only when the caller holds every guarded permission it carries (S-8),
 * so the picker never offers what the server would refuse.
 */
export function offerable(role: { tier: RoleTier; permissions?: string[] },
                          callerPermissions: readonly string[]): boolean {
  if (ASSIGNABLE_TIERS.includes(role.tier)) return true;
  if (role.tier !== "future_legal") return false;
  return (role.permissions ?? []).filter((p) => GUARDED.includes(p))
    .every((p) => callerPermissions.includes(p));
}

export const TIER_ORDER: RoleTier[] = [
  "department", "platform", "break_glass", "custom", "future_legal",
];

export function AdminNav() {
  const pathname = usePathname();
  // Longest match, so `/dashboard/admin/audit` never also lights "Users"
  // (whose href is a prefix of every section).
  const active = ADMIN_SECTIONS
    .filter((s) => pathname === s.href || pathname.startsWith(`${s.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className="ws-tabs ws-adminnav" aria-label="Administration sections">
      {ADMIN_SECTIONS.map((section) => (
        <Link
          key={section.href}
          href={section.href}
          className={`ws-tab ${active === section.href ? "ws-tab--active" : ""}`}
          aria-current={active === section.href ? "page" : undefined}
        >
          {section.label}
        </Link>
      ))}
    </nav>
  );
}

export function AccountStatus({ status }: { status: string }) {
  // Only DISABLED/SUSPENDED get emphasis: ACTIVE is the resting state and a
  // roster where every row shouts is a roster nobody scans.
  const attention = status !== "ACTIVE";
  return (
    <span className={`ws-chip${attention ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}>
      {status === "ACTIVE" ? "Active" : status === "DISABLED" ? "Disabled" : "Suspended"}
    </span>
  );
}

/** A timestamp as a date, or an em dash. Never a guess. */
export function dateOnly(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "—";
}

export function dateTime(value: string | null | undefined): string {
  return value ? value.slice(0, 16).replace("T", " ") : "—";
}

/**
 * How this account signs in, in the administrator's words.
 *
 * The empty case is not a blank: an account with no identity row exists and
 * cannot authenticate by any route, which is a state worth naming out loud
 * rather than rendering as absence.
 */
export function signInMethod(user: User): string {
  if (user.auth_providers.length === 0) return "No sign-in yet";
  return user.auth_providers
    .map((p) => (p === "OIDC" ? "Google SSO" : "Password"))
    .join(" + ");
}
