import { useInfiniteQuery } from "@tanstack/react-query"
import { getQueryHistory, type QuerySummary } from "../api/client"
import { formatTimestamp, prettyFormula } from "../model/formula"

export function QueryHistory(props: {
  workspaceId: string
  token: string
  onOpen: (item: QuerySummary) => void
}) {
  const history = useInfiniteQuery({
    queryKey: ["query-history", props.workspaceId],
    queryFn: ({ pageParam, signal }) =>
      getQueryHistory(props.workspaceId, { token: props.token, signal }, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  })
  return (
    <details className="panel">
      <summary className="section-title">Saved questions</summary>
      <button type="button" onClick={() => void history.refetch()}>
        Refresh questions
      </button>
      <p className="meta">
        Reopen a result with its original premises and proof. A historical answer must be rechecked
        before making a current decision.
      </p>
      {history.isPending && <p role="status">Loading questions…</p>}
      {history.error && (
        <p role="alert">Query history could not be loaded. Use Refresh questions to retry.</p>
      )}
      {history.data?.pages.every((page) => !page.items.length) && (
        <p>No questions yet. Check a proposition or rule above.</p>
      )}
      <ul className="memory-list">
        {history.data?.pages
          .flatMap((page) => page.items)
          .map((item) => (
            <li key={item.query_id}>
              <button type="button" className="memory-row" onClick={() => props.onOpen(item)}>
                <strong>
                  {item.query
                    ? prettyFormula(item.query)
                    : "Earlier question · expression unavailable"}
                </strong>
                <span>
                  {item.result} · {item.proof_status}
                </span>
                <span className="meta">
                  {item.revision_id}
                  {item.created_at ? ` · ${formatTimestamp(item.created_at)}` : ""}
                </span>
              </button>
            </li>
          ))}
      </ul>
      {history.hasNextPage && (
        <button
          type="button"
          disabled={history.isFetchingNextPage}
          onClick={() => void history.fetchNextPage()}
        >
          Load earlier questions
        </button>
      )}
    </details>
  )
}
