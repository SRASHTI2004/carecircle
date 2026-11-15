import { FormEvent, useState } from "react";
import type { MedicationInput } from "../types";
import { todayIso } from "../util";

/** Blank form values for a new medicine. */
export const EMPTY_MED: MedicationInput = {
  kind: "medicine",
  name: "",
  dose: "",
  times: ["08:00"],
  start_date: todayIso(),
  end_date: null,
  instructions: "",
  stock: 0,
  low_stock_threshold: 5,
};

/** Blank form values for a new daily routine. */
export const EMPTY_ROUTINE: MedicationInput = {
  ...EMPTY_MED,
  kind: "routine",
  times: ["17:00"],
  stock: 0,
  low_stock_threshold: 0,
};

interface Props {
  initial: MedicationInput;
  submitLabel: string;
  idPrefix: string;
  onSubmit: (m: MedicationInput) => Promise<void>;
  onCancel: () => void;
}

/** Add/edit form shared by medicines, routines and AI prescription drafts. */
export function MedForm({ initial, submitLabel, idPrefix, onSubmit, onCancel }: Props) {
  const [m, setM] = useState<MedicationInput>(initial);
  const [busy, setBusy] = useState(false);
  const id = (f: string) => `${idPrefix}-${f}`;
  const routine = m.kind === "routine";

  function setTime(i: number, value: string) {
    setM({ ...m, times: m.times.map((t, j) => (j === i ? value : t)) });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit({ ...m, end_date: m.end_date || null });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={(e) => void submit(e)}>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={id("kind")}>Type</label>
          <select
            id={id("kind")}
            value={m.kind}
            onChange={(e) => setM({ ...m, kind: e.target.value as MedicationInput["kind"] })}
          >
            <option value="medicine">Medicine</option>
            <option value="routine">Daily routine (walk, BP or sugar check, water, physio)</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={id("name")}>{routine ? "Routine name" : "Medicine name"}</label>
          <input
            id={id("name")}
            required
            maxLength={100}
            value={m.name}
            onChange={(e) => setM({ ...m, name: e.target.value })}
          />
        </div>
      </div>
      {!routine && (
        <div className="field">
          <label htmlFor={id("dose")}>Dose (e.g. 500 mg)</label>
          <input
            id={id("dose")}
            required
            maxLength={100}
            value={m.dose}
            onChange={(e) => setM({ ...m, dose: e.target.value })}
          />
        </div>
      )}
      <fieldset className="field">
        <legend>Times each day ({m.times.length} per day)</legend>
        <div className="row wrap">
          {m.times.map((t, i) => (
            <span key={i} className="row">
              <label className="sr-only" htmlFor={id(`time${i}`)}>
                Time {i + 1}
              </label>
              <input id={id(`time${i}`)} type="time" required value={t} onChange={(e) => setTime(i, e.target.value)} />
              {m.times.length > 1 && (
                <button
                  type="button"
                  className="btn btn-link"
                  onClick={() => setM({ ...m, times: m.times.filter((_, j) => j !== i) })}
                >
                  Remove<span className="sr-only"> time {i + 1}</span>
                </button>
              )}
            </span>
          ))}
          {m.times.length < 8 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setM({ ...m, times: [...m.times, "12:00"] })}
            >
              Add a time
            </button>
          )}
        </div>
      </fieldset>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={id("start")}>Start date</label>
          <input
            id={id("start")}
            type="date"
            required
            value={m.start_date}
            onChange={(e) => setM({ ...m, start_date: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={id("end")}>End date (optional)</label>
          <input
            id={id("end")}
            type="date"
            value={m.end_date ?? ""}
            min={m.start_date}
            onChange={(e) => setM({ ...m, end_date: e.target.value || null })}
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor={id("instr")}>
          {routine ? "Notes (e.g. 20 minutes, gentle pace)" : "Instructions (e.g. after food)"}
        </label>
        <input
          id={id("instr")}
          maxLength={300}
          value={m.instructions}
          onChange={(e) => setM({ ...m, instructions: e.target.value })}
        />
      </div>
      {!routine && (
        <div className="grid-2">
          <div className="field">
            <label htmlFor={id("stock")}>Tablets in stock</label>
            <input
              id={id("stock")}
              type="number"
              min={0}
              max={10000}
              required
              value={m.stock}
              onChange={(e) => setM({ ...m, stock: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label htmlFor={id("low")}>Warn me when stock reaches</label>
            <input
              id={id("low")}
              type="number"
              min={0}
              max={1000}
              required
              value={m.low_stock_threshold}
              onChange={(e) => setM({ ...m, low_stock_threshold: Number(e.target.value) })}
            />
          </div>
        </div>
      )}
      <div className="row wrap">
        <button className="btn btn-primary" disabled={busy}>
          {submitLabel}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
