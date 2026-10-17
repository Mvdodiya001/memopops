# memopops

Proof-carrying shared memory for AI agents, targeting Graph Hacks Track 02. Working concept: persistent propositions, evidence, revisions, and proof dependencies in FalkorDB, with a separate propositional-logic checker.

Status: detailed implementation plan and collaboration documentation. No application, dependencies, test runner, deployment, or CI exists yet. The plan proposes a stack and task split; G0 must validate dependencies and contracts.

## Start here

- [Detailed implementation plan and parallel work](docs/IMPLEMENTATION_PLAN.md)
- [Agent and contributor rules](AGENTS.md)
- [Project context and MVP boundaries](docs/PROJECT_CONTEXT.md)
- [Two-person workflow](docs/COLLABORATION.md)
- [Research and source notes](docs/RESEARCH.md)
- [Master activity log](logs/MASTER.md)
- Detailed logs: [Saqlain](logs/saqlain.md) and [Mahavir](logs/mahavir.md)

Each person should use their own clone and task branch. Do not run concurrent agents in the same working directory. Read AGENTS.md before making changes.
