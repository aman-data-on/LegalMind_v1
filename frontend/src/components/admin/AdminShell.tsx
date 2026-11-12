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

/** The permissions only a holder may grant: S-8's four, and `legal.review` (AM-237 r4) —
 *  `GRANT_GUARDED_PERMISSIONS` on the server. */
const GUARDED = ["legal.decision", "legal.approve_customization", "role.manage", "platform.manage",
  "legal.review"];

/**
 * Whether THIS caller may be offered a role to grant (owner, 2026-10-21; AB-100): the
 * assignable tiers and the two legal-review roles a contract's owner sends a Review to —
 * each only when the caller holds every guarded permission it carries (S-8, AM-237 r4:
 * a Platform Admin is no longer offered DEVELOPER), so the picker never offers what the
 * server would refuse.
 */
export function offerable(role: { tier: RoleTier; permissions?: string[] },
                          callerPermissions: readonly string[]): boolean {
  if (!ASSIGNABLE_TIERS.includes(role.tier) && role.tier !== "future_legal") return false;
  return (role.permissions ?? []).filter((p) => GUARDED.includes(p))
    .every((p) => callerPermissions.includes(p));
}

export const TIER_ORDER: RoleTier[] = [
  "department", "platform", "break_glass", "custom", "future_legal",
];

/** The account-lifecycle actions worth offering as one-click filters. Free text
 *  is still available for anything else, and matches exactly. */
export const COMMON_ACTIONS = [
  { value: "", label: "All actions" },
  { value: "admin.user_created", label: "Account created" },
  { value: "admin.user_updated", label: "Account updated" },
  { value: "admin.user_deleted", label: "Account deleted" },
  { value: "admin.role_granted", label: "Role granted" },
  { value: "admin.role_revoked", label: "Role revoked" },
  { value: "admin.department_created", label: "Department created" },
  { value: "admin.department_updated", label: "Department renamed" },
  { value: "admin.permission_changed", label: "Role permissions changed" },
  { value: "auth.login_failed", label: "Failed sign-in" },
  { value: "auth.session_revoked", label: "Session revoked" },
] as const;

/** B3 p2: an audit action in plain words — the filter's own labels and a few everyday ones;
 *  any other code is said as words ("Contract: read via department scope"). The code itself
 *  stays in the row's Details. UI copy only: the record is unchanged (AUD-01). */
const ACTION_WORDS: Record<string, string> = {
  ...Object.fromEntries(COMMON_ACTIONS.filter((a) => a.value).map((a) => [a.value, a.label])),
  "auth.login_succeeded": "Signed in", "auth.logout": "Signed out",
  "contract.created": "Created a contract", "document.uploaded": "Uploaded a document",
  "review.created": "Started a review", "legal.decision_recorded": "Recorded a decision",
  "legal.finding_escalated": "Asked Legal",
};
const SUBJECT: Record<string, string> = {
  auth: "Sign-in", authz: "Access", admin: "Administration", config: "Standards", assist: "Ask",
};
const words = (code: string) => code.replace(/_/g, " ");
export function actionWords(code: string): string {
  if (ACTION_WORDS[code]) return ACTION_WORDS[code];
  if (code.startsWith("contract.read_via_")) return "Opened a contract";
  const [subject = "", ...rest] = code.split(".");
  const head = SUBJECT[subject] ?? words(subject).replace(/^./, (c) => c.toUpperCase());
  return rest.length ? `${head}: ${words(rest.join(" "))}` : head;
}

export function AdminNav() {
  const pathname = usePathname();
  // Longest match, so `/dashboard/admin/audit` never also lights "Users"
  // (whose href is a prefix of every section).
  const active = ADMIN_SECTIONS
    .filter((s) => pathname === s.href || pathname.startsWith(`${s.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className="lm-tabs" aria-label="Administration sections">
      {ADMIN_SECTIONS.map((section) => (
        <Link
          key={section.href}
          href={section.href}
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
    <span className={`ws-chip${attention ? " lm-lozenge" : ""}`}>
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
