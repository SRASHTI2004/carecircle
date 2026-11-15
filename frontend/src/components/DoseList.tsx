import { useState } from "react";
import { api } from "../api";
import type { Dose } from "../types";
import { firstName, formatTime, groupDoses, isTaken, Notify, ROLE_LABEL } from "../util";
import { StatusBadge } from "./StatusBadge";

interface Props {
  doses: Dose[];
  /** Local "now" from the server, used to group doses (e.g. "2025-03-03T12:00"). */
  now: string;
  elderName: string;
  canLog: boolean;
  large?: boolean;
  notify: Notify;
  onChanged: () => void;
}

function who(d: Dose, elderName: string): string {
  if (!d.logged_by) return "";
  return d.logged_by === "elder" ? firstName(elderName) : ROLE_LABEL[d.logged_by as keyof typeof ROLE_LABEL];
}

/** Today's doses grouped into Now and next, Later today and Done today, with Taken, Skip and Undo actions. */
export function DoseList({ doses, now, elderName, canLog, large, notify, onChanged }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const keyOf = (d: Dose) => `${d.medication_id}-${d.scheduled_at}`;

  async function act(d: Dose, action: "taken" | "skipped" | "undo") {
    setBusy(keyOf(d));
    try {
      await api.logDose(d.medication_id, d.scheduled_at, action);
      const word = d.kind === "routine" ? "done" : "taken";
      notify(
        action === "undo"
          ? `${d.name} is back on the list.`
          : `${d.name} marked as ${action === "taken" ? word : "skipped"}.`,
      );
      onChanged();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    } finally {
      setBusy(null);
    }
  }

  if (doses.length === 0) return <p className="muted">Nothing scheduled for today.</p>;

  const groups = groupDoses(doses, now);
  const sections: { id: string; title: string; items: Dose[] }[] = [
    { id: "now", title: "Now and next", items: groups.now },
    { id: "later", title: "Later today", items: groups.later },
    { id: "done", title: "Done today", items: groups.done },
  ];

  function card(d: Dose, compact = false) {
    const key = keyOf(d);
    const finished = isTaken(d.status) || d.status === "skipped";
    const doneWord = d.kind === "routine" ? "Done" : "Taken";
    return (
      <li key={key} className={`dose status-${d.status}${compact ? " compact" : ""}`}>
        <div className="dose-main">
          <div className="dose-time">{formatTime(d.scheduled_at)}</div>
          <div className="dose-body">
            <div className="dose-title">
              <strong>{d.name}</strong> {d.dose && <span className="dose-amount">{d.dose}</span>}
              {d.kind === "routine" && <span className="tag">Routine</span>}
            </div>
            {d.instructions && <div className="muted">{d.instructions}</div>}
          </div>
          <StatusBadge status={d.status} />
        </div>
        {finished ? (
          <p className="dose-done-line">
            <span aria-hidden="true">{d.status === "skipped" ? "⏭" : "✓"} </span>
            {d.status === "skipped" ? "Skipped" : doneWord}
            {d.logged_at ? ` at ${formatTime(d.logged_at)}` : ""}
            {who(d, elderName) ? ` by ${who(d, elderName)}` : ""}
            {canLog && (
              <button
                className="btn-link"
                disabled={busy === key}
                onClick={() => void act(d, "undo")}
                aria-label={`Undo ${d.name} at ${formatTime(d.scheduled_at)}`}
              >
                Undo
              </button>
            )}
          </p>
        ) : (
          canLog &&
          (compact ? (
            <p className="dose-done-line">
              <button
                className="btn-link"
                disabled={busy === key}
                onClick={() => void act(d, "taken")}
                aria-label={`Mark ${d.name} at ${formatTime(d.scheduled_at)} as ${d.kind === "routine" ? "done" : "taken"}`}
              >
                Mark as {doneWord.toLowerCase()} early
              </button>
            </p>
          ) : (
            <div className="dose-actions">
              <button
                className="btn btn-primary"
                disabled={busy === key}
                onClick={() => void act(d, "taken")}
                aria-label={`Mark ${d.name} at ${formatTime(d.scheduled_at)} as ${d.kind === "routine" ? "done" : "taken"}`}
              >
                {doneWord}
              </button>
              <button
                className="btn btn-secondary"
                disabled={busy === key}
                onClick={() => void act(d, "skipped")}
                aria-label={`Skip ${d.name} at ${formatTime(d.scheduled_at)}`}
              >
                Skip
              </button>
            </div>
          ))
        )}
      </li>
    );
  }

  return (
    <div className={`dose-groups${large ? " large" : ""}`}>
      {groups.now.length === 0 && groups.later.length === 0 && (
        <p className="all-done" role="status">
          Everything for today is done. Well done!
        </p>
      )}
      {sections
        .filter((s) => s.items.length > 0)
        .map((s) => (
          <section key={s.id} aria-labelledby={`grp-${s.id}${large ? "-big" : ""}`}>
            <h3 id={`grp-${s.id}${large ? "-big" : ""}`} className="group-title">
              {s.title} <span className="group-count">{s.items.length}</span>
            </h3>
            <ul className="doses" aria-label={s.title}>
              {s.items.map((d) => card(d, s.id !== "now"))}
            </ul>
          </section>
        ))}
    </div>
  );
}
