"""Architectural boundaries, asserted from the import graph.

Some rules are about what the code must *not* contain, and no behavioural test can prove an
absence. `frontend/src/__tests__/boundary.test.ts` already makes that argument for the frontend
and enforces its three locked rules by reading source. This file is the backend counterpart.

It parses Python with `ast` rather than matching substrings. The existing check in
`test_observability.py::test_logging_never_writes_an_audit_event` is kept exactly as it is —
substring matching catches things an import graph cannot (a mention inside a docstring or a
comment), and the two are complementary. What the substring form cannot do is see an aliased
import, or look inside a subpackage, since it globs one directory without recursing. This file
walks `rglob("*.py")` and resolves the real module names.

**Honest limits, stated rather than implied.** An `ast` walk sees `import` and `from ... import`
statements. It cannot see `importlib.import_module("x")` or `__import__("x")`, where the module
name is a runtime string. `test_dynamic_import_forms_are_absent` closes that specific hole by
asserting those forms are not used at all in the packages under guard, which is true today and
is a much easier property to check than reasoning about what a string might evaluate to.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1] / "legalmind"


def _internal_imports(package: str) -> dict[pathlib.Path, set[str]]:
    """Map each module in ``package`` to the set of sibling `legalmind` packages it imports."""
    found: dict[pathlib.Path, set[str]] = {}
    for path in sorted((_PACKAGE_ROOT / package).rglob("*.py")):
        tree = ast.parse(path.read_text())
        targets: set[str] = set()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # A relative import inside legalmind/<package>/ resolves into that same
                # package at level 1, so it can never cross a boundary and is not a finding.
                names = [node.module] if node.module and node.level == 0 else []
            for name in names:
                parts = name.split(".")
                if parts[0] == "legalmind" and len(parts) > 1 and parts[1] != package:
                    targets.add(parts[1])
        found[path] = targets
    return found


def _external_roots(package: str) -> dict[pathlib.Path, set[str]]:
    """Map each module in ``package`` to the top-level non-`legalmind` modules it imports."""
    found: dict[pathlib.Path, set[str]] = {}
    for path in sorted((_PACKAGE_ROOT / package).rglob("*.py")):
        tree = ast.parse(path.read_text())
        roots: set[str] = set()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module and node.level == 0 else []
            for name in names:
                root = name.split(".")[0]
                if root != "legalmind":
                    roots.add(root)
        found[path] = roots
    return found


ALL_PACKAGES = tuple(sorted(
    p.name for p in _PACKAGE_ROOT.iterdir()
    if p.is_dir() and (p / "__init__.py").exists()
))


# ==========================================================================
# 1. No outbound network client, anywhere
# ==========================================================================
# Locked `AM-25` r9 as amended by `AM-30` (AB-4): the generation call is the ONLY permitted
# egress, and every other path r9 names stays closed. `AM-26`'s "Inference runtime — no
# outbound network route" governs the local embedding and reranking models.
#
# Today this codebase makes NO external network call of any kind, and that is worth pinning as
# a test rather than as a claim in a document. The value is in the future: when the `AM-30`
# generation adapter lands, it must be added to `EGRESS_ALLOWED` by name, in the same commit,
# and the diff says out loud that a new egress path was opened. A reviewer cannot miss it, and
# nobody can add a second one by accident.
#
# `celery` is absent from this list deliberately: it speaks to an internal broker (locked Step
# 39), not the internet. `subprocess` likewise — the OCR path shells out to a local binary.
_NETWORK_MODULES = frozenset({
    "socket", "ssl", "http", "httplib", "urllib", "urllib2", "urllib3",
    "requests", "httpx", "httpcore", "aiohttp", "websockets", "websocket",
    "ftplib", "telnetlib", "smtplib", "poplib", "imaplib", "xmlrpc",
    "google", "googleapiclient", "google_genai", "openai", "anthropic",
    "boto3", "botocore", "paramiko", "pycurl", "grpc",
})

# Modules permitted to hold an outbound network client, with the record that authorizes each.
# Empty today. An entry here is an architectural decision, not a convenience.
EGRESS_ALLOWED: dict[str, str] = {
    # AM-30 t1 (AB-4, locked 2026-08-25): "Generation is the ONLY permitted egress."
    # The adapter uses stdlib urllib deliberately — no provider SDK, so rule 19's
    # separate dependency approval is never triggered — and the AM-31 gate inside it
    # refuses production egress while no written no-training confirmation exists.
    "legalmind.assist.generation": "AM-30 t1/t8; AM-31 gate enforced in-module",
    # ⚠️ SECOND EGRESS, ADDED 2026-09-01, AND REGISTERED AS CONFLICT C-17 — read
    # CONFLICTS.md before assuming this entry is settled.
    #
    # Locked 47.1.3 (OD-9) makes corporate SSO via OIDC the PRIMARY authentication
    # mechanism, and no OIDC flow can exist without a server-to-server call to the
    # identity provider's discovery and token endpoints. So one locked record
    # mandates an egress path that `AM-30` t10's sentence "the provider call is the
    # only external call in the stack" appears to forbid.
    #
    # Per rule 5 that tension is REGISTERED, not resolved: this entry exists so the
    # code matches the mandate in 47.1.3, and C-17 records that the owner must say
    # which reading of t10 governs. The narrow reading — t10 scoped to the document
    # path, which is what its own first sentence is about — is the one the code
    # currently reflects, and it is an interpretation, not a lock.
    #
    # What is NOT in tension, and must stay that way: this path carries an email
    # address and a subject identifier to an authentication provider. It carries no
    # document, no chunk, no clause text and no internal legal position, so `AM-30`
    # t2 and t3 are untouched by it. A test below pins that.
    "legalmind.security.oidc":
        "47.1.3 / SEC-01 (OD-9) mandates OIDC; egress to the IdP is inherent to it. "
        "Registered as C-17 pending the owner's reading of AM-30 t10",
}


@pytest.mark.parametrize("package", ALL_PACKAGES)
def test_no_outbound_network_client_is_imported(package):
    """`AM-25` r9 / `AM-30` t1 — nothing in the application reaches the network.

    A failure here means a new egress path was opened. That is not necessarily wrong, but it is
    never incidental: add the module to `EGRESS_ALLOWED` with the record that authorizes it, or
    remove the import.
    """
    for path, roots in _external_roots(package).items():
        module = f"legalmind.{package}.{path.stem}"
        offending = sorted(roots & _NETWORK_MODULES)
        allowed = module in EGRESS_ALLOWED
        assert not offending or allowed, (
            f"{module} imports network module(s) {offending}. "
            "If this egress is authorized, add the module to EGRESS_ALLOWED naming the "
            "locked record that permits it (AM-30 t1/t8)."
        )


def test_the_egress_allowlist_names_exactly_the_two_authorized_modules():
    """A guard on the guard.

    TWO modules may reach the network, and no third may appear without this test
    failing. Each entry must cite the record that mandates it:

    * `AM-30` t1's generation adapter — the assist lane's one AI egress;
    * the OIDC provider flow, which locked 47.1.3 mandates and which cannot exist
      without an IdP call. Registered as **C-17**, because `AM-30` t10's "the
      provider call is the only external call in the stack" reads against it and
      rule 5 forbids resolving that here.

    An empty list means a module moved without its authorization moving with it.
    """
    assert set(EGRESS_ALLOWED) == {"legalmind.assist.generation",
                                    "legalmind.security.oidc"}
    assert "AM-30" in EGRESS_ALLOWED["legalmind.assist.generation"]
    assert "C-17" in EGRESS_ALLOWED["legalmind.security.oidc"]
    assert "47.1.3" in EGRESS_ALLOWED["legalmind.security.oidc"]


def test_the_oidc_egress_carries_no_document_and_no_legal_position():
    """`AM-30` t2/t3 are untouched by the authentication egress, and must stay so.

    Not a stylistic check. t3 makes LEGAL-02 an egress rule: no Company Standard
    value, Legal Rule, threshold, Rule Outcome, Evaluation or Finding may appear in
    an egressing payload. The OIDC module is therefore forbidden from importing the
    modules that hold any of those, so a future change cannot quietly put a legal
    position into a token request.
    """
    import ast
    from pathlib import Path

    source = Path("legalmind/security/oidc.py").read_text()
    imported = {
        node.module for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = {"evaluation", "mapping", "extraction", "analysis", "workflow",
                 "assist", "reporting"}
    reached = {module for module in imported
               if module.startswith("legalmind.")
               and module.split(".")[1] in forbidden}
    assert reached == set(), reached


# ==========================================================================
# 2. Layering — an allow-list, so anything new fails by default
# ==========================================================================
# Stated as "may import exactly these" rather than "must not import those". A deny-list only
# catches what someone thought of in advance; an allow-list catches a package that does not
# exist yet. That property is the point: when `legalmind/assist/` is created under `AM-27`, no
# rule has to be added for the deterministic core to refuse it — importing it fails here on the
# first run, which is what `AM-25` r1 and r2 need in order to be structural rather than
# aspirational.
#
# Verified against the graph as it stands on 2026-08-25; every entry is what the code does
# today, not an aspiration.
LAYERING: dict[str, frozenset[str]] = {
    "evaluation": frozenset({"db", "domain"}),
    "mapping": frozenset({"db", "domain"}),
    "extraction": frozenset({"domain", "evaluation", "mapping"}),
    "analysis": frozenset({"db", "domain", "evaluation", "extraction", "mapping",
                           "observability", "security", "workflow"}),
    "workflow": frozenset({"db", "domain", "evaluation", "observability", "security"}),
    # The assist lane, added with Gate section 5b unit A2. Its allow-list is the
    # mechanical form of `AM-25` r1: it may read the document model and log, and it
    # imports NONE of `evaluation`, `mapping`, `extraction`, `analysis` or `workflow`.
    #
    # That exclusion is the load-bearing part. `AM-25` r1 makes the deterministic
    # engine the sole producer of every Finding, Evaluation, Classification, Rule
    # Outcome, Mapping State, Legal Decision and Lifecycle transition, and r4 sends
    # "does this document meet our standard?" to the evaluator rather than answering
    # it generatively. An import edge from here into the evaluator is how an assist
    # module quietly acquires the ability to produce one — so the edge does not exist,
    # and routing such a question is the API layer's job, not this package's.
    #
    # `security` entered the set with unit A6: `AM-30` t5 requires every generation
    # call recorded in audit_events, and the audit writer lives in
    # `legalmind.security.audit`. Retrieval authorization itself stays in the API
    # layer's Guard — the assist package still cannot reach the evaluator, the
    # mapping engine, or any other producer of a legal outcome.
    "assist": frozenset({"db", "domain", "observability", "security"}),
}


@pytest.mark.parametrize("package", sorted(LAYERING))
def test_the_deterministic_core_imports_only_its_declared_dependencies(package):
    """Step 38's domain boundaries, and `AM-25` r1/r2 in advance.

    The deterministic core is the authoritative lane. It must not depend on the web layer, the
    worker, or — when it exists — the assist lane. `AM-25` r1 makes the deterministic engine the
    sole producer of every Finding, Evaluation, Classification and Rule Outcome; an import edge
    from this lane into an assist package is how that stops being true.
    """
    permitted = LAYERING[package]
    for path, targets in _internal_imports(package).items():
        extra = sorted(targets - permitted)
        assert not extra, (
            f"legalmind.{package}.{path.stem} imports {extra}, which is not in "
            f"{package}'s declared dependencies {sorted(permitted)}. "
            "If this is a deliberate architectural change, update LAYERING and say why; "
            "if the import is into an assist-lane package, it violates AM-25 r1/r2."
        )


# ==========================================================================
# 3. Observability, recursively and alias-aware
# ==========================================================================
def test_observability_never_imports_the_audit_writer_or_the_models():
    """Locked 53.1 — "an operational log is never a substitute for an audit event".

    `test_observability.py` asserts this by substring over a non-recursive glob. This is the
    same rule resolved from the import graph instead, so an aliased import or a future
    subpackage cannot slip past it. Both checks are kept; neither subsumes the other.
    """
    for path, targets in _internal_imports("observability").items():
        assert "db" not in targets, (
            f"legalmind.observability.{path.stem} imports legalmind.db — evidence lives in the "
            "document store, not in logs (53.3)")

    for path in sorted((_PACKAGE_ROOT / "observability").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                names = [f"{base}.{a.name}" for a in node.names] + [base]
            assert not any(n == "legalmind.security.audit" for n in names), (
                f"legalmind.observability.{path.stem} imports the audit writer; 53.1 keeps the "
                "operational log and the legal record separate")


# ==========================================================================
# 4. No dynamic import escape hatch
# ==========================================================================
def test_dynamic_import_forms_are_absent():
    """Closes the one hole an import-graph check genuinely has.

    An `ast` walk cannot resolve `importlib.import_module(name)` or `__import__(name)` when the
    name is computed. Rather than pretend otherwise, this asserts the forms are unused in the
    guarded packages — true today, and a far cheaper property to verify than reasoning about
    what a runtime string could hold. If one is ever genuinely needed, this test is where the
    justification belongs.
    """
    guarded = set(LAYERING) | {"observability"}
    for package in sorted(guarded):
        for path in sorted((_PACKAGE_ROOT / package).rglob("*.py")):
            source = path.read_text()
            assert "importlib" not in source, f"{path.name}: dynamic import in a guarded package"
            assert "__import__" not in source, f"{path.name}: dynamic import in a guarded package"


def test_every_package_is_covered_by_a_boundary_rule_or_explicitly_exempt():
    """Stops a new package from silently escaping every rule in this file.

    The network rule already runs over every package. This asserts the *layering* rules have not
    quietly stopped covering the deterministic core — for instance if a package were renamed and
    `LAYERING` still named the old one, every parametrized case would vanish and the suite would
    stay green while asserting nothing.
    """
    missing = sorted(set(LAYERING) - set(ALL_PACKAGES))
    assert not missing, f"LAYERING names package(s) that no longer exist: {missing}"

    # Packages with no layering rule, each for a stated reason.
    exempt = {
        "api",            # the web layer: composes everything by design
        "worker",         # dispatch layer: imports the orchestrator it runs
        "db",             # the bottom of the stack
        "domain",         # leaf: pure vocabulary, imports nothing internal
        "security",       # cross-cutting, guarded by its own tests
        "observability",  # covered by its own rule above
        "ingestion",      # covered by the network rule; layering not yet pinned
        "deploy",         # preflight: reads across the stack by design
        "services",       # thin composition layer
    }
    uncovered = sorted(set(ALL_PACKAGES) - set(LAYERING) - exempt)
    assert not uncovered, (
        f"package(s) {uncovered} have no layering rule and are not listed as exempt. "
        "Add a LAYERING entry or an exemption with a reason — a new package must not "
        "escape review by default.")
