import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Me, NotifyType, Role } from "../types";
import { NOTIFY_ALL, NOTIFY_LABEL, Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
  onChanged: () => void;
}

export function SettingsTab({ me, notify, onChanged }: Props) {
  const contacts = useLoad(api.contacts);
  const passcodes = useLoad(api.passcodes);
  const [c, setC] = useState<{ name: string; email: string; role: Role }>({ name: "", email: "", role: "family" });
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [fresh, setFresh] = useState<{ role: Role; passcode: string } | null>(null);

  async function toggle(value: boolean) {
    try {
      await api.setApproval(value);
      notify(value ? "Others' changes now need your approval." : "Changes by others apply immediately.");
      onChanged();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addContact(c);
      setC({ name: "", email: "", role: "family" });
      void contacts.reload();
      notify("Reminder contact added.");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not save.", "error");
    }
  }

  async function remove(id: number, name: string) {
    if (!window.confirm(`Remove ${name} from email reminders?`)) return;
    await api.deleteContact(id);
    void contacts.reload();
  }

  async function togglePref(id: number, current: NotifyType[], type: NotifyType, on: boolean) {
    const next = on ? [...current, type] : current.filter((t) => t !== type);
    try {
      await api.setNotify(id, next);
      void contacts.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  async function sendTest(e: FormEvent) {
    e.preventDefault();
    setTesting(true);
    try {
      const r = await api.testEmail(testTo);
      notify(r.message, r.delivered || !r.smtp_configured ? "ok" : "error");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not send.", "error");
    } finally {
      setTesting(false);
    }
  }

  async function rotate(role: Role) {
    if (
      !window.confirm(
        `Create a new ${ROLE_LABEL[role]} passcode? The old one stops working and that role is signed out.`,
      )
    )
      return;
    try {
      const r = await api.rotatePasscode(role);
      setFresh({ role, passcode: r.passcode });
      void passcodes.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  async function revoke(role: Role) {
    if (
      !window.confirm(
        `Turn off the ${ROLE_LABEL[role]} passcode? Nobody can sign in with it until you create a new one.`,
      )
    )
      return;
    try {
      await api.revokePasscode(role);
      notify(`${ROLE_LABEL[role]} passcode turned off.`);
      void passcodes.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  return (
    <div className="stack">
      <section className="card" aria-labelledby="appr-h">
        <h2 id="appr-h">{me.profile.name} decides</h2>
        <div className="check">
          <input
            id="approval"
            type="checkbox"
            checked={me.profile.require_approval}
            disabled={me.role !== "elder"}
            onChange={(e) => void toggle(e.target.checked)}
            aria-describedby="approval-help"
          />
          <label htmlFor="approval">Require the elder's approval before others' changes take effect</label>
        </div>
        <p id="approval-help" className="muted">
          {me.role === "elder"
            ? 'When on, changes by caretakers appear as "pending elder approval" until you approve them. Your own changes always apply at once.'
            : "Only the elder can change this setting."}
        </p>
      </section>

      <section className="card" aria-labelledby="contacts-h">
        <h2 id="contacts-h">Who gets email reminders</h2>
        {contacts.loading && <p role="status">Loading...</p>}
        {contacts.error && (
          <p role="alert" className="error">
            {contacts.error}
          </p>
        )}
        <ul className="list">
          {contacts.data?.map((x) => (
            <li key={x.id} className="list-item column">
              <div className="row between wrap full">
                <div>
                  <strong>{x.name}</strong> ({ROLE_LABEL[x.role]}) <span className="muted">{x.email}</span>
                </div>
                <button
                  className="btn btn-danger"
                  onClick={() => void remove(x.id, x.name)}
                  aria-label={`Remove ${x.name}`}
                >
                  Remove
                </button>
              </div>
              <fieldset className="prefs">
                <legend>Emails {x.name} receives</legend>
                {NOTIFY_ALL.map((t) => (
                  <label key={t} className="pref">
                    <input
                      type="checkbox"
                      checked={x.notify.includes(t)}
                      onChange={(e) => void togglePref(x.id, x.notify, t, e.target.checked)}
                    />
                    {NOTIFY_LABEL[t]}
                  </label>
                ))}
              </fieldset>
            </li>
          ))}
        </ul>
        {contacts.data?.length === 0 && (
          <p className="muted">No one yet. Add an email below to start sending reminders.</p>
        )}
        <form className="form" onSubmit={(e) => void add(e)}>
          <h3>Add a person</h3>
          <div className="grid-3">
            <div className="field">
              <label htmlFor="c-name">Name</label>
              <input
                id="c-name"
                required
                maxLength={80}
                value={c.name}
                onChange={(e) => setC({ ...c, name: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="c-email">Email</label>
              <input
                id="c-email"
                type="email"
                required
                value={c.email}
                onChange={(e) => setC({ ...c, email: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="c-role">Role</label>
              <select id="c-role" value={c.role} onChange={(e) => setC({ ...c, role: e.target.value as Role })}>
                <option value="elder">Elder</option>
                <option value="caretaker">Caretaker</option>
                <option value="family">Family</option>
              </select>
            </div>
          </div>
          <button className="btn btn-primary">Add contact</button>
        </form>
      </section>

      <section className="card" aria-labelledby="test-h">
        <h2 id="test-h">Send a test email</h2>
        <p className="muted">
          Check that email reminders reach you. Without email set up on the server, the test appears in the Email
          reminders page instead.
        </p>
        <form className="form" onSubmit={(e) => void sendTest(e)}>
          <div className="field">
            <label htmlFor="test-to">Send to</label>
            <input id="test-to" type="email" required value={testTo} onChange={(e) => setTestTo(e.target.value)} />
          </div>
          <button className="btn btn-primary" disabled={testing}>
            {testing ? "Sending..." : "Send test email"}
          </button>
        </form>
      </section>

      <section className="card" aria-labelledby="pass-h">
        <h2 id="pass-h">Passcodes</h2>
        <p className="muted">
          {me.role === "elder"
            ? "Create a new passcode if one is shared with the wrong person, or turn one off."
            : "You can manage the family passcode."}
        </p>
        {fresh && (
          <div className="subcard" role="status">
            New {ROLE_LABEL[fresh.role]} passcode: <code>{fresh.passcode}</code>
            <p className="muted">Share it now. It is shown only once.</p>
          </div>
        )}
        {passcodes.error && (
          <p role="alert" className="error">
            {passcodes.error}
          </p>
        )}
        <ul className="list">
          {passcodes.data?.map((p) => (
            <li key={p.role} className="list-item">
              <div>
                <strong>{ROLE_LABEL[p.role]}</strong>{" "}
                <span className={`badge ${p.active ? "badge-taken_on_time" : "badge-missed"}`}>
                  {p.active ? "On" : "Turned off"}
                </span>
              </div>
              {p.can_manage && (
                <div className="row wrap">
                  <button
                    className="btn btn-secondary"
                    onClick={() => void rotate(p.role)}
                    aria-label={`Create a new ${ROLE_LABEL[p.role]} passcode`}
                  >
                    New passcode
                  </button>
                  {p.role !== me.role && p.active && (
                    <button
                      className="btn btn-danger"
                      onClick={() => void revoke(p.role)}
                      aria-label={`Turn off the ${ROLE_LABEL[p.role]} passcode`}
                    >
                      Turn off
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
