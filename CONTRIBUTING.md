# Contributing

This repo follows the engineering rules in [`docs/rules.md`](docs/rules.md). Read that file in full before making changes; the summary below is a quick-reference, not a replacement.

## Local dev setup

See [`docs/setup.md`](docs/setup.md) for how to run the database, backend, and frontend, and how to run each project's tests/lint/format commands.

## Before opening a PR

- [ ] Tests added/updated
- [ ] Linter/formatter passed (`ruff` for backend, `oxlint` + `prettier` for frontend)
- [ ] Security scan run
- [ ] Public API changes documented
- [ ] Release notes / changelog entry if needed
- [ ] Detailed docs written in `docs/` for any feature implemented or modified
- [ ] Commit messages follow Conventional Commits and do not include the agent's name/identity

## Commits and branches

- Conventional Commits: `type(scope): subject`.
- Branches: `feature/<short-desc>`, `fix/<short-desc>`, `chore/<short-desc>`.
- Small, focused, atomic commits — one logical change each.
