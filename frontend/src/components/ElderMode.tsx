import { useEffect, useState } from "react";
import { api } from "../api";
import type { Dose, Me } from "../types";
import { DISCLAIMER, formatDateTime, formatTime, isTaken, Notify, speak, stopSpeaking, useLoad } from "../util";
import { CheckinCard } from "./CheckinCard";
import { DoseList } from "./DoseList";
import { EmergencyTab } from "./EmergencyTab";
import { PendingPanel } from "./PendingPanel";

interface Props {
  me: Me;
  notify: Notify;
  pendingVersion: number;
  onResolved: () => void;
  onExit: () => void;
  onLogout: () => void;
}

export function doseSentence(d: Dose): string {
  const state = isTaken(d.status)
    ? "Already taken."
    : d.status === "skipped"
      ? "Skipped."
      : d.status === "missed"
        ? "This one was missed."
        : "";
  return `At ${formatTime(d.scheduled_at)}, ${d.name}, ${d.dose}. ${d.instructions ? `${d.instructions}.` : ""} ${state}`
    .replace(/\s+/g, " ")
    .trim();
}

export function readAloudText(name: string, doses: Dose[]): string {
  if (doses.length === 0) return `Hello ${name}. You have no medicines to take today.`;
  const left = doses.filter((d) => d.status === "upcoming" || d.status === "due" || d.status === "missed").length;
  return `Hello ${name}. Today you have ${doses.length} ${doses.length === 1 ? "dose" : "doses"}, and ${left} still to take. ${doses.map(doseSentence).join(" ")}`;
}

export function ElderMode({ me, notify, pendingVersion, onResolved, onExit, onLogout }: Props) {
  const today = useLoad(api.today, 30_000);
  const appts = useLoad(api.appointments);
  const [speaking, setSpeaking] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const canLog = me.role !== "family";
  const next = appts.data?.[0];

  useEffect(() => stopSpeaking, []);

  function readAloud() {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    const text = readAloudText(me.profile.name, today.data?.doses ?? []);
    if (!speak(text)) {
      notify("Your browser cannot read aloud.", "error");
      return;
    }
    setSpeaking(true);
    window.setTimeout(() => setSpeaking(false), Math.min(60_000, text.length * 80));
  }

  return (
    <div className="elder">
      <header className="elder-head">
        <h1>Hello, {me.role === "elder" ? me.profile.name : `${me.profile.name}'s day`}</h1>
        <div className="row wrap">
          <button className="btn btn-big btn-secondary" onClick={onExit}>
            Standard view
          </button>
          <button className="btn btn-big btn-secondary" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </header>

      <button className="btn btn-huge btn-primary" onClick={readAloud} aria-pressed={speaking}>
        {speaking ? "Stop reading" : "Read today's medicines aloud"}
      </button>

      <PendingPanel me={me} notify={notify} large version={pendingVersion} onResolved={onResolved} />

      <section aria-labelledby="e-today">
        <h2 id="e-today">Today's medicines and routines</h2>
        {today.loading && <p role="status">Loading...</p>}
        {today.error && (
          <p role="alert" className="error">
            {today.error}
          </p>
        )}
        {today.data && (
          <DoseList
            large
            doses={today.data.doses}
            canLog={canLog}
            notify={notify}
            onChanged={() => void today.reload()}
          />
        )}
      </section>

      <CheckinCard me={me} notify={notify} large />

      <section aria-labelledby="e-appt">
        <h2 id="e-appt">Next doctor visit</h2>
        {next ? (
          <p className="elder-appt">
            <strong>{next.doctor}</strong>
            <br />
            {formatDateTime(next.starts_at)}
            <br />
            {next.place}
          </p>
        ) : (
          <p>No visits planned.</p>
        )}
      </section>
      <button className="btn btn-big btn-secondary" aria-expanded={showCard} onClick={() => setShowCard(!showCard)}>
        {showCard ? "Hide my emergency card" : "My emergency card"}
      </button>
      {showCard && <EmergencyTab me={me} notify={notify} />}
      <p className="elder-note">{DISCLAIMER}</p>
    </div>
  );
}
