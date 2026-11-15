import { api } from "../api";
import type { Me } from "../types";
import { Notify, useLoad } from "../util";
import { AdherenceChart } from "./AdherenceChart";
import { CheckinCard } from "./CheckinCard";
import { DoseList } from "./DoseList";

interface Props {
  me: Me;
  notify: Notify;
}

/** Today screen: doses, wellbeing check-in and weekly adherence with chart. */
export function TodayTab({ me, notify }: Props) {
  const today = useLoad(api.today, 60_000);
  const weekly = useLoad(api.weekly);
  const canLog = me.role !== "family";
  const refresh = () => {
    void today.reload();
    void weekly.reload();
  };
  const pct = weekly.data?.percent;

  return (
    <div className="stack">
      <section className="card" aria-labelledby="today-h">
        <h2 id="today-h">Today</h2>
        {today.loading && <p role="status">Loading today's doses...</p>}
        {today.error && (
          <p role="alert" className="error">
            {today.error}{" "}
            <button className="btn-link" onClick={() => void today.reload()}>
              Try again
            </button>
          </p>
        )}
        {today.data && (
          <DoseList
            doses={today.data.doses}
            now={today.data.now}
            elderName={me.profile.name}
            canLog={canLog}
            notify={notify}
            onChanged={refresh}
          />
        )}
        {!canLog && <p className="muted">Family members can view doses but not change them.</p>}
      </section>

      <CheckinCard me={me} notify={notify} />

      <section className="card" aria-labelledby="week-h">
        <h2 id="week-h">This week's adherence</h2>
        {weekly.loading && <p role="status">Loading...</p>}
        {weekly.error && (
          <p role="alert" className="error">
            {weekly.error}
          </p>
        )}
        {weekly.data && pct == null && <p className="muted">Not enough data yet. Mark a few doses to see your week.</p>}
        {weekly.data && pct != null && (
          <div className="grid-2 align-start">
            <div>
              <p className="big-number" aria-label={`${pct} percent of doses taken this week`}>
                {pct}%
              </p>
              <div
                className="meter"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Weekly adherence"
              >
                <div className="meter-fill" style={{ width: `${pct}%` }} />
              </div>
              <p className="muted">
                {weekly.data.counts.taken_on_time} on time, {weekly.data.counts.taken_late} late,{" "}
                {weekly.data.counts.skipped} skipped, {weekly.data.counts.missed} missed
              </p>
            </div>
            <AdherenceChart weekly={weekly.data} />
          </div>
        )}
        {weekly.data && weekly.data.by_medicine.length > 0 && (
          <>
            <h3>By medicine or routine</h3>
            <ul className="list compact">
              {weekly.data.by_medicine.map((m) => (
                <li key={m.name} className="list-item">
                  <span>
                    <strong>{m.name}</strong>
                    {m.missed > 0 && <span className="muted"> ({m.missed} missed)</span>}
                  </span>
                  <span className="pct">{m.percent === null ? "n/a" : `${m.percent}%`}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}
