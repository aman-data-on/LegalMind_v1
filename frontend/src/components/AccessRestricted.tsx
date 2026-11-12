/**
 * Locked 52.3: "A section the user cannot view renders an explicit **'Access
 * restricted'** state rather than an empty or broken view."
 *
 * Note carefully what this may and may not say. It states that *this section of
 * the application* requires a permission the caller does not hold. It must never
 * describe the object behind it, because that would be a disclosure — and for an
 * object outside the caller's scope there is nothing to describe anyway, since the
 * server answered with a byte-identical 404 (49.5 r1, 52.4).
 *
 * `PermissionGate` is the same rule applied to a control rather than a section:
 * 52.3 says "A control the user cannot invoke is not rendered", so its default is
 * to render nothing at all.
 */

import type { ReactNode } from "react";

export function AccessRestricted({ what }: { what?: string }) {
  return (
    <section className="access-restricted" role="note">
      <h2>Access restricted</h2>
      {/* GP-23 (owner OK 2026-11-11, wording only): why it is blocked, in the reader's
          words, and the one thing they can do. The server still checks every request. */}
      <p>
        {what
          ? `Your account doesn’t include access to ${what}.`
          : "Your account doesn’t include access to this section."}
      </p>
      <p className="hint">Ask your administrator if you need it.</p>
    </section>
  );
}

/**
 * Presentation-only gating (52.1 r3, 43.31). Hiding a control is a usability
 * affordance, never a security control: the server authorizes every operation
 * regardless, so a gate that failed open would change nothing about what actually
 * happens.
 */
export function PermissionGate({
  granted,
  children,
  fallback = null,
}: {
  granted: boolean;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return granted ? <>{children}</> : <>{fallback}</>;
}
