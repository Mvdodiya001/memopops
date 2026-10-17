# Two-person workflow

## Direct publication policy

Saqlain and Mahavir have standing authorization to commit and push completed, validated work directly to main. No pull request or additional permission request is required. Both agents must read this policy from current origin/main before starting. Task branches/worktrees remain useful for isolation; they are not a PR requirement.

## Daily use

1. Read AGENTS.md, project context, implementation plan, master log, and the relevant personal handoff.
2. Use your own clone or worktree. Fetch origin, inspect status, and start a focused personal task branch from origin/main. Never run concurrent writers in one checkout.
3. Record task ID, file/interface scope, success criteria and dependencies in your personal log. Publish a small log-only commit or task branch when needed to make the claim visible. A claim is advisory, not a lock; agree overlapping interface changes.
4. Implement a focused milestone. Use separate ports, temporary paths and test graphs for concurrent environments. Review your diff and run relevant checks.
5. Update your personal/master logs, stage only your own explicit paths, and commit with task ID.
6. Fetch origin again and merge origin/main into your current branch. Resolve conflicts by understanding both changes. Rerun affected checks on the combined result before pushing HEAD to main.
7. If the push is rejected because the other agent advanced main, repeat step 6 and retry normally. Never force-push, reset the teammate's commits, or discard one side of a conflict.
8. Fetch and verify your published commit is an ancestor of origin/main. Record the outcome and next handoff. Exact HEAD equality is unnecessary if the teammate pushed afterward.

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
git push origin HEAD:main
git fetch origin
git merge-base --is-ancestor HEAD origin/main
# Exit code 0 confirms this commit is included in remote main.
```

Mahavir uses codex/mahavir/task-name and logs/mahavir.md. Commands are a pattern, not a script to run with placeholder paths. Worktrees are optional on different computers. Do not publish an unfinished merge or failed checks merely to complete the sequence. If semantic conflicts need the other person's decision, document the precise overlap and continue independent work.

## Contracts and quality

Agree assertion identifiers, formula encoding, result enums, revisions and evidence fields before parallel implementation. Follow the plan's one-owner-per-shared-file assignments. Self-review and required tests are mandatory; peer review can happen asynchronously without a PR or publication gate. Do not wait for an unnecessary approval after the authorized task and checks are complete.

Keep main runnable once code exists. Do not introduce a required-PR protection policy. Existing repository protections still apply; report a blocked push without bypassing them. Revert commits are the normal way to undo published changes.

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
