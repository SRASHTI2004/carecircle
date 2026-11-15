import { useState } from "react";
import { api } from "../api";
import type { Dose } from "../types";
import { formatTime, isTaken, Notify, STATUS_LABEL } from "../util";

interface Props {
  doses: Dose[];
  canLog: boolean;
  large?: boolean;
  notify: Notify;
  onChanged: () => void;
}

export function DoseList({ doses, canLog, large, notify, onChanged }: Props) {
  const [busy, setBusy] = useState<string | null>(null);

  async function act(d: Dose, action: "taken" | "skipped") {
    const key = `${d.medication_id}-${d.scheduled_at}`;
    setBusy(key);
    try {
      await api.logDose(d.medication_id, d.scheduled_at, action);
      notify(`${d.name} marked as ${action === "taken" ? "taken" : "skipped"}.`);
      onChanged();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    } finally {
      setBusy(null);
    }
  }

  if (doses.length === 0) return <p className="muted">No doses scheduled for today.</p>;

  return (
    <ul className={`doses${large ? " large" : ""}`} aria-label="Today's doses">
      {doses.map((d) => {
        const key = `${d.medication_id}-${d.scheduled_at}`;
        const done = isTaken(d.status) || d.status === "skipped";
        return (
          <li key={key} className={`dose status-${d.status}`}>
            <div className="dose-time">{formatTime(d.scheduled_at)}</div>
            <div className="dose-body">
              <strong>{d.name}</strong> <span>{d.dose}</span>
              {d.instructions && <div className="muted">{d.instructions}</div>}
              <span className={`badge badge-${d.status}`}>{STATUS_LABEL[d.status]}</span>
              {d.logged_by && done && <span className="muted"> (by {d.logged_by})</span>}
            </div>
            {canLog && (
              <div className="dose-actions">
                <button
                  className="btn btn-primary"
                  disabled={busy === key || isTaken(d.status)}
                  onClick={() => void act(d, "taken")}
                  aria-label={`Mark ${d.name} at ${formatTime(d.scheduled_at)} as taken`}
                >
                  Taken
                </button>
                <button
                  className="btn btn-secondary"
                  disabled={busy === key || d.status === "skipped"}
                  onClick={() => void act(d, "skipped")}
                  aria-label={`Skip ${d.name} at ${formatTime(d.scheduled_at)}`}
                >
                  Skip
                </button>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
