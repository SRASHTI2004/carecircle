import { api } from "../api";
import { formatUtc, useLoad } from "../util";

export function OutboxTab() {
  const box = useLoad(api.outbox, 30_000);
  return (
    <section className="card" aria-labelledby="out-h">
      <h2 id="out-h">Email reminders</h2>
      {box.data && (
        <p className="muted">
          {box.data.smtp_configured
            ? "Email is configured: reminders are sent to your care circle and listed here."
            : "Demo outbox: email (SMTP) is not configured, so these are the emails that would have been sent."}
        </p>
      )}
      {box.error && <p role="alert" className="error">{box.error}</p>}
      <ul className="list">
        {box.data?.emails.map((e) => (
          <li key={e.id} className="list-item">
            <details>
              <summary>
                <strong>{e.subject}</strong> to {e.to_email}{" "}
                <span className={`badge ${e.delivered ? "badge-taken_on_time" : ""}`}>{e.delivered ? "Sent" : "Not sent (demo)"}</span>
                <span className="muted"> {formatUtc(e.created_at)}</span>
              </summary>
              <pre className="mail">{e.body}</pre>
            </details>
          </li>
        ))}
      </ul>
      {box.data?.emails.length === 0 && (
        <p className="muted">No reminders yet. They appear when a dose is coming up or missed, an appointment is near, or stock is low.</p>
      )}
    </section>
  );
}
