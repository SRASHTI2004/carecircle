import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Emergency, EmergencyInput, Me } from "../types";
import { DISCLAIMER, formatUtc, Notify, ROLE_LABEL, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
}

const FIELDS: { key: keyof EmergencyInput; label: string; long?: boolean }[] = [
  { key: "blood_group", label: "Blood group" },
  { key: "allergies", label: "Allergies", long: true },
  { key: "conditions", label: "Medical conditions", long: true },
  { key: "doctor_name", label: "Doctor's name" },
  { key: "doctor_phone", label: "Doctor's phone" },
  { key: "emergency_contacts", label: "Emergency contacts (names and phones)", long: true },
  { key: "notes", label: "Other notes for a doctor", long: true },
];

/** Full-screen, high-contrast card to show a doctor or paramedic. */
function CardView({ card, onClose }: { card: Emergency; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="doctor-view" role="dialog" aria-modal="true" aria-labelledby="dv-title">
      <div className="doctor-inner">
        <div className="row between wrap no-print">
          <button className="btn btn-big btn-primary" onClick={() => window.print()}>
            Print
          </button>
          <button ref={closeRef} className="btn btn-big btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <h1 id="dv-title">Emergency information</h1>
        <p className="dv-name">{card.name}</p>
        <dl className="dv-grid">
          <div>
            <dt>Blood group</dt>
            <dd>{card.blood_group || "Not recorded"}</dd>
          </div>
          <div>
            <dt>Allergies</dt>
            <dd>{card.allergies || "None recorded"}</dd>
          </div>
          <div>
            <dt>Conditions</dt>
            <dd>{card.conditions || "None recorded"}</dd>
          </div>
          <div>
            <dt>Doctor</dt>
            <dd>
              {card.doctor_name || "Not recorded"} {card.doctor_phone}
            </dd>
          </div>
          <div>
            <dt>Emergency contacts</dt>
            <dd>{card.emergency_contacts || "Not recorded"}</dd>
          </div>
        </dl>
        <h2>Current medicines</h2>
        {card.medicines.length === 0 ? (
          <p>None recorded.</p>
        ) : (
          <ul className="dv-meds">
            {card.medicines.map((m) => (
              <li key={m.name}>
                <strong>{m.name}</strong> {m.dose}, {m.times.length}x daily
                {m.instructions ? ` (${m.instructions})` : ""}
              </li>
            ))}
          </ul>
        )}
        {card.notes && (
          <p>
            <strong>Notes:</strong> {card.notes}
          </p>
        )}
        <p className="dv-foot">
          Shown from CareCircle{card.updated_at ? `, last updated ${formatUtc(card.updated_at)}` : ""}. {DISCLAIMER}
        </p>
      </div>
    </div>
  );
}

export function EmergencyTab({ me, notify }: Props) {
  const card = useLoad(api.emergency);
  const [form, setForm] = useState<EmergencyInput | null>(null);
  const [showing, setShowing] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    try {
      await api.saveEmergency(form);
      notify("Emergency card saved.");
      setForm(null);
      void card.reload();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not save.", "error");
    }
  }

  const c = card.data;
  return (
    <section className="card" aria-labelledby="em-h">
      <div className="row between wrap">
        <h2 id="em-h">Emergency information card</h2>
        <div className="row wrap">
          <button className="btn btn-primary" disabled={!c} onClick={() => setShowing(true)}>
            Show to doctor
          </button>
          {c?.can_edit && !form && (
            <button
              className="btn btn-secondary"
              onClick={() =>
                setForm({
                  blood_group: c.blood_group,
                  allergies: c.allergies,
                  conditions: c.conditions,
                  doctor_name: c.doctor_name,
                  doctor_phone: c.doctor_phone,
                  emergency_contacts: c.emergency_contacts,
                  notes: c.notes,
                })
              }
            >
              Edit card
            </button>
          )}
        </div>
      </div>
      <p className="muted">
        {c?.can_edit
          ? `You control what is on this card, ${c.name}. `
          : `${me.profile.name} controls this card; only they can edit it. `}
        Current medicines are filled in automatically.
      </p>
      {card.loading && <p role="status">Loading...</p>}
      {card.error && (
        <p role="alert" className="error">
          {card.error}
        </p>
      )}
      {form ? (
        <form className="form" onSubmit={(e) => void save(e)}>
          {FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label htmlFor={`em-${f.key}`}>{f.label}</label>
              {f.long ? (
                <textarea
                  id={`em-${f.key}`}
                  rows={2}
                  maxLength={500}
                  value={form[f.key]}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              ) : (
                <input
                  id={`em-${f.key}`}
                  maxLength={f.key === "blood_group" ? 10 : 100}
                  value={form[f.key]}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              )}
            </div>
          ))}
          <div className="row wrap">
            <button className="btn btn-primary">Save card</button>
            <button type="button" className="btn btn-secondary" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        c && (
          <dl className="facts">
            {FIELDS.map((f) => (
              <div key={f.key}>
                <dt>{f.label}</dt>
                <dd>{c[f.key] || <span className="muted">Not recorded</span>}</dd>
              </div>
            ))}
            <div>
              <dt>Current medicines</dt>
              <dd>
                {c.medicines.length ? (
                  c.medicines.map((m) => `${m.name} ${m.dose}`).join(", ")
                ) : (
                  <span className="muted">None</span>
                )}
              </dd>
            </div>
            <div>
              <dt>Care circle</dt>
              <dd>
                {c.contacts.length ? (
                  c.contacts.map((x) => `${x.name} (${ROLE_LABEL[x.role]})`).join(", ")
                ) : (
                  <span className="muted">None</span>
                )}
              </dd>
            </div>
          </dl>
        )
      )}
      {showing && c && <CardView card={c} onClose={() => setShowing(false)} />}
    </section>
  );
}
