"""Re-export: the Constitution's checkable Unacceptable Positions live in
`legalmind.domain.constitution_boundaries` since AM-159 (2026-10-17), so the assist
lane can apply the same projection the review applies — it may import `domain`, never
`evaluation` (`test_import_boundaries.py`; `AI-01`). Every caller is unchanged."""
from legalmind.domain.constitution_boundaries import (  # noqa: F401
    ConstitutionProhibition,
    constitution_prohibition_for,
)
