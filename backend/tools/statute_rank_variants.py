"""Ranking alternatives for Domain C, for measurement only — nothing here is wired
into `search_statutes`, and importing this module changes no behaviour.

Each variant differs from the shipped ranking in ONE respect, so a difference in the
probe is attributable. The admission floor, the calibrated gate, `RRF_K` and the
vector path are the shipped ones: `statutes._vector_neighbours` is called, not copied.

  current        exactly what ships, which since 2026-09-21 IS demote+live
  act_match_first  the ranking that shipped BEFORE 2026-09-21, kept so the regression
                 it caused stays measurable: `act_match` primary, on a fractional
                 title overlap, which let one Act take every slot
  demote         act_match demoted, repealed Acts not demoted
  live           repealed Acts demoted, act_match still primary
"""
from __future__ import annotations

from sqlalchemy import text as sql_text

from legalmind import config
from legalmind.assist import statutes as S
from legalmind.security import permissions as P

_ACT_MATCH_FIRST = "act_match DESC, exact_section DESC, matched DESC"
_MATCHED_FIRST = "(act_match >= 0.5) DESC, exact_section DESC, matched DESC, act_match DESC"
_LIVE = "(official_title LIKE '%REPEALED%') ASC"

VARIANTS: dict[str, str] = {
    "act_match_first": f"{_ACT_MATCH_FIRST}, score DESC",
    "demote": f"{_MATCHED_FIRST}, score DESC",
    "live": f"{_ACT_MATCH_FIRST}, {_LIVE}, score DESC",
}

_INNER = """
WITH q AS MATERIALIZED (SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex)
SELECT sc.id, s.official_title, s.act_number_year, sc.section_number, sc.sub_section,
       sc.marginal_note, sc.content,
       (SELECT count(*) FROM q, unnest(tsvector_to_array(sc.content_tsv)) l
         WHERE l = ANY(q.lex)) AS matched,
       ts_rank(sc.content_tsv,
               to_tsquery('english', (SELECT array_to_string(lex, ' | ') FROM q)))
           AS score,
       (upper(sc.section_number) = ANY(:wanted)) AS exact_section,
       (SELECT CASE WHEN count(*) = 0 THEN 0.0 ELSE
            count(*) FILTER (WHERE t = ANY(q.lex))::float / count(*) END
          FROM q, unnest(tsvector_to_array(to_tsvector('english', s.official_title))) t
         WHERE t NOT IN ('india', 'indian')) AS act_match,
       sc.ordinal AS ord
  FROM "{schema}".statute_chunks sc JOIN "{schema}".statutes s ON s.id = sc.statute_id
 WHERE (SELECT cardinality(lex) FROM q) > 0
"""
_OUTER = "SELECT * FROM ({inner}) x ORDER BY {order}, official_title, ord LIMIT :limit"


def searcher(db, variant: str, *, limit: int, embed):
    """A `search_statutes`-shaped callable using `variant`'s ordering."""
    if variant == "current":
        return lambda q: S.search_statutes(db, query=q, permissions=frozenset({P.ASSIST_ASK}),
                                           limit=limit, embed_query=embed)
    sql = _OUTER.format(inner=_INNER.format(schema=config.assist_schema()),
                        order=VARIANTS[variant])

    def search(question: str) -> list[S.StatuteHit]:
        wanted = [m.group("num").upper()
                  for m in S._SECTION_IN_QUESTION.finditer(question or "")]
        query = S.expand_aliases(question)
        rows = db.execute(sql_text(sql), {"q": query or "", "wanted": wanted or [""],
                                          "limit": limit * 6}).all()
        floor = 2 if len((query or "").split()) > 1 else 1
        hits = [S.StatuteHit(r.id, r.official_title, r.act_number_year, r.section_number,
                             r.sub_section, r.marginal_note, r.content, float(r.score))
                for r in rows
                if r.exact_section or r.matched >= floor or r.act_match >= 0.5][:limit]
        named = any(r.exact_section or r.act_match >= 0.5 for r in rows)
        if named:
            if len(hits) < limit:
                seen = {h.statute_chunk_id for h in hits}
                hits += [h for h in S._vector_neighbours(db, query, limit=limit,
                                                         embed_query=embed)
                         if h.statute_chunk_id not in seen][:limit - len(hits)]
            return hits
        from legalmind.assist.calibration import RRF_K
        vector = S._vector_neighbours(db, query, limit=limit, embed_query=embed)
        fused: dict = {}
        by_id: dict = {}
        for rank, h in enumerate(vector + hits, start=1):
            rank = rank if rank <= len(vector) else rank - len(vector)
            fused[h.statute_chunk_id] = fused.get(h.statute_chunk_id, 0.0) + 1 / (RRF_K + rank)
            by_id.setdefault(h.statute_chunk_id, h)
        order = list(fused)
        return [by_id[i] for i in sorted(order, key=lambda i: (-fused[i], order.index(i)))][:limit]

    return search
