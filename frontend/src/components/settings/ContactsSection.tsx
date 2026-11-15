import { FormEvent, useState } from "react";
import { api } from "../../api";
import type { NotifyType, Role } from "../../types";
import { NOTIFY_ALL, NOTIFY_LABEL, Notify, ROLE_LABEL, useLoad } from "../../util";

const EMPTY_CONTACT: { name: string; email: string; role: Role } = { name: "", email: "", role: "family" };

/** Who gets email reminders, and which kinds each person receives. */
export function ContactsSection({ notify }: { notify: Notify }) {
  const contacts = useLoad(api.contacts);
  const [form, setForm] = useState(EMPTY_CONTACT);

  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api.addContact(form);
      setForm(EMPTY_CONTACT);
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

  return (
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
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="c-email">Email</label>
            <input
              id="c-email"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="c-role">Role</label>
            <select id="c-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              <option value="elder">Elder</option>
              <option value="caretaker">Caretaker</option>
              <option value="family">Family</option>
            </select>
          </div>
        </div>
        <button className="btn btn-primary">Add contact</button>
      </form>
    </section>
  );
}
