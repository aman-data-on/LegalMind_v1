# Statute intake — what C-16 needs, exactly

**Status: 📁 DERIVED — an intake specification. It decides nothing and supplies
nothing**; rule 21 stands: statute material is supplied by the owner, never authored or
fetched by us. Prepared 2026-08-27. Companion to
[SOURCE_MATERIAL_INTAKE.md](SOURCE_MATERIAL_INTAKE.md) and the AB-5 proposal
([AB5_DOMAIN_CORPUS_PROPOSAL.md](AB5_DOMAIN_CORPUS_PROPOSAL.md), `AM-32` r6–r7).

---

## 1 · What is missing (C-16, verbatim need)

| # | Item | State |
|---|---|---|
| 1 | **Negotiable Instruments Act, 1881** — the product vision's headline example ("what does Section 138 say?") | Never supplied |
| 2 | **The Evidence Act** — named in the v1 statute set | Never supplied — **and see the question in §3** |
| 3 | **Provenance confirmation for the seven statutes already on disk** (Contract Act 1872 · IT Act 2000 · SPDI Rules 2011 · Companies Act 2013 · CERT-In Directions 2022 · DPDP Act 2023 · IT Rules 2021) | On disk, but not sourced from India Code — vision §9.2 makes India Code canonical "as a hard rule" |
| 4 | **The curated judgment list** | The plan assigns selection to the legal team; no list exists |

## 2 · Where to get them (for the person doing the supplying)

**India Code — `https://www.indiacode.nic.in`** — the Government of India's official
statute repository, and the only source the vision accepts for Indian statutes.
Search the Act by name/year → download the official PDF ("as amended" consolidated
text where offered) → note the page URL and the "as on" date. Place files in
`LEGALMIND_SOURCE_MATERIAL_DIR` (`legal-docs/`, gitignored — locked 54.6 keeps them
out of the repository), like every other supplied document.

I can *verify* a supplied file's structure and record its hash; I will not download
statutes myself — sourcing is an owner act so provenance is attested by you, not
asserted by a script.

## 3 · One question only you can answer

**"Evidence Act" is ambiguous in 2026.** The Indian Evidence Act, 1872 was repealed by
the **Bharatiya Sakshya Adhiniyam, 2023** (in force 1 July 2024). Which do you want in
the corpus — the BSA 2023 (current law), the 1872 Act (still relevant to older
matters), or both, each labelled with its in-force window? The registry design
(`AM-32` r6) can record either; it cannot choose. *The same question technically
touches nothing else in the v1 set — the other six statutes stand unrepealed, though
several are heavily amended, which is what the "as amended" date field is for.*

## 4 · What each supplied statute must arrive with (the provenance record)

Per `AM-32` r6 (proposed), ingestion **refuses** a statute without all of:

```text
official_title        e.g. "The Negotiable Instruments Act, 1881"
act_number_year       e.g. "Act No. 26 of 1881"
jurisdiction          e.g. "IN"
source                "India Code" (the hard rule for Indian statutes)
source_url            the indiacode.nic.in page the PDF came from
as_amended_date       the consolidation date printed on the document
file_sha256           computed at intake and recorded
supplied_by / date    who placed it in LEGALMIND_SOURCE_MATERIAL_DIR, when
```

## 5 · How statutes will be chunked (design, implemented once AM-32 is approved)

**Section-based, never page- or clause-based.** A statute's addressable unit is the
section (`AM-32` r7): each chunk = one section (or sub-section where a section is
long), carrying `section_number`, `sub_section`, `marginal_note`, and its character
offsets in the source. A Domain C citation is always **Act + section** ("NI Act,
s. 138"), never a bare page. Chapter headings and schedules are chunked as their own
units, labelled as such. The existing contract chunker is *not* reused as-is —
contracts number clauses (§17.2), statutes number sections with a different grammar
(138, 138A, provisos, explanations); a statute-specific splitter is part of the
Domain C work and gets its own tests against the supplied PDFs.

## 6 · What statutes will never do here (standing rules, restated)

Background law only (source-material ruling, 2026-08-18): no Requirement, Company
Standard, Legal Rule, threshold or acceptance position is derived from a statute; a
statute never enters the evaluator; statute text answers "what does the law say",
never "is this contract acceptable to us". Rule 7 and rule 21 in a new coat.

## 7 · Until this arrives

The workspace shows Domain C as a visible, honest placeholder ("Statute search — not
yet available; awaiting source material"), never a broken pane and never a silent
absence. Blocked is a legitimate state and is displayed as one.
