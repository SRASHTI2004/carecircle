import { useState } from "react";
import { api } from "../api";
import type { Me, Mood } from "../types";
import { MOODS, Notify, formatUtc, useLoad } from "../util";

interface Props {
  me: Me;
  notify: Notify;
  large?: boolean;
}

/** One-tap daily wellbeing check-in. Visible to family; repeated "not well" alerts caretakers by email. */
export function CheckinCard({ me, notify, large }: Props) {
  const list = useLoad(api.checkins);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const canCheckin = me.role !== "family";
  const last = list.data?.[0];

  async function send(mood: Mood) {
    setBusy(true);
    try {
      const r = await api.checkin(mood, note);
      setNote("");
      notify(
        r.alerted > 0 ? "Thank you. Your caretaker has been told you are not well." : "Thank you for checking in.",
      );
      await list.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`card${large ? " large" : ""}`} aria-labelledby={large ? "ci-h-big" : "ci-h"}>
      <h2 id={large ? "ci-h-big" : "ci-h"}>How are you feeling today?</h2>
      {canCheckin ? (
        <>
          <div className="mood-row" role="group" aria-label="Choose how you feel">
            {MOODS.map((m) => (
              <button
                key={m.mood}
                className={`btn mood mood-${m.mood}`}
                disabled={busy}
                onClick={() => void send(m.mood)}
              >
                <span className="mood-icon" aria-hidden="true">
                  {m.icon}
                </span>{" "}
                {m.label}
              </button>
            ))}
          </div>
          <div className="field">
            <label htmlFor={large ? "ci-note-big" : "ci-note"}>Add a note (optional)</label>
            <input
              id={large ? "ci-note-big" : "ci-note"}
              maxLength={300}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </>
      ) : (
        <p className="muted">Only the elder or a caretaker can record a check-in. Family can see the latest answers.</p>
      )}
      {last && (
        <p className="muted" role="status">
          Last check-in: <strong>{MOODS.find((m) => m.mood === last.mood)?.label}</strong> ({formatUtc(last.created_at)}
          ){last.note ? ` - "${last.note}"` : ""}
        </p>
      )}
      {list.data && list.data.length > 1 && (
        <ul className="chips" aria-label="Recent check-ins">
          {list.data.slice(0, 7).map((c, i) => (
            <li key={i} className={`chip mood-${c.mood}`} title={formatUtc(c.created_at)}>
              <span aria-hidden="true">{MOODS.find((m) => m.mood === c.mood)?.icon}</span>
              <span className="sr-only">
                {MOODS.find((m) => m.mood === c.mood)?.label}, {formatUtc(c.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
