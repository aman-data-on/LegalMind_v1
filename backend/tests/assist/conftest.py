import pytest


@pytest.fixture(autouse=True)
def _empty_ask_caches():
    """`retrieval/cache.py` is process-wide (`AM-126`): a score memoised from one
    test's fake reranker must never answer another's."""
    from legalmind.assist.retrieval import cache
    cache.reset_for_tests()
    yield
    cache.reset_for_tests()


@pytest.fixture(autouse=True)
def _closed_circuits():
    """The circuit breaker is per process (`llm/breaker.py`): a test whose fake provider
    fails three times must not open the circuit for the next test."""
    from legalmind.assist.llm import breaker
    breaker.reset()
    yield
    breaker.reset()
