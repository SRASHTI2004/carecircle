import { useEffect } from "react";
import { api } from "../api";
import type { Me } from "../types";
import { formatUtc, Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
  large?: boolean;
  version: number;
  onResolved: () => void;
}

/** Changes waiting for the elder's approval. The elder can approve or reject; others just see them. */
export function PendingPanel({ me, notify, large, version, onResolved }: Props) {
  const pending = useLoad(api.pending, 30_000);
  const list = pending.data ?? [];
  const { reload } = pending;
  // `version` changes when something may have been queued elsewhere; re-fetch then.
  useEffect(() => {
    void reload();
  }, [version, reload]);
  if (list.length === 0) return null;

  async function decide(id: number, decision: "approve" | "reject") {
    try {
      await api.decide(id, decision);
      notify(decision === "approve" ? "Change approved and applied." : "Change rejected.");
      void pending.reload();
      onResolved();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  return (
    <section className={`card pending${large ? " large" : ""}`} aria-labelledby="pending-h">
      <h2 id="pending-h">Waiting for {me.role === "elder" ? "your" : `${me.profile.name}'s`} approval ({list.length})</h2>
      <ul className="list">
        {list.map((p) => (
          <li key={p.id} className="list-item">
            <div>
              <strong>{p.summary}</strong>
              <div className="muted">Requested by {ROLE_LABEL[p.requested_by]} &middot; {formatUtc(p.created_at)}</div>
              <span className="badge badge-due">Pending elder approval</span>
            </div>
            {me.role === "elder" && (
              <div className="row">
                <button className="btn btn-primary" onClick={() => void decide(p.id, "approve")} aria-label={`Approve: ${p.summary}`}>Approve</button>
                <button className="btn btn-danger" onClick={() => void decide(p.id, "reject")} aria-label={`Reject: ${p.summary}`}>Reject</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
