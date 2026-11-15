import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Me } from "../types";
import { DISCLAIMER, formatUtc, Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
}

export function CareTab({ me, notify }: Props) {
  const summary = useLoad(api.weeklySummary);
  const comments = useLoad(api.comments);
  const activity = useLoad(api.activity);
  const [text, setText] = useState("");

  async function post(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addComment(text);
      setText("");
      void comments.reload();
      void activity.reload();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not post.", "error");
    }
  }

  return (
    <div className="stack">
      <section className="card" aria-labelledby="sum-h">
        <h2 id="sum-h">Weekly summary for family <span className="badge">AI, optional</span></h2>
        {summary.loading && <p role="status">Writing summary...</p>}
        {summary.data && (
          <>
            <p className="summary-text">{summary.data.summary}</p>
            {summary.data.message && <p className="muted" role="status">{summary.data.message}</p>}
            <p className="muted">
              {summary.data.source === "ai" ? "Written by AI from the adherence numbers. " : ""}{DISCLAIMER}
            </p>
          </>
        )}
        {summary.error && <p role="alert" className="error">{summary.error}</p>}
      </section>

      <section className="card" aria-labelledby="comm-h">
        <h2 id="comm-h">Family notes</h2>
        <form className="form" onSubmit={(e) => void post(e)}>
          <div className="field">
            <label htmlFor="comment">Leave a note for {me.profile.name}'s care circle</label>
            <textarea id="comment" required maxLength={500} rows={2} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <button className="btn btn-primary">Post note</button>
        </form>
        <ul className="list">
          {comments.data?.map((c, i) => (
            <li key={i} className="list-item">
              <div><strong>{ROLE_LABEL[c.role]}</strong>: {c.text}<div className="muted">{formatUtc(c.created_at)}</div></div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby="act-h">
        <h2 id="act-h">Activity log</h2>
        <p className="muted">Every change and dose is recorded here so {me.profile.name} can see who did what.</p>
        <ul className="list">
          {activity.data?.map((a, i) => (
            <li key={i} className="list-item">
              <div><strong>{ROLE_LABEL[a.actor_role]}</strong> {a.action}: {a.detail}<div className="muted">{formatUtc(a.created_at)}</div></div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
