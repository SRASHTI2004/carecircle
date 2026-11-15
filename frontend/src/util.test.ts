import { describe, expect, it } from "vitest";
import { doseSentence, readAloudText } from "./components/ElderMode";
import type { Dose } from "./types";
import { firstName, formatTime, groupDoses, isTaken } from "./util";

const dose = (over: Partial<Dose> = {}): Dose => ({
  medication_id: 1,
  name: "Metformin",
  dose: "500 mg",
  instructions: "After food",
  kind: "medicine",
  scheduled_at: "2025-03-03T08:00",
  status: "upcoming",
  logged_by: null,
  logged_at: null,
  ...over,
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
    const text = readAloudText("Margaret", [
      dose({ status: "taken_on_time" }),
      dose({ scheduled_at: "2025-03-03T20:00" }),
    ]);
    expect(text).toContain("Hello Margaret");
    expect(text).toContain("2 doses, and 1 still to take");
  });

  it("handles an empty day", () => {
    expect(readAloudText("Margaret", [])).toContain("no medicines");
  });
});

describe("groupDoses", () => {
  const now = "2025-03-03T12:00";
  it("puts due, missed and the next 3 hours in 'now', later ones in 'later', finished ones in 'done'", () => {
    const g = groupDoses(
      [
        dose({ scheduled_at: "2025-03-03T08:00", status: "taken_on_time" }),
        dose({ scheduled_at: "2025-03-03T09:00", status: "missed" }),
        dose({ scheduled_at: "2025-03-03T11:50", status: "due" }),
        dose({ scheduled_at: "2025-03-03T14:59", status: "upcoming" }),
        dose({ scheduled_at: "2025-03-03T15:01", status: "upcoming" }),
        dose({ scheduled_at: "2025-03-03T07:00", status: "skipped" }),
      ],
      now,
    );
    expect(g.now.map((d) => d.scheduled_at.slice(11))).toEqual(["09:00", "11:50", "14:59"]);
    expect(g.later.map((d) => d.scheduled_at.slice(11))).toEqual(["15:01"]);
    expect(g.done).toHaveLength(2);
  });
});

describe("firstName", () => {
  it("uses the first word", () => {
    expect(firstName("Margaret Sharma")).toBe("Margaret");
    expect(firstName("  Joe ")).toBe("Joe");
  });
});
