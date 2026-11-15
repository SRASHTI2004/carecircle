import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Role } from "../types";
import { DISCLAIMER, ROLE_LABEL } from "../util";

export const DEMO: { role: Role; passcode: string; blurb: string }[] = [
  { role: "elder", passcode: "DEMO-ELDER24", blurb: "Big buttons, read aloud, approves changes" },
  { role: "caretaker", passcode: "DEMO-CARER24", blurb: "Manages medicines and appointments" },
  { role: "family", passcode: "DEMO-FAMILY24", blurb: "Views progress and leaves notes" },
];

interface Props {
  onLogin: (token: string, role: Role) => void;
}

const FEATURES = [
  ["Medicines and daily routines", "Doses, walks, BP and sugar checks, with one-tap Taken."],
  ["Family kept in the loop", "Email reminders, weekly summaries and a shared activity feed."],
  ["The elder decides", "Approve or reject changes, control the emergency card."],
  ["Made to be easy", "Large text, high contrast, read aloud, keyboard friendly."],
];

export function Login({ onLogin }: Props) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [emails, setEmails] = useState<Record<Role, string>>({ elder: "", caretaker: "", family: "" });
  const [created, setCreated] = useState<Record<Role, string> | null>(null);

  async function signIn(code: string) {
    setBusy(true);
    setError("");
    try {
      const r = await api.login(code);
      onLogin(r.token, r.role);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const contacts = (Object.keys(emails) as Role[])
        .filter((r) => emails[r].trim())
        .map((r) => ({ name: `${ROLE_LABEL[r]} contact`, email: emails[r].trim(), role: r }));
      const r = await api.createProfile(name, contacts);
      setCreated(r.passcodes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="login" tabIndex={-1}>
      <header className="hero">
        <p className="eyebrow">CareCircle</p>
        <h1>Care that keeps the elder at the centre.</h1>
        <p className="lead">
          One shared place where an elderly person, their caretakers and family manage medicines, routines and
          appointments together, with timely email reminders.
        </p>
        <ul className="features">
          {FEATURES.map(([title, text]) => (
            <li key={title}>
              <strong>{title}</strong>
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </header>

      <section className="card demo" aria-labelledby="demo-h">
        <h2 id="demo-h">Try the demo in one click</h2>
        <p className="muted">
          Margaret Sharma's profile comes with medicines, routines, appointments and two weeks of history.
        </p>
        <div className="demo-buttons">
          {DEMO.map((d) => (
            <button
              key={d.role}
              className="btn btn-primary demo-btn"
              disabled={busy}
              onClick={() => void signIn(d.passcode)}
            >
              Try as {ROLE_LABEL[d.role]}
              <span>{d.blurb}</span>
            </button>
          ))}
        </div>
        <table>
          <caption className="sr-only">Demo passcodes</caption>
          <thead>
            <tr>
              <th scope="col">Role</th>
              <th scope="col">Passcode</th>
            </tr>
          </thead>
          <tbody>
            {DEMO.map((d) => (
              <tr key={d.role}>
                <th scope="row">{ROLE_LABEL[d.role]}</th>
                <td>
                  <code>{d.passcode}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card" aria-labelledby="signin-h">
        <h2 id="signin-h">Sign in with a passcode</h2>
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            void signIn(passcode);
          }}
        >
          <div className="field">
            <label htmlFor="passcode">Passcode</label>
            <input
              id="passcode"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              required
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              aria-describedby="passcode-help"
            />
            <small id="passcode-help" className="muted">
              Looks like ABCD-1234WXYZ. Ask the elder for the passcode for your role.
            </small>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="btn btn-primary" disabled={busy}>
            Sign in
          </button>
        </form>
      </section>

      <section className="card" aria-labelledby="new-h">
        <h2 id="new-h">Set up a new care profile</h2>
        {!creating && !created && (
          <button className="btn btn-secondary" onClick={() => setCreating(true)}>
            Create a profile
          </button>
        )}
        {creating && !created && (
          <form className="form" onSubmit={(e) => void create(e)}>
            <div className="field">
              <label htmlFor="p-name">Elder's name</label>
              <input id="p-name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <p className="muted">Optional: emails for reminders.</p>
            {(["elder", "caretaker", "family"] as Role[]).map((r) => (
              <div className="field" key={r}>
                <label htmlFor={`p-${r}`}>{ROLE_LABEL[r]} email</label>
                <input
                  id={`p-${r}`}
                  type="email"
                  value={emails[r]}
                  onChange={(e) => setEmails({ ...emails, [r]: e.target.value })}
                />
              </div>
            ))}
            <button className="btn btn-primary" disabled={busy}>
              Create profile
            </button>
          </form>
        )}
        {created && (
          <div role="status">
            <p>
              <strong>Save these passcodes now. They are shown only once.</strong>
            </p>
            <ul className="list">
              {(Object.keys(created) as Role[]).map((r) => (
                <li key={r} className="list-item">
                  {ROLE_LABEL[r]}: <code>{created[r]}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <p className="muted center">{DISCLAIMER}</p>
    </main>
  );
}
