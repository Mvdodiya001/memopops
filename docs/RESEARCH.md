# Collaboration research

Researched 2026-10-17. These are selected relevant sources, not a claim of exhaustive coverage or a popularity ranking. Team rules are our synthesis. Community anecdotes are not technical specifications.

## Primary technical guidance

- [Claude Code best practices](https://code.claude.com/docs/en/best-practices): keep persistent instructions concise and give agents concrete ways to verify outcomes. Applied here through a short entry point, linked context, and recorded verification. Avoid copying tool-specific commands into a different agent's workflow.
- [Git worktree documentation](https://git-scm.com/docs/git-worktree): separate working trees allow different branches to be checked out within one repository. Applied here as optional same-machine isolation, with separate clones for different people. Worktrees do not eliminate conflicts when branches edit the same files.

## X / Twitter practitioner posts

- [Boris Cherny: team workflow tips](https://x.com/bcherny/status/2017742741636321619).
- [Boris Cherny: worktree support announcement](https://x.com/bcherny/status/2025007393290272904).

Direct X retrieval failed during this research. Indexed [thread mirror](https://twstalker.com/bcherny/status/2017742741636321619) and [announcement mirror](https://ngntipkolamrenang.twstalker.com/bcherny/status/2025007393290272904) describe independent worktrees/checkouts for parallel sessions. These provide practitioner context only; the Git documentation above independently supports the isolation rule. No claim that these were fully read on X, and no additional technical policy rests solely on a mirror.

## Reddit experience

- [Running multiple Claude Code sessions on the same repo keeps breaking things](https://www.reddit.com/r/ClaudeAI/comments/1sljbks/running_multiple_claude_code_sessions_on_the_same/): the discussion reports agents interfering in one checkout and recommends separate worktrees and a deliberate starting revision. We adopt checkout isolation, explicit origin/main as a branch base after fetch, and publication of work claims. We do not adopt a blanket requirement to push unfinished work to main.

## Project research and limits

- [Graph Hacks official page](https://www.wemakedevs.org/hackathons/falkordb) and [schedule](https://www.wemakedevs.org/hackathons/falkordb/schedule): confirm Track 02 focus, central FalkorDB use, event window and submission deadline. See PROJECT_CONTEXT.md for the applied constraints.
- The supplied DOCX explains the project's evolution toward proof-carrying memory. Prior-work claims about Kumiho, Atlas, MemTX and other systems remain historical notes, not freshly verified findings. No novelty claim is made in this bootstrap.

## Decisions from the synthesis

Separate checkouts, named task branches, visible task claims, agreed interfaces, small PRs, review of correctness-sensitive work, observed test evidence, and precise handoffs reduce coordination risk. A three-file log is the team's chosen convention, not an industry standard. Its shared master file can conflict, so entries use stable IDs and an explicit keep-both resolution policy. Avoid long instruction files, transcript dumps, premature automation, and claims that prose rules enforce permissions or CI.
