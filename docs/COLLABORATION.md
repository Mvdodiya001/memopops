# Two-person workflow

## Pull request policy

Publish each completed, validated milestone from a focused task branch through a pull request. Do not push implementation commits directly to main. Both agents must read this policy from current origin/main before starting. Keep PRs small, include exact validation results, and merge only when the user or repository workflow authorizes it.

## Daily use

1. Read AGENTS.md, project context, implementation plan, master log, and the relevant personal handoff.
2. Use your own clone or worktree. Fetch origin, inspect status, and start a focused personal task branch from origin/main. Never run concurrent writers in one checkout.
3. Record task ID, file/interface scope, success criteria and dependencies in your personal log. Publish a small log-only commit or task branch when needed to make the claim visible. A claim is advisory, not a lock; agree overlapping interface changes.
4. Implement a focused milestone. Use separate ports, temporary paths and test graphs for concurrent environments. Review your diff and run relevant checks.
5. Update your personal/master logs, stage only your own explicit paths, and commit with task ID.
6. Fetch origin and merge or rebase origin/main into your task branch. Resolve conflicts by understanding both changes. Rerun affected checks.
7. Push only your task branch and open or update its pull request with a concise description and validation results. Never force-push, reset the teammate's commits, or discard one side of a conflict.
8. Record the PR link, review status, and next handoff. Do not merge without authorization. Exact HEAD equality is unnecessary if the teammate pushed afterward.

## Command pattern

Run from your own checkout. Replace the task name and paths. Check each command succeeded before continuing.

```powershell
git fetch origin
git switch -c codex/saqlain/task-name origin/main
# Implement, test, review, and update logs.
git add -- path/to/your/file logs/saqlain.md logs/MASTER.md
git commit -m 'feat: describe completed milestone (task ID)'
git fetch origin
git merge --no-edit origin/main
# Resolve any conflicts and rerun affected checks BEFORE the push.
git push -u origin HEAD
# Open a pull request from this task branch into main; do not merge without authorization.
```

Mahavir uses codex/mahavir/task-name and logs/mahavir.md. Commands are a pattern, not a script to run with placeholder paths. Worktrees are optional on different computers. Do not publish an unfinished merge or failed checks merely to complete the sequence. If semantic conflicts need the other person's decision, document the precise overlap and continue independent work.

## Contracts and quality

Agree assertion identifiers, formula encoding, result enums, revisions and evidence fields before parallel implementation. Follow the plan's one-owner-per-shared-file assignments. Self-review and required tests are mandatory. Use the PR for peer review and CI results before integration.

Keep main runnable once code exists. Respect repository protections. Revert commits are the normal way to undo merged changes.

## Logs

MASTER.md is a concise milestone index. saqlain.md and mahavir.md contain task-level explanations. Each person edits their own log; never invent the other's work. Preserve both master entries during an append conflict, ordered by timestamp, and validate their links.

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
- Publication: commit/task reference; verified inclusion in origin/main
```

Use M-prefixed IDs for Mahavir. Do not mark a task completed if required implementation/checks remain. Code completion and successful push are separate observed facts. Correct historical errors explicitly. Never log credentials, private prompts or hidden reasoning.
