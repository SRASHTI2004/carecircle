import { ChangeEvent, useState } from "react";
import { api } from "../api";
import type { ChangeResult, Me, Medication, MedicationInput } from "../types";
import { DISCLAIMER, Notify, useLoad } from "../util";
import { EMPTY_MED, MedForm } from "./MedForm";

interface Props {
  me: Me;
  notify: Notify;
  onPendingChange: () => void;
}

export function MedicationsTab({ me, notify, onPendingChange }: Props) {
  const meds = useLoad(api.medications);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [drafts, setDrafts] = useState<MedicationInput[]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const canEdit = me.can_edit;

  function done(r: ChangeResult, what: string) {
    notify(r.status === "pending" ? `${what}: waiting for ${me.profile.name}'s approval.` : `${what}: saved.`);
    setEditing(null);
    void meds.reload();
    onPendingChange();
  }

  async function guard(fn: () => Promise<ChangeResult>, what: string) {
    try {
      done(await fn(), what);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
      throw e;
    }
  }

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setAiBusy(true);
    try {
      const r = await api.readPrescription(file);
      if (r.ok) {
        setDrafts(r.drafts);
        notify("Review the draft below. Nothing is saved until you confirm.");
      } else {
        notify(r.message, "error");
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not read the photo. Please enter medicines by hand.", "error");
    } finally {
      setAiBusy(false);
    }
  }

  async function remove(m: Medication) {
    if (!window.confirm(`Stop ${m.name}? Past adherence records are kept.`)) return;
    await guard(() => api.deleteMedication(m.id), `Stop ${m.name}`).catch(() => undefined);
  }

  return (
    <div className="stack">
      <section className="card" aria-labelledby="meds-h">
        <div className="row between wrap">
          <h2 id="meds-h">Medications</h2>
          {canEdit && editing === null && (
            <button className="btn btn-primary" onClick={() => setEditing("new")}>Add medication</button>
          )}
        </div>
        {!canEdit && <p className="muted">You can view medications. Only the elder and caretakers can change them.</p>}
        {editing === "new" && (
          <div className="subcard">
            <h3>New medication</h3>
            <MedForm initial={EMPTY_MED} idPrefix="new" submitLabel="Save medication" onCancel={() => setEditing(null)}
              onSubmit={(m) => guard(() => api.addMedication(m), `Add ${m.name}`)} />
          </div>
        )}
        {meds.loading && <p>Loading...</p>}
        {meds.error && <p role="alert" className="error">{meds.error}</p>}
        <ul className="list">
          {meds.data?.map((m) => (
            <li key={m.id} className="list-item">
              {editing === m.id ? (
                <MedForm initial={m} idPrefix={`edit${m.id}`} submitLabel="Save changes" onCancel={() => setEditing(null)}
                  onSubmit={(v) => guard(() => api.editMedication(m.id, v), `Update ${m.name}`)} />
              ) : (
                <>
                  <div>
                    <strong>{m.name}</strong> {m.dose}
                    <div className="muted">
                      {m.times.length}x daily at {m.times.join(", ")}{m.instructions ? ` - ${m.instructions}` : ""}
                    </div>
                    <div className="muted">
                      From {m.start_date}{m.end_date ? ` to ${m.end_date}` : ""} &middot;{" "}
                      <span className={m.stock <= m.low_stock_threshold ? "badge badge-missed" : ""}>
                        {m.stock} in stock{m.stock <= m.low_stock_threshold ? " (low)" : ""}
                      </span>
                    </div>
                  </div>
                  {canEdit && (
                    <div className="row">
                      <button className="btn btn-secondary" onClick={() => setEditing(m.id)} aria-label={`Edit ${m.name}`}>Edit</button>
                      <button className="btn btn-danger" onClick={() => void remove(m)} aria-label={`Stop ${m.name}`}>Stop</button>
                    </div>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
        {meds.data?.length === 0 && <p className="muted">No medications yet.</p>}
      </section>

      {canEdit && (
        <section className="card" aria-labelledby="ai-h">
          <h2 id="ai-h">Add from a prescription photo <span className="badge">AI, optional</span></h2>
          <p className="muted">
            Upload a clear photo. AI will suggest a draft that you must review and confirm. It can make mistakes. {DISCLAIMER}
          </p>
          <div className="field">
            <label htmlFor="rx-file">Prescription photo (JPEG, PNG or WebP, up to 5 MB)</label>
            <input id="rx-file" type="file" accept="image/jpeg,image/png,image/webp" disabled={aiBusy} onChange={(e) => void upload(e)} />
          </div>
          {aiBusy && <p role="status">Reading the prescription...</p>}
          {drafts.map((d, i) => (
            <div key={`${d.name}-${i}`} className="subcard">
              <h3>Draft {i + 1}: check every field before saving</h3>
              <MedForm initial={d} idPrefix={`draft${i}`} submitLabel="Confirm and save"
                onCancel={() => setDrafts(drafts.filter((_, j) => j !== i))}
                onSubmit={async (m) => {
                  await guard(() => api.addMedication(m), `Add ${m.name}`);
                  setDrafts((cur) => cur.filter((_, j) => j !== i));
                }} />
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
