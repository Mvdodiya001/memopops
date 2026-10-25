import { useState } from "react"
import { ApiError, initializeWorkspace } from "../api/client"
import type { AtomRecord } from "../api/types"

export function WorkspaceSetup(props: {
  workspaceId: string
  token: string
  onReady: (revision: string) => void
}) {
  const [atoms, setAtoms] = useState<AtomRecord[]>([{ id: "", label: "", meaning: "", scope: "" }])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  return (
    <details className="panel workspace-setup">
      <summary>Create your own workspace</summary>
      <p>
        Use an operator token assigned to the workspace above. Define each proposition precisely
        before adding facts or rules. Creating a workspace starts with no accepted claims.
      </p>
      <p className="meta">
        The vocabulary is fixed for this workspace. For example, use a scope such as “release
        2026.10” rather than an ambiguous claim about all releases. Existing workspaces are never
        reset here.
      </p>
      {atoms.map((atom, index) => (
        <fieldset key={index} disabled={pending}>
          <legend>Proposition {index + 1}</legend>
          {(
            [
              ["id", "ID (for example, tests_pass)"],
              ["label", "Short label"],
              ["meaning", "Precise meaning"],
              ["scope", "Scope / project version"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="revision-control">
              <span>{label}</span>
              <input
                value={atom[key]}
                maxLength={
                  key === "id" ? 64 : key === "meaning" ? 1000 : key === "scope" ? 200 : 120
                }
                onChange={(e) =>
                  setAtoms(
                    atoms.map((value, i) =>
                      i === index ? { ...value, [key]: e.target.value } : value,
                    ),
                  )
                }
              />
            </label>
          ))}
          {atoms.length > 1 && (
            <button type="button" onClick={() => setAtoms(atoms.filter((_, i) => i !== index))}>
              Remove proposition {index + 1}
            </button>
          )}
        </fieldset>
      ))}
      <div className="cluster">
        <button
          type="button"
          disabled={pending || atoms.length >= 128}
          onClick={() => setAtoms([...atoms, { id: "", label: "", meaning: "", scope: "" }])}
        >
          Add proposition
        </button>
        <button
          className="primary"
          type="button"
          disabled={
            pending ||
            !props.token ||
            !props.workspaceId.trim() ||
            atoms.some((atom) => Object.values(atom).some((value) => !value.trim()))
          }
          onClick={() => {
            setPending(true)
            setError("")
            void initializeWorkspace(props.workspaceId, atoms, { token: props.token })
              .then((result) => props.onReady(result.revision_id))
              .catch((caught: unknown) =>
                setError(
                  caught instanceof ApiError ? caught.message : "Workspace creation failed.",
                ),
              )
              .finally(() => setPending(false))
          }}
        >
          {pending ? "Creating…" : "Create workspace"}
        </button>
      </div>
      {error && (
        <p className="callout" role="alert">
          {error}
        </p>
      )}
    </details>
  )
}
