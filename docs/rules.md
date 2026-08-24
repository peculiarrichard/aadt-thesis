Naming & Structure
R1.1: Use clear, intent-revealing names: nouns for types/modules, verbs for functions, adjectives for flags.
R1.2: Prefer short, consistent names over clever ones. Abbreviations only when universally understood.
R1.3: One responsibility per module/class/function (single responsibility). Keep functions short where reasonable.
Formatting & Style
R2.1: Use and enforce a single code formatter for the stack (e.g., Prettier, gofmt, rustfmt). Run it in CI.
R2.2: Use a linter with team rules enabled and treat new lint failures as build breaks.
R2.3: Follow a consistent brace/indent/line-length style (100–120 chars max recommended).
Commits & Branches
R3.1: Use Conventional Commits format (type(scope): subject) for automated changelogs.
R3.2: Branch naming: feature/<ticket>-short-desc, fix/<ticket>-short-desc, chore/<desc>.
R3.3: Keep commits focused and atomic; prefer many small commits that do one thing.
R3.4: Never include the agent’s name or identity in commit messages. Do not insert strings like the agent username, “copilot”, “assistant”, “AI”, or “bot” into commit messages. Use neutral/automated markers only if needed (e.g., chore(deps): bump x), and never attribute the commit to the agent in the message body.
Pull Requests & Code Review
R4.1: Keep PRs small and focused (ideally < 400 LOC). Describe intent, design decisions, and migration notes in the PR body.
R4.2: Include a short changelog-friendly summary and testing instructions.
R4.3: Require at least one approved reviewer (two for high-risk changes). Request domain-specific reviewers for relevant areas.
R4.4: Review criteria: correctness, tests, security, readability, backwards compatibility, performance.
Testing
R5.1: Every public function/endpoint must have unit tests. Critical paths get integration/e2e tests.
R5.2: Aim for meaningful coverage—cover behavior and edge cases.
R5.3: Run tests in CI on every PR and block merges on failing tests.
CI / Automation
R6.1: CI pipeline must run formatting, linting, unit tests, and security scans.
R6.2: Fail fast: make lint/format errors and test failures block merges.
R6.3: Automate dependency updates (Dependabot/renovate) and run tests on update PRs.
Error Handling & Logging
R7.1: Do not swallow errors: handle, wrap with context, or return them. Prefer explicit error types where helpful.
R7.2: Log at appropriate levels and keep logs structured (JSON) for production services. Avoid logging secrets.
Security & Secrets
R8.1: Never commit secrets; enforce secret scanning. Use environment variables / secret managers.
R8.2: Validate inputs at boundaries and apply the principle of least privilege. Keep dependencies up-to-date and monitor CVEs.
Dependencies & Releases
R9.1: Track transitive dependencies and bump regularly. Pin versions for reproducible builds where applicable.
R9.2: Use semantic versioning for libraries. Document breaking changes in changelogs.
Performance & Resource Use
R10.1: Optimize based on measurement (profiling, metrics), not premature optimization.
R10.2: Add benchmarks for performance-sensitive code and test for regressions in CI as needed.
Documentation (new / agent-specific)
R11.1: All major comments, architecture notes, design docs, API references, migration guides, and long-form explanations must live under a docs/ directory at repo root (path exactly docs/). Minor inline comments remain in code where appropriate, but anything substantial must be in docs/.
R11.2: The agent must write detailed documentation for any feature it implements or modifies: purpose, usage examples, public API shape, configuration, migration/upgrade notes, testing instructions, and any security/privilege concerns.
R11.3: The docs/ folder will be git-ignored per project policy. The agent must ensure docs/ is listed in .gitignore (or the repository’s ignore mechanism) when operating in a repo. If docs are required in source control, follow alternate project rules (create a tracked docs repo or follow the project's specified docs publication workflow).
R11.4: When the docs folder is git-ignored, the agent must still provide a machine-readable, commit-able summary (e.g., a short tracked changelog entry or a PR body section) describing the docs location and contents, and optionally push tracked docs to the designated docs repo if one exists.
Observability & Health
R12.1: Emit metrics, health endpoints, and traces for services. Include alerts for key failures.
Accessibility & Internationalization
R13.1: Consider accessibility in UI work and design strings for localization when needed.
Backward Compatibility & Migrations
R14.1: Deprecate public APIs before removing them. Provide migration guides and feature flags for risky rollouts. Include upgrade notes in releases.
Review & Onboarding
R15.1: Add a CONTRIBUTING.md listing these rules and the local dev/CI checklist.
R15.2: Run periodic cleanup sprints to reduce technical debt.
Minimal PR checklist (update for agent)

 Tests added/updated
 Linter/formatter passed
 Security scan run
 Public API changes documented
 Release notes / changelog entry if needed
 Detailed docs written in docs/ (if docs/ is ignored, include a tracked summary and point to docs location)
 .gitignore updated to include docs/ when project policy requires it
 Commit messages follow Conventional Commits and do NOT include the agent’s name/identity