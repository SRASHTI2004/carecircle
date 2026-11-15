import { FormEvent, useState } from "react";
import { api } from "../api";
import type { Appointment, AppointmentInput, ChangeResult, Me } from "../types";
import { formatDateTime, Notify, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
  onPendingChange: () => void;
}

const EMPTY: AppointmentInput = { doctor: "", place: "", starts_at: "", notes: "" };

function ApptForm({ initial, idPrefix, label, onSubmit, onCancel }: {
  initial: AppointmentInput; idPrefix: string; label: string;
  onSubmit: (a: AppointmentInput) => Promise<void>; onCancel: () => void;
}) {
  const [a, setA] = useState(initial);
  const [busy, setBusy] = useState(false);
  const id = (f: string) => `${idPrefix}-${f}`;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit(a);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="form" onSubmit={(e) => void submit(e)}>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={id("doc")}>Doctor</label>
          <input id={id("doc")} required maxLength={100} value={a.doctor} onChange={(e) => setA({ ...a, doctor: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={id("place")}>Place</label>
          <input id={id("place")} required maxLength={200} value={a.place} onChange={(e) => setA({ ...a, place: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label htmlFor={id("when")}>Date and time</label>
        <input id={id("when")} type="datetime-local" required value={a.starts_at} onChange={(e) => setA({ ...a, starts_at: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor={id("notes")}>Notes</label>
        <textarea id={id("notes")} maxLength={500} rows={2} value={a.notes} onChange={(e) => setA({ ...a, notes: e.target.value })} />
      </div>
      <div className="row">
        <button className="btn btn-primary" disabled={busy}>{label}</button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export function AppointmentsTab({ me, notify, onPendingChange }: Props) {
  const appts = useLoad(api.appointments);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const canEdit = me.can_edit;

  async function guard(fn: () => Promise<ChangeResult>, what: string) {
    try {
      const r = await fn();
      notify(r.status === "pending" ? `${what}: waiting for ${me.profile.name}'s approval.` : `${what}: saved.`);
      setEditing(null);
      void appts.reload();
      onPendingChange();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
      throw e;
    }
  }

  async function remove(a: Appointment) {
    if (!window.confirm(`Delete the appointment with ${a.doctor}?`)) return;
    await guard(() => api.deleteAppointment(a.id), `Delete appointment`).catch(() => undefined);
  }

  return (
    <section className="card" aria-labelledby="appt-h">
      <div className="row between wrap">
        <h2 id="appt-h">Upcoming appointments</h2>
        {canEdit && editing === null && <button className="btn btn-primary" onClick={() => setEditing("new")}>Add appointment</button>}
      </div>
      {!canEdit && <p className="muted">You can view appointments. Only the elder and caretakers can change them.</p>}
      {editing === "new" && (
        <div className="subcard">
          <h3>New appointment</h3>
          <ApptForm initial={EMPTY} idPrefix="new-appt" label="Save appointment" onCancel={() => setEditing(null)}
            onSubmit={(a) => guard(() => api.addAppointment(a), "Add appointment")} />
        </div>
      )}
      {appts.loading && <p>Loading...</p>}
      {appts.error && <p role="alert" className="error">{appts.error}</p>}
      <ul className="list">
        {appts.data?.map((a) => (
          <li key={a.id} className="list-item">
            {editing === a.id ? (
              <ApptForm initial={a} idPrefix={`appt${a.id}`} label="Save changes" onCancel={() => setEditing(null)}
                onSubmit={(v) => guard(() => api.editAppointment(a.id, v), "Update appointment")} />
            ) : (
              <>
                <div>
                  <strong>{a.doctor}</strong>
                  <div>{formatDateTime(a.starts_at)} at {a.place}</div>
                  {a.notes && <div className="muted">{a.notes}</div>}
                </div>
                {canEdit && (
                  <div className="row">
                    <button className="btn btn-secondary" onClick={() => setEditing(a.id)} aria-label={`Edit appointment with ${a.doctor}`}>Edit</button>
                    <button className="btn btn-danger" onClick={() => void remove(a)} aria-label={`Delete appointment with ${a.doctor}`}>Delete</button>
                  </div>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
      {appts.data?.length === 0 && <p className="muted">No upcoming appointments.</p>}
    </section>
  );
}
