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
EGRESS_ALLOWED: dict[str, str] = {}


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


def test_the_egress_allowlist_is_empty_until_a_record_authorizes_an_entry():
    """A guard on the guard.

    `AM-31` g4 records the real-contract egress gate as CLOSED, and no generation adapter
    exists yet. If this fails, someone added an allow-list entry — check that an appended lock
    record actually authorizes it, and that `AM-30` t8's network allow-list exists too, since
    an application-level import is not a network control.
    """
    assert EGRESS_ALLOWED == {}


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
    # `security` is deliberately absent for now. Retrieval authorization lands in A3
    # (`AM-25` r6, applied inside the query), and adding the dependency before the code
    # that needs it would weaken the rule to no purpose.
    "assist": frozenset({"db", "domain", "observability"}),
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
