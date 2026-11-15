import { describe, expect, it } from "vitest";
import { doseSentence, readAloudText } from "./components/ElderMode";
import type { Dose } from "./types";
import { formatTime, isTaken } from "./util";

const dose = (over: Partial<Dose> = {}): Dose => ({
  medication_id: 1, name: "Metformin", dose: "500 mg", instructions: "After food",
  scheduled_at: "2025-03-03T08:00", status: "upcoming", logged_by: null, ...over,
});

describe("formatTime", () => {
  it("formats 12-hour clock", () => {
    expect(formatTime("2025-03-03T00:05")).toBe("12:05 AM");
    expect(formatTime("2025-03-03T08:00")).toBe("8:00 AM");
    expect(formatTime("2025-03-03T12:30")).toBe("12:30 PM");
    expect(formatTime("2025-03-03T21:30")).toBe("9:30 PM");
  });
});

describe("isTaken", () => {
  it("is true only for taken statuses", () => {
    expect(isTaken("taken_on_time")).toBe(true);
    expect(isTaken("taken_late")).toBe(true);
    expect(isTaken("missed")).toBe(false);
    expect(isTaken("skipped")).toBe(false);
  });
});

describe("read aloud text", () => {
  it("describes a dose with its instructions and state", () => {
    expect(doseSentence(dose())).toBe("At 8:00 AM, Metformin, 500 mg. After food.");
    expect(doseSentence(dose({ status: "taken_on_time" }))).toContain("Already taken.");
  });

  it("summarises how many doses are still to take", () => {
    const text = readAloudText("Margaret", [dose({ status: "taken_on_time" }), dose({ scheduled_at: "2025-03-03T20:00" })]);
    expect(text).toContain("Hello Margaret");
    expect(text).toContain("2 doses, and 1 still to take");
  });

  it("handles an empty day", () => {
    expect(readAloudText("Margaret", [])).toContain("no medicines");
  });
});
