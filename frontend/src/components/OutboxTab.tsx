import { useState } from "react";
import { api } from "../api";
import type { OutboxEmail } from "../types";
import { formatUtc, useLoad } from "../util";

function state(e: OutboxEmail, smtp: boolean): { label: string; cls: string } {
  if (e.delivered) return { label: "Sent", cls: "badge-taken_on_time" };
  if (smtp && e.error) return { label: "Failed, will retry", cls: "badge-missed" };
  return { label: "Not sent (demo)", cls: "badge-upcoming" };
}

/** Email reminders page: the demo outbox, or sent mail when SMTP is configured. */
export function OutboxTab() {
  const box = useLoad(() => api.outbox(0), 30_000);
  const [more, setMore] = useState<OutboxEmail[]>([]);
  const [exhausted, setExhausted] = useState(false);
  const smtp = box.data?.smtp_configured ?? false;
  const emails = [...(box.data?.emails ?? []), ...more];

  async function loadMore() {
    const next = await api.outbox(emails.length);
    setMore([...more, ...next.emails]);
    if (next.emails.length < 20) setExhausted(true);
  }

  return (
    <section className="card" aria-labelledby="out-h">
      <h2 id="out-h">Email reminders</h2>
      {box.data && (
        <p className="muted">
          {smtp
            ? "Email is set up: reminders are sent to your care circle and listed here."
            : "Demo outbox: email (SMTP) is not set up on this server, so these are the emails that would have been sent."}
        </p>
      )}
      {box.loading && <p role="status">Loading...</p>}
      {box.error && (
        <p role="alert" className="error">
          {box.error}
        </p>
      )}
      <ul className="list">
        {emails.map((e) => {
          const s = state(e, smtp);
          return (
            <li key={e.id} className="list-item">
              <details>
                <summary>
                  <strong>{e.subject}</strong> to {e.to_email} <span className={`badge ${s.cls}`}>{s.label}</span>
                  <span className="muted"> {formatUtc(e.created_at)}</span>
                </summary>
                <pre className="mail">{e.body}</pre>
              </details>
            </li>
          );
        })}
      </ul>
      {box.data && emails.length === 0 && (
        <p className="muted">
          No emails yet. They appear when a dose is coming up or missed, an appointment is near, or stock is low. Try
          "Send a test email" in Settings.
        </p>
      )}
      {!exhausted && (box.data?.emails.length ?? 0) >= 20 && (
        <button className="btn btn-secondary" onClick={() => void loadMore()}>
          Show older emails
        </button>
      )}
    </section>
  );
}
