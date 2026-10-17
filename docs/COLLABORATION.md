# Two-person workflow

## Daily use

1. Read AGENTS.md, project context, master log, and the relevant personal handoff.
2. Use your own clone on your computer. Fetch origin, inspect status, and start a focused task branch from origin/main. For simultaneous sessions on one machine, use separate worktrees and branches.
3. Claim the task in your personal log and publish the branch/draft PR. List files and shared interfaces, success criteria, and dependencies. Agree overlaps with the teammate; a claim is advisory, not a lock.
4. Implement and verify a small change. Give each local service instance its own ports, temporary files, and test graph/tenant. Never share a writable demo database accidentally.
5. Update your detailed task and append a brief master milestone. Review explicit staged paths, commit with task ID, push, and request the other person's review.
6. Integrate current main and rerun affected checks before merging. Hand off blockers and next steps explicitly.

Example PowerShell commands, run from your own clean checkout; replace the task name:

```powershell
git fetch origin
git switch -c codex/saqlain/memory-contract origin/main
# Mahavir uses codex/mahavir/<task> in his own clone.
# If adding a second simultaneous session on the same computer:
git worktree add -b codex/saqlain/logic-tests ../mempops-logic-tests origin/main
```

Do not run these examples blindly if branches/paths already exist. A worktree is optional when each person already has a separate clone. Never share one checkout between agents.

## Reviews and shared contracts

Agree assertion identifiers, formula encoding, query results, revision handling, and evidence fields before parallel implementation. A proposed change to a shared contract should include its consumer impact. One author implements; the other checks logic-sensitive changes and migrations. Reuse a small deterministic demo fixture for integration.

Use a PR per task. Squash merging is a reasonable default; no merge policy is configured by this file. Recommended GitHub settings when the maintainers configure CI: require PR review, passing relevant checks, and prevent force pushes to main. Do not require nonexistent checks. During an explicitly authorized urgent direct push, record the exception and validation.

## Logs

MASTER.md is a concise human index, not a synchronized task scheduler. saqlain.md and mahavir.md hold detailed task records, not hidden chain-of-thought. Each milestone links its task heading. Keep entries about meaningful work and failures. Do not log private prompts, raw conversations, credentials, or private infrastructure addresses.

Concurrent master-log conflicts: preserve both task entries, order them by timestamp, and check links after resolution. If log contention becomes frequent, propose generated summaries from per-person entries; do not add automation before it is needed.

Task template for personal logs:

```markdown
## S-YYYYMMDD-NN
- Updated: YYYY-MM-DDTHH:mm:ss+05:30
- Human / agent: Saqlain / actual agent name
- Status: in-progress
- Branch / scope: ...
- Objective and success criteria: ...
- Actions and decisions: ...
- Validation: exact commands and observed results; skipped checks and why
- Outcome / blockers: ...
- Handoff: remaining work, affected interfaces, reproduction steps
- PR / commit reference: task ID in commit message; add PR link when available
```

Use M-prefixed IDs in Mahavir's log. Correct past mistakes with explicit notes. Do not mark tasks completed until required work and verification are done; specify push or merge status separately.

## Lightweight safeguards

Keep task-specific plans in logs or PRs, durable decisions in docs, and broadly applicable instructions in AGENTS.md. Keep one lockfile per selected package manager and avoid unrelated dependency upgrades. Before submission, both humans should understand the demo, limits of its proof claims, local startup, and evidence of passing scenarios. Add CI once runnable code exists; these initial Markdown rules are guidance, not automated enforcement.
