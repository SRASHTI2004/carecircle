import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Me, Role } from "../types";
import { Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
  onChanged: () => void;
}

export function SettingsTab({ me, notify, onChanged }: Props) {
  const contacts = useLoad(api.contacts);
  const [c, setC] = useState<{ name: string; email: string; role: Role }>({ name: "", email: "", role: "family" });

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

  async function remove(id: number) {
    await api.deleteContact(id);
    void contacts.reload();
  }

  return (
    <div className="stack">
      <section className="card" aria-labelledby="appr-h">
        <h2 id="appr-h">{me.profile.name} decides</h2>
        <div className="check">
          <input id="approval" type="checkbox" checked={me.profile.require_approval} disabled={me.role !== "elder"}
            onChange={(e) => void toggle(e.target.checked)} aria-describedby="approval-help" />
          <label htmlFor="approval">Require the elder's approval before others' changes take effect</label>
        </div>
        <p id="approval-help" className="muted">
          {me.role === "elder"
            ? "When on, changes by caretakers appear as \"pending elder approval\" until you approve them. Your own changes always apply at once."
            : "Only the elder can change this setting."}
        </p>
      </section>

      <section className="card" aria-labelledby="contacts-h">
        <h2 id="contacts-h">Who gets email reminders</h2>
        <ul className="list">
          {contacts.data?.map((x) => (
            <li key={x.id} className="list-item">
              <div><strong>{x.name}</strong> ({ROLE_LABEL[x.role]}) <span className="muted">{x.email}</span></div>
              <button className="btn btn-danger" onClick={() => void remove(x.id)} aria-label={`Remove ${x.name}`}>Remove</button>
            </li>
          ))}
        </ul>
        <form className="form" onSubmit={(e) => void add(e)}>
          <div className="grid-3">
            <div className="field">
              <label htmlFor="c-name">Name</label>
              <input id="c-name" required maxLength={80} value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="c-email">Email</label>
              <input id="c-email" type="email" required value={c.email} onChange={(e) => setC({ ...c, email: e.target.value })} />
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
    </div>
  );
}
