# Agent instructions

**Read [CLAUDE.md](CLAUDE.md) before doing anything in this repository.** It is the single authoritative instruction file for every AI coding agent working here, regardless of vendor. This file exists only so agents that look for `AGENTS.md` find their way there.

Nothing is duplicated here — duplicated rules drift.

Minimum context before you act:

| | |
|---|---|
| The rules | [CLAUDE.md](CLAUDE.md) |
| Where everything lives | [docs/README.md](docs/README.md) |
| What is settled | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| What is *not* settled | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| How to propose a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| How to work here, day to day | [docs/00-project/CLAUDE_WORKING_RULES.md](docs/00-project/CLAUDE_WORKING_RULES.md) |

**LegalMind is a specification-first project, and implementation is authorized and underway** — `IMPL-01` (2026-08-17) for the V1 engine, `IMPL-02` (2026-08-25) for the assist lane. *(This paragraph previously said the project was "in the specification phase" and that application code must not be written; that was true when written and became misleading once `IMPL-01` landed. Corrected 2026-08-25.)*

**Specification-first still governs everything.** Authorization covers **building what is already locked** and confers no authority to decide what is not. Do not implement an unspecified behavior, add a table beyond `AM-27`'s nine, or add a technology or dependency without approval. Do not invent a legal rule, threshold, or evaluator behavior. When you find a contradiction, report it — never resolve it yourself.
