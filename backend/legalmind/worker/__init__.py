"""Background jobs — locked Step 39 (Celery + Redis), locked 55.1.

Locked 55.1: "Workers run the SAME image as the API — a version skew would break
`evaluator_version` reproducibility, so they deploy together." This package is
therefore part of the application, not a service beside it:

```text
api      uvicorn legalmind.api.app:app
worker   celery -A legalmind.worker.app worker -Q analysis
```

`dispatch` is the only module a caller needs. Importing `app` or `tasks` from a
request path is unnecessary and pulls Celery into the API's import graph for nothing.
"""

from legalmind.worker.dispatch import AnalysisDispatch, DispatchMode, dispatch_analysis

__all__ = ["AnalysisDispatch", "DispatchMode", "dispatch_analysis"]
