export type Role = "elder" | "caretaker" | "family";

export interface Me {
  role: Role;
  profile: { id: number; name: string; timezone: string; require_approval: boolean };
  pending_count: number;
  can_edit: boolean;
}

export type Kind = "medicine" | "routine";
export type NotifyType = "dose_upcoming" | "dose_missed" | "routine" | "appointment" | "low_stock" | "wellbeing";
export type Mood = "good" | "okay" | "unwell";

export interface Medication {
  id: number;
  kind: Kind;
  name: string;
  dose: string;
  times: string[];
  start_date: string;
  end_date: string | null;
  instructions: string;
  stock: number;
  low_stock_threshold: number;
}

export type MedicationInput = Omit<Medication, "id">;

export type DoseStatus = "upcoming" | "due" | "taken_on_time" | "taken_late" | "skipped" | "missed";

export interface Dose {
  medication_id: number;
  name: string;
  dose: string;
  instructions: string;
  kind: Kind;
  scheduled_at: string;
  status: DoseStatus;
  logged_by: string | null;
}

export interface Appointment {
  id: number;
  doctor: string;
  place: string;
  starts_at: string;
  notes: string;
}

export type AppointmentInput = Omit<Appointment, "id">;

export interface Weekly {
  days: number;
  percent: number | null;
  counts: Record<string, number>;
  total: number;
  missed_by_medicine: Record<string, number>;
  daily: { date: string; percent: number | null; total: number }[];
  by_medicine: { name: string; percent: number | null; total: number; missed: number }[];
}

export interface Pending {
  id: number;
  entity: string;
  op: string;
  summary: string;
  requested_by: Role;
  created_at: string;
}

export interface Activity {
  actor_role: Role;
  action: string;
  detail: string;
  created_at: string;
}

export interface Comment {
  role: Role;
  text: string;
  created_at: string;
}

export interface Contact {
  id: number;
  name: string;
  email: string;
  role: Role;
  notify: NotifyType[];
}

export interface PasscodeInfo {
  role: Role;
  active: boolean;
  can_manage: boolean;
}

export interface Emergency {
  name: string;
  blood_group: string;
  allergies: string;
  conditions: string;
  doctor_name: string;
  doctor_phone: string;
  emergency_contacts: string;
  notes: string;
  updated_at: string;
  medicines: { name: string; dose: string; instructions: string; times: string[] }[];
  contacts: { name: string; email: string; role: Role }[];
  can_edit: boolean;
}

export type EmergencyInput = Pick<
  Emergency,
  "blood_group" | "allergies" | "conditions" | "doctor_name" | "doctor_phone" | "emergency_contacts" | "notes"
>;

export interface Checkin {
  mood: Mood;
  note: string;
  logged_by: Role;
  created_at: string;
}

export interface OutboxEmail {
  id: number;
  to_email: string;
  subject: string;
  body: string;
  delivered: number;
  error: string;
  created_at: string;
}

export interface ChangeResult {
  status: "applied" | "pending";
  id: number;
}

export interface AiDraftResponse {
  ok: boolean;
  message: string;
  drafts: MedicationInput[];
  disclaimer: string;
}

export interface SummaryResponse {
  summary: string;
  source: "ai" | "facts";
  message: string;
  disclaimer: string;
}
