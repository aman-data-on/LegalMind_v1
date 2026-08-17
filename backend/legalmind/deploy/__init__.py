"""Deployment support — locked Step 55.

Locked 55.6 turns the production-blocker list into "an explicit register rather than
an implicit assumption". This package makes that register *runnable*, so the answer to
"is this deployment ready?" is produced rather than remembered.

Locked 55.6 also records the hosting platform, container orchestration, CI/CD
tooling, object-storage provider, monitoring stack and DR objectives as **NOT YET
SPECIFIED**. Nothing here chooses any of them.
"""
