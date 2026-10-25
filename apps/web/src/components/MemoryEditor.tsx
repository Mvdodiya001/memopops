import { useEffect, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ApiError, postRevision } from "../api/client"
import type { Formula, MutationRequest } from "../api/types"
import { parseExpression } from "../model/expression"
import { prettyFormula } from "../model/formula"

export function MemoryEditor(props: {
  workspaceId: string
  revisionId: string
  token: string
  atoms: { id: string; label: string }[]
  assertions: { id: string; formula: Formula }[]
  onCommitted: (revision: string) => void
}) {
  const cache = useQueryClient()
  const [mode, setMode] = useState<"add" | "replace" | "retract">("add")
  const [target, setTarget] = useState("")
  const [atom, setAtom] = useState(props.atoms[0]?.id ?? "")
  const [negated, setNegated] = useState(false)
  const [expression, setExpression] = useState("")
  const [reason, setReason] = useState("")
  const [uri, setUri] = useState("")
  const [excerpt, setExcerpt] = useState("")
  const [observed, setObserved] = useState("")
  const [notice, setNotice] = useState("")
  const [key, setKey] = useState(() => crypto.randomUUID())
  useEffect(
    () => setKey(crypto.randomUUID()),
    [mode, target, atom, negated, expression, reason, uri, excerpt, observed, props.revisionId],
  )
  let formula: Formula = negated
    ? { op: "not", arg: { op: "atom", id: atom } }
    : { op: "atom", id: atom }
  let parseError = ""
  if (expression.trim()) {
    try {
      formula = parseExpression(
        expression,
        props.atoms.map((a) => a.id),
      )
    } catch (error) {
      parseError = error instanceof Error ? error.message : "Invalid expression"
    }
  }
  const validTarget = props.assertions.some((item) => item.id === target)
  const mutation = useMutation({
    mutationFn: () => {
      if (parseError && mode !== "retract") throw new Error(parseError)
      const assertion = {
        client_ref: "workspace-edit",
        formula,
        evidence:
          mode === "retract"
            ? []
            : [
                {
                  uri: uri.trim(),
                  excerpt: excerpt.trim(),
                  observed_at: new Date(observed).toISOString(),
                },
              ],
      }
      // Retracting does not require new evidence or a fabricated observation timestamp.
      const mutations: MutationRequest["mutations"] =
        mode === "retract"
          ? [{ op: "retract", target_assertion_id: target }]
          : mode === "replace"
            ? [{ op: "replace", target_assertion_id: target, assertion }]
            : [{ op: "add", assertion }]
      return postRevision(
        props.workspaceId,
        {
          expected_revision: props.revisionId,
          idempotency_key: key,
          reason: reason.trim(),
          acceptance: "human_confirmed",
          mutations,
        },
        { token: props.token },
      )
    },
    onSuccess: async (response) => {
      if (response.status === 201 && response.body.revision_id) {
        setKey(crypto.randomUUID())
        setNotice("Saved as a new revision. Earlier evidence and conclusions remain in history.")
        await cache.invalidateQueries()
        props.onCommitted(response.body.revision_id)
      } else {
        setNotice(
          "This change conflicts with accepted memory and was quarantined. To correct an outdated claim, choose Replace and select that claim; do not add its opposite alongside it.",
        )
        await cache.invalidateQueries({ queryKey: ["proposals"] })
      }
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError
          ? `${error.message}${error.status === 409 ? " Refresh the workspace and review your change before retrying." : ""}`
          : error.message,
      ),
  })
  return (
    <form
      className="panel"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <h2 className="section-title">
        {mode === "add" ? "Add memory" : mode === "replace" ? "Correct memory" : "Retract memory"}
      </h2>
      <fieldset disabled={mutation.isPending}>
        <legend>Evidence-backed change</legend>
        <label className="revision-control">
          <span>Change</span>
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as typeof mode)
              setNotice("")
            }}
          >
            <option value="add">Add a fact or rule</option>
            <option value="replace">Replace an outdated claim</option>
            <option value="retract">Retract a claim</option>
          </select>
        </label>
        {mode !== "add" && (
          <label className="revision-control">
            <span>Claim to change</span>
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">Choose an accepted claim</option>
              {props.assertions.map((item) => (
                <option key={item.id} value={item.id}>
                  {prettyFormula(item.formula)} · {item.id}
                </option>
              ))}
            </select>
          </label>
        )}
        {mode !== "retract" && (
          <>
            <label className="revision-control">
              <span>Atom</span>
              <select value={atom} onChange={(e) => setAtom(e.target.value)}>
                {props.atoms.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="cluster">
              <input
                type="checkbox"
                checked={negated}
                onChange={(e) => setNegated(e.target.checked)}
              />{" "}
              Assert the negation
            </label>
            <details>
              <summary>Write a rule or compound expression</summary>
              <label className="revision-control">
                <span>Memory expression</span>
                <textarea
                  value={expression}
                  maxLength={4096}
                  onChange={(e) => setExpression(e.target.value)}
                  placeholder="(api_v2 & tests_pass) -> release_ready"
                />
              </label>
              <p className="meta">
                When filled, this expression replaces the atom selection. Operators: ! not, &amp;
                and, | or, -&gt; implies, &lt;-&gt; equivalent. Use parentheses to make grouping
                explicit.
              </p>
            </details>
            {parseError ? (
              <p role="alert">{parseError}</p>
            ) : (
              <p className="formula">{prettyFormula(formula)}</p>
            )}
            <label className="revision-control">
              <span>Evidence URI</span>
              <input
                required
                maxLength={2048}
                value={uri}
                onChange={(e) => setUri(e.target.value)}
                placeholder="https://… or fixture://…"
              />
            </label>
            <label className="revision-control">
              <span>Evidence excerpt</span>
              <textarea
                required
                maxLength={2000}
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
              />
            </label>
            <label className="revision-control">
              <span>Observed at (local time)</span>
              <input
                required
                type="datetime-local"
                value={observed}
                onChange={(e) => setObserved(e.target.value)}
              />
            </label>
          </>
        )}
        <label className="revision-control">
          <span>Reason</span>
          <input
            required
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <p className="meta">
          Changes are checked against the complete revision. Sources document provenance; logical
          validity does not establish that a source is factually correct.
        </p>
        <button
          className="primary"
          type="submit"
          disabled={
            !reason.trim() ||
            (mode !== "add" && !validTarget) ||
            (mode !== "retract" &&
              (Boolean(parseError) || !atom || !uri.trim() || !excerpt.trim() || !observed))
          }
        >
          {mutation.isPending ? "Saving…" : "Submit for check"}
        </button>
      </fieldset>
      {notice && (
        <p className="callout" role="status">
          {notice}
        </p>
      )}
    </form>
  )
}
