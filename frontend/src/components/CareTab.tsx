import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Activity, Me } from "../types";
import { DISCLAIMER, formatUtc, Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
}

export function CareTab({ me, notify }: Props) {
  const summary = useLoad(api.weeklySummary);
  const comments = useLoad(api.comments);
  const activity = useLoad(() => api.activity(0));
  const [more, setMore] = useState<Activity[]>([]);
  const [exhausted, setExhausted] = useState(false);
  const [text, setText] = useState("");

  async function post(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addComment(text);
      setText("");
      notify("Note posted.");
      void comments.reload();
      void activity.reload();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not post.", "error");
    }
  }

  async function loadMore() {
    const offset = (activity.data?.length ?? 0) + more.length;
    const next = await api.activity(offset);
    setMore([...more, ...next]);
    if (next.length < 20) setExhausted(true);
  }

  const feed = [...(activity.data ?? []), ...more];

  return (
    <div className="stack">
      <section className="card" aria-labelledby="sum-h">
        <h2 id="sum-h">
          Weekly summary for family <span className="badge">AI, optional</span>
        </h2>
        {summary.loading && <p role="status">Writing the summary...</p>}
        {summary.data && (
          <>
            <p className="summary-text">{summary.data.summary}</p>
            {summary.data.message && (
              <p className="muted" role="status">
                {summary.data.message}
              </p>
            )}
            <p className="muted">
              {summary.data.source === "ai" ? "Reworded by AI from the adherence numbers. " : ""}
              {DISCLAIMER}
            </p>
          </>
        )}
        {summary.error && (
          <p role="alert" className="error">
            {summary.error}
          </p>
        )}
      </section>

      <section className="card" aria-labelledby="comm-h">
        <h2 id="comm-h">Notes for the care circle</h2>
        <form className="form" onSubmit={(e) => void post(e)}>
          <div className="field">
            <label htmlFor="comment">Leave a note for {me.profile.name}'s care circle</label>
            <textarea
              id="comment"
              required
              maxLength={500}
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <button className="btn btn-primary">Post note</button>
        </form>
        <ul className="list">
          {comments.data?.map((c, i) => (
            <li key={i} className="list-item">
              <div>
                <strong>{ROLE_LABEL[c.role]}</strong>: {c.text}
                <div className="muted">{formatUtc(c.created_at)}</div>
              </div>
            </li>
          ))}
        </ul>
        {comments.data?.length === 0 && <p className="muted">No notes yet. Say hello!</p>}
      </section>

      <section className="card" aria-labelledby="act-h">
        <h2 id="act-h">Activity feed</h2>
        <p className="muted">Every change and dose is recorded so {me.profile.name} can always see who did what.</p>
        {activity.error && (
          <p role="alert" className="error">
            {activity.error}
          </p>
        )}
        <ul className="list">
          {feed.map((a, i) => (
            <li key={i} className="list-item">
              <div>
                <strong>{ROLE_LABEL[a.actor_role]}</strong> {a.action}: {a.detail}
                <div className="muted">{formatUtc(a.created_at)}</div>
              </div>
            </li>
          ))}
        </ul>
        {!exhausted && (activity.data?.length ?? 0) >= 20 && (
          <button className="btn btn-secondary" onClick={() => void loadMore()}>
            Show older activity
          </button>
        )}
      </section>
    </div>
  );
}
