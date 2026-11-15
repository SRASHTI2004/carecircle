import { vi } from "vitest";
import type { Role } from "../types";

const today = new Date().toISOString().slice(0, 10);
const slot = (t: string) => `${today}T${t}`;

export const doses = [
  {
    medication_id: 1,
    name: "Metformin",
    dose: "500 mg",
    instructions: "After food",
    kind: "medicine",
    scheduled_at: slot("08:00"),
    status: "taken_on_time",
    logged_by: "elder",
    logged_at: slot("08:02"),
  },
  {
    medication_id: 2,
    name: "Amlodipine",
    dose: "5 mg",
    instructions: "",
    kind: "medicine",
    scheduled_at: slot("09:00"),
    status: "missed",
    logged_by: null,
    logged_at: null,
  },
  {
    medication_id: 3,
    name: "Evening walk",
    dose: "",
    instructions: "20 minutes",
    kind: "routine",
    scheduled_at: slot("17:30"),
    status: "upcoming",
    logged_by: null,
    logged_at: null,
  },
];

const weekly = {
  days: 7,
  percent: 90,
  total: 10,
  counts: { taken_on_time: 8, taken_late: 1, skipped: 0, missed: 1 },
  missed_by_medicine: { Amlodipine: 1 },
  daily: Array.from({ length: 7 }, (_, i) => ({ date: `2025-03-0${i + 1}`, percent: i === 2 ? null : 90, total: 3 })),
  by_medicine: [
    { name: "Amlodipine", percent: 80, total: 5, missed: 1 },
    { name: "Metformin", percent: 100, total: 5, missed: 0 },
  ],
};

const meds = [
  {
    id: 1,
    kind: "medicine",
    name: "Metformin",
    dose: "500 mg",
    times: ["08:00", "20:00"],
    start_date: "2025-01-01",
    end_date: null,
    instructions: "After food",
    stock: 3,
    low_stock_threshold: 5,
  },
  {
    id: 3,
    kind: "routine",
    name: "Evening walk",
    dose: "",
    times: ["17:30"],
    start_date: "2025-01-01",
    end_date: null,
    instructions: "",
    stock: 0,
    low_stock_threshold: 0,
  },
];

const emergency = {
  name: "Margaret Sharma",
  blood_group: "B+",
  allergies: "Penicillin",
  conditions: "Diabetes",
  doctor_name: "Dr. Mehta",
  doctor_phone: "123",
  emergency_contacts: "Priya 999",
  notes: "",
  updated_at: "2025-03-01T10:00:00+00:00",
  medicines: [{ name: "Metformin", dose: "500 mg", instructions: "After food", times: ["08:00", "20:00"] }],
  contacts: [{ name: "Priya", email: "p@x.co", role: "caretaker" }],
  can_edit: true,
};

export interface Calls {
  method: string;
  path: string;
  body?: unknown;
}
type Reply = { status?: number; body: unknown };

/** Install a fetch mock that behaves like the CareCircle API for the given role. */
export function installApi(role: Role, overrides: Record<string, (c: Calls) => Reply> = {}): Calls[] {
  const calls: Calls[] = [];
  const handler = (c: Calls): Reply => {
    const key = `${c.method} ${c.path.split("?")[0]}`;
    if (overrides[key]) return overrides[key](c);
    const table: Record<string, unknown> = {
      "POST /auth/login": { token: "t", role },
      "GET /me": {
        role,
        profile: { id: 1, name: "Margaret Sharma", timezone: "Asia/Kolkata", require_approval: false },
        pending_count: 0,
        can_edit: role !== "family",
      },
      "GET /doses/today": { now: slot("12:00"), doses },
      "GET /adherence/weekly": weekly,
      "GET /appointments": [
        { id: 1, doctor: "Dr. Rao", place: "Apollo Clinic", starts_at: slot("15:00"), notes: "Bring BP log" },
      ],
      "GET /pending": [],
      "GET /checkins": [{ mood: "good", note: "", logged_by: "elder", created_at: "2025-03-01T08:00:00+00:00" }],
      "GET /medications": meds,
      "GET /ai/weekly-summary": {
        summary: "Margaret took 90% of her doses.",
        source: "facts",
        message: "",
        disclaimer: "x",
      },
      "GET /comments": [{ role: "family", text: "Hello Mom", created_at: "2025-03-01T08:00:00+00:00" }],
      "GET /activity": [
        { actor_role: "elder", action: "taken", detail: "Metformin at 08:00", created_at: "2025-03-01T08:00:00+00:00" },
      ],
      "GET /emergency": { ...emergency, can_edit: role === "elder" },
      "GET /outbox": {
        smtp_configured: false,
        emails: [
          {
            id: 1,
            to_email: "a@b.co",
            subject: "Low stock: Metformin",
            body: "Only 3 left",
            delivered: 0,
            error: "",
            created_at: "2025-03-01T08:00:00+00:00",
          },
        ],
      },
      "GET /contacts": [
        { id: 1, name: "Priya", email: "p@x.co", role: "caretaker", notify: ["dose_missed", "appointment"] },
      ],
      "GET /passcodes": [
        { role: "elder", active: true, can_manage: true },
        { role: "caretaker", active: true, can_manage: true },
        { role: "family", active: false, can_manage: true },
      ],
    };
    return { body: key in table ? table[key] : { status: "applied", id: 1 } };
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const c: Calls = {
        method: init?.method ?? "GET",
        path: String(url).replace(/^\/api/, ""),
        body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body,
      };
      calls.push(c);
      const r = handler(c);
      return new Response(JSON.stringify(r.body), {
        status: r.status ?? 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}
