import { api } from "../api";
import type { Me } from "../types";
import { Notify, useLoad } from "../util";
import { DoseList } from "./DoseList";

interface Props {
  me: Me;
  notify: Notify;
}

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
      <section className="card" aria-labelledby="week-h">
        <h2 id="week-h">This week's adherence</h2>
        {pct == null ? (
          <p className="muted">Not enough data yet.</p>
        ) : (
          <>
            <p className="big-number" aria-label={`${pct} percent of doses taken this week`}>{pct}%</p>
            <div className="meter" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Weekly adherence">
              <div className="meter-fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="muted">
              {weekly.data?.counts.taken_on_time} on time, {weekly.data?.counts.taken_late} late,{" "}
              {weekly.data?.counts.skipped} skipped, {weekly.data?.counts.missed} missed (last 7 days)
            </p>
          </>
        )}
      </section>
      <section className="card" aria-labelledby="today-h">
        <h2 id="today-h">Today's doses</h2>
        {today.loading && <p>Loading...</p>}
        {today.error && <p role="alert" className="error">{today.error}</p>}
        {today.data && <DoseList doses={today.data.doses} canLog={canLog} notify={notify} onChanged={refresh} />}
        {!canLog && <p className="muted">Family members can view doses but not change them.</p>}
      </section>
    </div>
  );
}
