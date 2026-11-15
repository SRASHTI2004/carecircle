import type { Weekly } from "../types";

const WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "short" });

/** Simple 7-day bar chart (SVG) with a visually hidden table for screen readers. */
export function AdherenceChart({ weekly }: { weekly: Weekly }) {
  const days = weekly.daily;
  const w = 280;
  const h = 120;
  const bar = w / days.length;
  return (
    <figure className="chart">
      <figcaption className="muted">Adherence by day, last 7 days</figcaption>
      <svg
        viewBox={`0 0 ${w} ${h + 22}`}
        role="img"
        aria-label="Bar chart of the percentage of doses taken each day for the last 7 days"
      >
        <line x1="0" y1={h} x2={w} y2={h} stroke="currentColor" strokeWidth="1" opacity="0.4" />
        {days.map((d, i) => {
          const pct = d.percent ?? 0;
          const barH = ((h - 20) * pct) / 100;
          const label = WEEKDAY.format(new Date(`${d.date}T12:00:00`));
          return (
            <g key={d.date}>
              {d.percent === null ? (
                <text
                  x={i * bar + bar / 2}
                  y={h - 6}
                  textAnchor="middle"
                  fontSize="11"
                  fill="currentColor"
                  opacity="0.7"
                >
                  n/a
                </text>
              ) : (
                <>
                  <rect
                    x={i * bar + 6}
                    y={h - barH}
                    width={bar - 12}
                    height={barH}
                    rx="4"
                    className={pct >= 80 ? "bar-good" : pct >= 50 ? "bar-mid" : "bar-low"}
                  />
                  <text
                    x={i * bar + bar / 2}
                    y={h - barH - 4}
                    textAnchor="middle"
                    fontSize="11"
                    fill="currentColor"
                    fontWeight="700"
                  >
                    {pct}%
                  </text>
                </>
              )}
              <text x={i * bar + bar / 2} y={h + 15} textAnchor="middle" fontSize="11" fill="currentColor">
                {label}
              </text>
            </g>
          );
        })}
      </svg>
      <table className="sr-only">
        <caption>Adherence by day</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Percent taken</th>
            <th scope="col">Doses</th>
          </tr>
        </thead>
        <tbody>
          {days.map((d) => (
            <tr key={d.date}>
              <th scope="row">{d.date}</th>
              <td>{d.percent === null ? "no doses" : `${d.percent}%`}</td>
              <td>{d.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
