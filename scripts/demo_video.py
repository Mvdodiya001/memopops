"""Run the narrated memopops video demo against a published API."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from agents.client import MemoryClient
from agents.demo_memory import ASSERTION_INPUTS, WORKSPACE_ID
from agents.gemini_tools import GeminiFunctionCallingModel
from agents.model import ScriptedActions
from agents.operator import (
    inconsistent_failure_add,
    replace_passing_tests,
    submit_revision,
)
from agents.scripts import RELEASE_QUERY, ScriptedFailureWriter, ScriptedReleaseReader
from agents.session import AgentSession
from agents.transport import UrlTransport
from memopops.store import FalkorSnapshotStore, graph_name_for_workspace
from scripts.reset_demo_workspace import reset_demo_workspace
from scripts.seed_demo import load_local_env


READER_GOAL = "Decide whether release_ready holds at the current head and record the matching decision."
DOCS_GOAL = (
    "Decide whether docs_signed holds at the current head using proof_mode solver because "
    "an UNKNOWN result has no decisive certificate, then record the matching decision."
)
WRITER_GOAL = (
    "You observed that the integration tests for release demo-42 failed. Evidence: "
    'uri fixture://demo-42/writer-tests-failed, excerpt "Synthetic writer report: '
    'integration tests failed.", observed_at 2026-10-17T12:00:00Z. Propose that '
    "tests_pass is false."
)

EXPECTED_BASELINE_ASSERTIONS = {
    assertion_id: formula for assertion_id, formula, _uri, _excerpt in ASSERTION_INPUTS
}


def graph_queries(revision_id: str) -> tuple[str, str]:
    escaped_revision_id = revision_id.replace("\\", "\\\\").replace("'", "\\'")
    return (
        f"""MATCH (q:QueryResult {{revision_id: '{escaped_revision_id}'}})-[:USES_PREMISE]->(a:Assertion)-[:ENCODES]->(f:Formula)
OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(e:Evidence)
RETURN q.id, a.id, f.canonical_json, e.uri
ORDER BY a.id""",
        """MATCH (r:Revision)-[:INCLUDES]->(a:Assertion)
RETURN r.id, r.sequence, collect(a.id) AS members
ORDER BY r.sequence""",
    )


def pretty_formula(formula: dict[str, Any]) -> str:
    op = formula.get("op")
    if op == "atom":
        return str(formula.get("id", "?"))
    if op == "not":
        return f"NOT {pretty_formula(formula.get('arg', {}))}"
    args = formula.get("args", [])
    if not isinstance(args, list):
        return str(formula)
    rendered = [pretty_formula(item) for item in args if isinstance(item, dict)]
    joiner = {"and": " AND ", "or": " OR ", "implies": " -> ", "iff": " <-> "}.get(
        str(op), f" {str(op).upper()} "
    )
    return f"({joiner.join(rendered)})"


def _unknown_reader() -> ScriptedActions:
    def query(observation: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "tool",
            "name": "query_conclusion",
            "arguments": {
                "revision_id": observation["head_revision_id"],
                "query": {"op": "atom", "id": "docs_signed"},
                "proof_mode": "solver",
            },
        }

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "tool",
            "name": "record_decision",
            "arguments": {
                "expected_revision_id": observation["revision_id"],
                "query_id": observation["query_id"],
                "choice": "abstain",
            },
        }

    return ScriptedActions(
        [
            {"type": "tool", "name": "inspect_memory", "arguments": {}},
            query,
            decide,
            {"type": "stop"},
        ]
    )


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _safe_error(exc: Exception) -> str:
    detail = str(exc)
    secret = os.getenv("MEMOPOPS_MODEL_API_KEY", "")
    if secret:
        detail = detail.replace(secret, "[REDACTED]")
    return detail[:300]


class DemoRunner:
    """Stateful scene runner usable with URL or in-process test clients."""

    def __init__(
        self,
        *,
        reader: MemoryClient,
        writer: MemoryClient,
        operator: MemoryClient,
        output: Path,
        model_mode: str,
        take: str,
        pause: bool = False,
        model_timeout: float | None = None,
        store_factory: Callable[[], FalkorSnapshotStore] | None = None,
    ):
        self.reader = reader
        self.writer = writer
        self.operator = operator
        self.output = Path(output)
        self.model_mode = model_mode
        self.take = take
        self.pause = pause
        self.model_timeout = model_timeout
        self.store_factory = store_factory
        self.output.mkdir(parents=True, exist_ok=True)
        self.summary: dict[str, Any] = {
            "workspace_id": WORKSPACE_ID,
            "take": take,
            "requested_model_mode": model_mode,
            "fallback_used": False,
            "scenes": {},
        }
        self.first_decision: dict[str, Any] | None = None
        self.first_query_id: str | None = None
        self.baseline_revision_id: str | None = None
        self.new_revision_id: str | None = None
        self.gemini_transcript: list[dict[str, Any]] = []

    def _header(self, number: int, title: str) -> None:
        print(f"\n== Scene {number}: {title} ==")

    def _wait(self) -> None:
        if self.pause:
            input("\nPress Enter for the next scene...")

    def _discover_baseline(self) -> tuple[str, dict[str, Any]]:
        workspace_status, workspace = self.reader.workspace()
        if workspace_status != 200:
            raise RuntimeError(f"workspace read failed with HTTP {workspace_status}")
        head = workspace.get("head_revision_id")
        if not isinstance(head, str) or not head:
            raise RuntimeError("workspace has no current head revision")
        memory_status, memory = self.reader.memory(head)
        if memory_status != 200:
            raise RuntimeError(f"memory read failed with HTTP {memory_status}")
        actual = {
            item.get("id"): item.get("formula")
            for item in memory.get("assertions", [])
            if isinstance(item, dict)
        }
        missing_or_changed = sorted(
            assertion_id
            for assertion_id, formula in EXPECTED_BASELINE_ASSERTIONS.items()
            if actual.get(assertion_id) != formula
        )
        unexpected = sorted(set(actual) - set(EXPECTED_BASELINE_ASSERTIONS))
        if missing_or_changed or unexpected:
            raise RuntimeError(
                f"workspace head {head!r} is not the canonical demo baseline "
                f"(missing or changed: {missing_or_changed}; unexpected: {unexpected}); "
                "rerun with --reset"
            )
        self.baseline_revision_id = head
        self.summary["baseline_revision_id"] = head
        return head, memory

    def _baseline(self) -> str:
        if self.baseline_revision_id is None:
            self._discover_baseline()
        assert self.baseline_revision_id is not None
        return self.baseline_revision_id

    def _print_session(
        self,
        result: dict[str, Any],
        *,
        mode: str,
        model: Any,
        event_start: int = 0,
    ) -> None:
        label = (
            "Live model: Gemini Flash, function calling"
            if mode == "live_model"
            else "Scripted replay"
        )
        print(f"[{label}]")
        calls = [
            item
            for item in getattr(model, "transcript", [])
            if item.get("type") == "function_call" and item.get("name") != "finish"
        ]
        events = result.get("events", [])[event_start:]
        for index, event in enumerate(events):
            call = calls[index] if index < len(calls) else {}
            rationale = call.get("rationale") or "Follow the bounded demo procedure."
            print(f"Agent says: {rationale}")
            print(
                "Tool call:",
                _json(
                    {
                        "name": call.get("name") or event.get("tool"),
                        "arguments": call.get("arguments", {}),
                    }
                ),
            )
            print("Service answered:", _json(event))

    def _fresh_session(
        self,
        *,
        client: MemoryClient,
        role: str,
        goal: str,
        journal: Path,
        scripted_model: Any,
    ) -> tuple[AgentSession, Any, str]:
        if self.model_mode == "live":
            live = GeminiFunctionCallingModel.from_env(
                role,
                goal,
                workspace_id=WORKSPACE_ID,
                request_timeout=self.model_timeout,
                status=self._model_status,
            )
            if live is not None:
                return (
                    AgentSession(
                        client=client,
                        model=live,
                        role=role,
                        workspace_id=WORKSPACE_ID,
                        mode="live_model",
                        journal_path=journal,
                    ),
                    live,
                    "live_model",
                )
            print("Live model unavailable: no configured API key. Falling back to scripted replay.")
            self.summary["fallback_used"] = True
        return (
            AgentSession(
                client=client,
                model=scripted_model,
                role=role,
                workspace_id=WORKSPACE_ID,
                mode="scripted_replay",
                journal_path=journal,
            ),
            scripted_model,
            "scripted_replay",
        )

    @staticmethod
    def _model_status(message: str) -> None:
        print(f"[Live model] {message}", flush=True)

    def _run_fresh(
        self,
        *,
        client: MemoryClient,
        role: str,
        goal: str,
        journal: Path,
        scripted_model: Any,
    ) -> tuple[AgentSession, dict[str, Any]]:
        session, model, mode = self._fresh_session(
            client=client,
            role=role,
            goal=goal,
            journal=journal,
            scripted_model=scripted_model,
        )
        try:
            result = session.run()
        except Exception as exc:
            if mode != "live_model":
                raise
            print(
                f"Live model unavailable: {exc.__class__.__name__}: {_safe_error(exc)}. "
                "Falling back to scripted replay."
            )
            self.summary["fallback_used"] = True
            session = AgentSession(
                client=client,
                model=scripted_model,
                role=role,
                workspace_id=WORKSPACE_ID,
                mode="scripted_replay",
                journal_path=journal,
            )
            model = scripted_model
            mode = "scripted_replay"
            result = session.run()
        self._print_session(result, mode=mode, model=model)
        self.gemini_transcript.extend(getattr(model, "transcript", []))
        return session, result

    def scene_preflight(self) -> dict[str, Any]:
        self._header(0, "Preflight")
        health_status, health = self.reader.transport.request(
            "GET", "/api/v1/health/ready", None, self.reader.token
        )
        if health_status != 200:
            raise RuntimeError(f"preflight failed: health={health_status}")
        head, _memory = self._discover_baseline()
        graph_name = graph_name_for_workspace(WORKSPACE_ID)
        result = {
            "health": health.get("status"),
            "head_revision_id": head,
            "model_mode": self.model_mode,
            "model_key_present": bool(os.getenv("MEMOPOPS_MODEL_API_KEY")),
            "graph_name": graph_name,
        }
        print(_json(result))
        return result

    def scene_memory(self) -> dict[str, Any]:
        baseline = self._baseline()
        self._header(1, f"Accepted memory at {baseline}")
        status, memory = self.reader.memory(baseline)
        if status != 200:
            raise RuntimeError(f"memory read failed with HTTP {status}")
        for assertion in memory.get("assertions", []):
            evidence = assertion.get("evidence", [{}])[0]
            print(
                f"{assertion.get('id')}: {pretty_formula(assertion.get('formula', {}))}\n"
                f"  Evidence: {evidence.get('excerpt')} ({evidence.get('uri')})"
            )
        print(f"Knowledge hash: {str(memory.get('knowledge_hash', ''))[:12]}...")
        return {
            "revision_id": memory.get("revision_id"),
            "assertion_count": len(memory.get("assertions", [])),
            "knowledge_hash": memory.get("knowledge_hash"),
        }

    def scene_reader(self) -> dict[str, Any]:
        baseline = self._baseline()
        self._header(2, f"Reader decides at {baseline}")
        session, result = self._run_fresh(
            client=self.reader,
            role="reader",
            goal=READER_GOAL,
            journal=self.output / "reader.json",
            scripted_model=ScriptedReleaseReader(),
        )
        self.first_decision = session.current_decision()
        if not self.first_decision:
            raise RuntimeError("reader did not record a decision")
        self.first_query_id = str(self.first_decision["query_id"])
        return {
            "decision": self.first_decision,
            "executed_steps": result["executed_steps"],
            "mode": result["mode"],
        }

    def scene_uncertain(self) -> dict[str, Any]:
        self._header(3, "Unknown stays unknown")
        self._baseline()
        session, result = self._run_fresh(
            client=self.reader,
            role="reader",
            goal=DOCS_GOAL,
            journal=self.output / "reader-docs.json",
            scripted_model=_unknown_reader(),
        )
        decision = session.current_decision()
        return {
            "decision": decision,
            "executed_steps": result["executed_steps"],
            "mode": result["mode"],
        }

    def scene_writer(self) -> dict[str, Any]:
        self._header(4, "Writer proposal and quarantine")
        baseline = self._baseline()
        _session, writer_result = self._run_fresh(
            client=self.writer,
            role="writer",
            goal=WRITER_GOAL,
            journal=self.output / "writer.json",
            scripted_model=ScriptedFailureWriter(),
        )
        print("Writer credentials cannot activate memory. Operator submits the observation for validation.")
        status, quarantined = submit_revision(
            self.operator,
            expected_revision=baseline,
            idempotency_key=f"video-quarantine-{self.take}",
            reason="Review the writer's synthetic failed-tests observation.",
            mutations=inconsistent_failure_add(),
        )
        workspace_status, workspace = self.reader.workspace()
        proposal_status, proposals = self.reader.proposals()
        print("Operator validation:", _json({"status_code": status, **quarantined}))
        print("Head after validation:", workspace.get("head_revision_id"))
        return {
            "writer_events": writer_result.get("events", []),
            "quarantine_status": status,
            "quarantine": quarantined,
            "head_revision_id": workspace.get("head_revision_id"),
            "proposal_status": proposal_status,
            "proposal_count": len(proposals.get("proposals", [])),
            "workspace_status": workspace_status,
        }

    def scene_correction(self) -> dict[str, Any]:
        self._header(5, "Operator correction and impact")
        baseline = self._baseline()
        status, committed = submit_revision(
            self.operator,
            expected_revision=baseline,
            idempotency_key=f"video-correction-{self.take}",
            reason="Operator replaces the passing test report after the reader decision.",
            mutations=replace_passing_tests(),
        )
        if status != 201 or committed.get("status") != "COMMITTED":
            raise RuntimeError(f"correction failed: HTTP {status} {_json(committed)}")
        self.new_revision_id = str(committed["revision_id"])
        impact_status, impact = self.reader.impact(self.new_revision_id)
        print("Correction:", _json({"status_code": status, **committed}))
        print("FalkorDB dependency impact:", _json(impact))
        return {
            "status": status,
            "revision_id": self.new_revision_id,
            "impact_status": impact_status,
            "impact": impact,
        }

    def scene_resume(self) -> dict[str, Any]:
        self._header(6, "Resumed reader rechecks the new head")
        if not self.first_decision:
            raise RuntimeError("reader scene must run before resume")
        if self.model_mode == "live":
            model: Any = GeminiFunctionCallingModel.from_env(
                "reader",
                READER_GOAL,
                workspace_id=WORKSPACE_ID,
                prior_decision=self.first_decision,
                request_timeout=self.model_timeout,
                status=self._model_status,
            )
        else:
            model = None
        mode = "live_model" if model is not None else "scripted_replay"
        if model is None:
            model = ScriptedReleaseReader(prior_decision=self.first_decision)
            if self.model_mode == "live":
                self.summary["fallback_used"] = True
        session = AgentSession.resume(
            self.output / "reader.json",
            client=self.reader,
            model=model,
            role="reader",
            mode=mode,
        )
        event_start = len(session.events)
        try:
            result = session.run()
        except Exception as exc:
            if mode != "live_model":
                raise
            print(
                f"Live model unavailable: {exc.__class__.__name__}: {_safe_error(exc)}. "
                "Falling back to scripted replay."
            )
            self.summary["fallback_used"] = True
            model = ScriptedReleaseReader(prior_decision=self.first_decision)
            mode = "scripted_replay"
            session = AgentSession.resume(
                self.output / "reader.json",
                client=self.reader,
                model=model,
                role="reader",
                mode=mode,
            )
            event_start = len(session.events)
            result = session.run()
        self._print_session(result, mode=mode, model=model, event_start=event_start)
        self.gemini_transcript.extend(getattr(model, "transcript", []))
        current = session.current_decision()
        return {
            "decision": current,
            "decisions": result["decisions"],
            "executed_steps": result["executed_steps"],
            "mode": mode,
        }

    def scene_verify(self) -> dict[str, Any]:
        self._header(7, "Independent certificate verification")
        if not self.first_query_id:
            raise RuntimeError("reader query must run before certificate verification")
        status, bundle = self.reader.certificate(self.first_query_id)
        if status != 200:
            raise RuntimeError(f"certificate export failed with HTTP {status}")
        baseline = self._baseline()
        safe_revision = "".join(
            character if character.isalnum() or character in "._-" else "_"
            for character in baseline
        )
        valid_path = self.output / f"certificate-{safe_revision}.json"
        valid_path.write_text(_json(bundle) + "\n", encoding="utf-8")
        valid = subprocess.run(
            [sys.executable, "-m", "proofcheck", str(valid_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        print(valid.stdout.strip())
        print(f"proofcheck valid exit: {valid.returncode}")

        tampered = copy.deepcopy(bundle)
        certificate = tampered.get("bundle", tampered)
        clauses = certificate.get("clauses") if isinstance(certificate, dict) else None
        if not isinstance(clauses, list):
            raise RuntimeError("certificate has no clauses to tamper")
        resolution = next(
            (
                clause
                for clause in reversed(clauses)
                if isinstance(clause, dict) and clause.get("origin") == "resolution"
            ),
            None,
        )
        if resolution is None:
            raise RuntimeError("certificate has no resolution step to tamper")
        resolution["pivot"] = int(resolution.get("pivot", 0)) + 10_000
        tampered_path = self.output / "certificate-tampered.json"
        tampered_path.write_text(_json(tampered) + "\n", encoding="utf-8")
        invalid = subprocess.run(
            [sys.executable, "-m", "proofcheck", str(tampered_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        print(invalid.stdout.strip())
        print(f"proofcheck tampered exit: {invalid.returncode}")
        return {
            "query_id": self.first_query_id,
            "valid_exit": valid.returncode,
            "tampered_exit": invalid.returncode,
        }

    def scene_graph(self) -> dict[str, Any]:
        self._header(8, "FalkorDB dependency graph")
        queries = graph_queries(self._baseline())
        (self.output / "graph-queries.cypher").write_text(
            "\n\n".join(queries) + "\n",
            encoding="utf-8",
        )
        if self.store_factory is None:
            print("Graph query skipped: this run has no FalkorDB store.")
            return {"skipped": True}
        store = self.store_factory()
        rows: list[list[Any]] = []
        try:
            graph = store._get_client().select_graph(graph_name_for_workspace(WORKSPACE_ID))
            for query in queries:
                print("\nCypher:\n" + query)
                result = graph.query(query).result_set
                rows.append(result)
                print("Rows:\n" + _json(result))
        finally:
            store.close()
        return {"skipped": False, "row_counts": [len(item) for item in rows]}

    def run(self, scenes: list[str]) -> dict[str, Any]:
        available = {
            "preflight": self.scene_preflight,
            "memory": self.scene_memory,
            "reader": self.scene_reader,
            "uncertain": self.scene_uncertain,
            "writer": self.scene_writer,
            "correction": self.scene_correction,
            "resume": self.scene_resume,
            "verify": self.scene_verify,
            "graph": self.scene_graph,
        }
        for name in scenes:
            if name not in available:
                raise ValueError(f"unknown scene: {name}")
            self.summary["scenes"][name] = available[name]()
            self._write_artifacts()
            self._wait()
        return self.summary

    def _write_artifacts(self) -> None:
        (self.output / "summary.json").write_text(
            _json(self.summary) + "\n",
            encoding="utf-8",
        )
        (self.output / "gemini-transcript.json").write_text(
            _json(self.gemini_transcript) + "\n",
            encoding="utf-8",
        )


def _tokens_from_env() -> dict[str, dict[str, str]]:
    raw = os.getenv("MEMOPOPS_AUTH_TOKENS", "{}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise SystemExit("MEMOPOPS_AUTH_TOKENS must be a JSON object")
    return parsed


def _token(tokens: dict[str, dict[str, str]], name: str) -> str:
    entry = tokens.get(name)
    if not isinstance(entry, dict) or entry.get("workspace_id") != WORKSPACE_ID:
        raise SystemExit(f"missing workspace_demo token {name!r}")
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description="Narrated memopops video demo.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8001")
    parser.add_argument("--model", choices=["live", "scripted"], default="scripted")
    parser.add_argument(
        "--model-timeout",
        type=float,
        default=None,
        help="Seconds per live Gemini request (default 10; range 1-120).",
    )
    parser.add_argument("--pause", action="store_true")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and reseed only workspace_demo before this run.",
    )
    parser.add_argument("--take", default="1")
    parser.add_argument("--output", type=Path, default=Path(".artifacts/video-demo"))
    parser.add_argument("--scenes", default="all")
    parser.add_argument("--reader-token-name", default="local-reader-token")
    parser.add_argument("--writer-token-name", default="local-writer-token")
    parser.add_argument("--operator-token-name", default="local-operator-token")
    args = parser.parse_args()
    if args.model_timeout is not None and not 1 <= args.model_timeout <= 120:
        parser.error("--model-timeout must be between 1 and 120 seconds")

    load_local_env()
    if args.reset:
        reset_demo_workspace(confirmed=True)
    tokens = _tokens_from_env()
    transport = UrlTransport(args.api_base)
    reader = MemoryClient(transport, _token(tokens, args.reader_token_name), WORKSPACE_ID)
    writer = MemoryClient(transport, _token(tokens, args.writer_token_name), WORKSPACE_ID)
    operator = MemoryClient(transport, _token(tokens, args.operator_token_name), WORKSPACE_ID)
    scenes = (
        list(
            (
                "preflight",
                "memory",
                "reader",
                "uncertain",
                "writer",
                "correction",
                "resume",
                "verify",
                "graph",
            )
        )
        if args.scenes == "all"
        else [item.strip() for item in args.scenes.split(",") if item.strip()]
    )
    output = args.output / f"take-{args.take}"
    runner = DemoRunner(
        reader=reader,
        writer=writer,
        operator=operator,
        output=output,
        model_mode=args.model,
        take=args.take,
        pause=args.pause,
        model_timeout=args.model_timeout,
        store_factory=FalkorSnapshotStore.from_env,
    )
    runner.run(scenes)
    print(f"\nArtifacts: {output}")


if __name__ == "__main__":
    main()
