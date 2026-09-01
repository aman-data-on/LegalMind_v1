"""Verify the Gemini connection — configuration first, then one synthetic call.

A release/operations tool, run by hand or by the deployment pipeline BEFORE the
assist lane is relied on in an environment. It never invents a second egress path:
the live check goes through ``legalmind.assist.generation.generate`` — the one
seam `AM-26` r1 permits — so every gate, payload screen and audit rule applies to
this tool exactly as it applies to the product.

Two modes:

  --check-only    (default) validates configuration and the gate decision for the
                  named environment. NO network call is made.
  --live          additionally makes ONE generation call with a synthetic question
                  and synthetic evidence. Refused in production while `AM-31` is
                  CLOSED — by the gate itself, not by this tool's politeness.

The synthetic payload is fixed, self-describing test text (locked 55.3: development
and staging are synthetic-only environments; this tool sends nothing else anywhere).

Exit codes: 0 ready · 1 not ready (each failed check printed) · 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys

from legalmind.assist import generation

# Deliberately self-describing and legally meaningless. Contains no counterparty,
# no clause text from any supplied document, and no internal legal position.
_SYNTHETIC_QUESTION = "What colour is the vehicle described in the excerpt?"
_SYNTHETIC_EVIDENCE = [
    "This is a synthetic connectivity-test excerpt for LegalMind. "
    "The vehicle described in this excerpt is blue."
]

_ENVIRONMENTS = ("development", "staging", "production")


def _checks(environment: str) -> list[tuple[str, bool, str]]:
    """Configuration checks that require no network. (name, ok, detail)."""
    results: list[tuple[str, bool, str]] = []

    # "Set" is not the same question as "is a credential". This tool reported
    # PASS for a literal `***` on 2026-09-01 while the provider answered 400
    # API_KEY_INVALID — the check was true and useless. It now asks the question
    # the caller actually means, using the same rule the application applies, so
    # the tool and the runtime can never disagree.
    raw = os.environ.get("LEGALMIND_GEMINI_API_KEY", "")
    if not raw:
        detail = ("LEGALMIND_GEMINI_API_KEY is not set — set it in the server "
                  "environment (/root/.legalmind.env), never in a file in the "
                  "repository")
    elif generation.is_placeholder_credential(raw):
        detail = (f"LEGALMIND_GEMINI_API_KEY is SET BUT IS A PLACEHOLDER "
                  f"({len(raw.strip())} chars), not a credential. The provider "
                  "will refuse it. Run `bash tools/set_gemini_key.sh`")
    else:
        detail = "LEGALMIND_GEMINI_API_KEY is a plausible credential (never printed)"
    results.append((
        "api_key",
        bool(raw) and not generation.is_placeholder_credential(raw),
        detail,
    ))

    model = os.environ.get("LEGALMIND_GENERATION_MODEL", generation.DEFAULT_MODEL)
    pinned = "latest" not in model
    results.append((
        "model_pin",
        pinned,
        f"model identifier is {model!r}" if pinned
        else f"model identifier {model!r} is a floating alias — AM-30 t7 requires "
             "a pinned, dated identifier",
    ))

    permitted, reason = generation.gate_permits_egress(environment)
    # The gate refusing production is CORRECT behaviour while AM-31 is CLOSED —
    # report it as the state it is, and fail readiness only because generation
    # cannot serve there yet, not because anything is misconfigured.
    results.append(("am31_gate", permitted, reason))

    return results


def _live_call(environment: str) -> tuple[bool, str]:
    """One synthetic generation call through the production seam."""
    try:
        result = generation.generate(
            _SYNTHETIC_QUESTION, list(_SYNTHETIC_EVIDENCE),
            environment=environment, request_id="verify-gemini-connection")
    except generation.GenerationRefused as exc:
        return False, f"refused: {exc}"
    except generation.GenerationUnavailable as exc:
        return False, f"provider unavailable: {exc}"

    text = result.text.strip()
    if not text:
        return False, "provider returned an empty answer"
    # The prompt contract demands citation markers; a reply with none means the
    # pinned model is not honouring the grounded-answer contract and the
    # guardrails would refuse every real answer it produced.
    if "[1]" not in text and text != "NOT FOUND":
        return False, (f"reply carries no citation marker — model {result.model!r} "
                       "is not honouring the grounded-answer prompt contract")
    return True, (f"model={result.model} prompt={result.prompt_version} "
                  f"latency_ms={result.latency_ms} "
                  f"payload_sha256={result.payload_sha256[:12]}…")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--environment", choices=_ENVIRONMENTS, default="development",
                    help="the environment whose posture is being verified")
    ap.add_argument("--live", action="store_true",
                    help="make one synthetic generation call (default: config only)")
    args = ap.parse_args(argv)

    print(f"Gemini connection verification — environment={args.environment}, "
          f"AM31_GATE={generation.AM31_GATE}")

    ok = True
    for name, passed, detail in _checks(args.environment):
        print(f"  {'PASS' if passed else 'FAIL':4}  {name:10}  {detail}")
        ok = ok and passed

    if args.live:
        if not ok:
            print("  SKIP  live_call    configuration checks failed; not calling")
        else:
            passed, detail = _live_call(args.environment)
            print(f"  {'PASS' if passed else 'FAIL':4}  live_call   {detail}")
            ok = ok and passed
    else:
        print("  ----  live_call    not requested (--live); no network call made")

    print("READY" if ok else "NOT READY")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
