import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Role } from "../types";
import { DISCLAIMER, ROLE_LABEL } from "../util";

const DEMO: { role: Role; passcode: string }[] = [
  { role: "elder", passcode: "DEMO-ELDER24" },
  { role: "caretaker", passcode: "DEMO-CARER24" },
  { role: "family", passcode: "DEMO-FAMILY24" },
];

interface Props {
  onLogin: (token: string, role: Role) => void;
}

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
    <main id="main" className="login">
      <h1>CareCircle</h1>
      <p className="lead">One shared place for an elder, their caretakers and family. The elder always stays in charge.</p>

      <section className="card" aria-labelledby="signin-h">
        <h2 id="signin-h">Sign in with a passcode</h2>
        <form className="form" onSubmit={(e) => { e.preventDefault(); void signIn(passcode); }}>
          <div className="field">
            <label htmlFor="passcode">Passcode</label>
            <input id="passcode" autoComplete="off" autoCapitalize="characters" spellCheck={false} required value={passcode}
              onChange={(e) => setPasscode(e.target.value)} aria-describedby="passcode-help" />
            <small id="passcode-help" className="muted">Looks like ABCD-1234WXYZ. Ask the elder for the right one for your role.</small>
          </div>
          {error && <p role="alert" className="error">{error}</p>}
          <button className="btn btn-primary" disabled={busy}>Sign in</button>
        </form>
      </section>

      <section className="card demo" aria-labelledby="demo-h">
        <h2 id="demo-h">Try the demo (for judges)</h2>
        <p className="muted">A demo profile, Margaret Sharma, has medicines, appointments and two weeks of history.</p>
        <table>
          <caption className="sr-only">Demo passcodes</caption>
          <thead><tr><th scope="col">Role</th><th scope="col">Passcode</th><th scope="col"><span className="sr-only">Action</span></th></tr></thead>
          <tbody>
            {DEMO.map((d) => (
              <tr key={d.role}>
                <th scope="row">{ROLE_LABEL[d.role]}</th>
                <td><code>{d.passcode}</code></td>
                <td>
                  <button className="btn btn-secondary" disabled={busy} onClick={() => void signIn(d.passcode)} aria-label={`Sign in as ${ROLE_LABEL[d.role]}`}>
                    Sign in
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card" aria-labelledby="new-h">
        <h2 id="new-h">Set up a new care profile</h2>
        {!creating && !created && <button className="btn btn-secondary" onClick={() => setCreating(true)}>Create a profile</button>}
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
                <input id={`p-${r}`} type="email" value={emails[r]} onChange={(e) => setEmails({ ...emails, [r]: e.target.value })} />
              </div>
            ))}
            <button className="btn btn-primary" disabled={busy}>Create profile</button>
          </form>
        )}
        {created && (
          <div role="status">
            <p><strong>Save these passcodes now. They are shown only once.</strong></p>
            <ul className="list">
              {(Object.keys(created) as Role[]).map((r) => (
                <li key={r} className="list-item">{ROLE_LABEL[r]}: <code>{created[r]}</code></li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <p className="muted center">{DISCLAIMER}</p>
    </main>
  );
}
