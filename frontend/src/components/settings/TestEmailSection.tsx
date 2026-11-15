import { FormEvent, useState } from "react";
import { api } from "../../api";
import type { Notify } from "../../util";

/** "Send a test email" so anyone can confirm that reminders reach them. */
export function TestEmailSection({ notify }: { notify: Notify }) {
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);

  async function send(e: FormEvent) {
    e.preventDefault();
    setSending(true);
    try {
      const r = await api.testEmail(to);
      notify(r.message, r.delivered || !r.smtp_configured ? "ok" : "error");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not send.", "error");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="card" aria-labelledby="test-h">
      <h2 id="test-h">Send a test email</h2>
      <p className="muted">
        Check that email reminders reach you. Without email set up on the server, the test appears in the Email
        reminders page instead.
      </p>
      <form className="form" onSubmit={(e) => void send(e)}>
        <div className="field">
          <label htmlFor="test-to">Send to</label>
          <input id="test-to" type="email" required value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <button className="btn btn-primary" disabled={sending}>
          {sending ? "Sending..." : "Send test email"}
        </button>
      </form>
    </section>
  );
}
