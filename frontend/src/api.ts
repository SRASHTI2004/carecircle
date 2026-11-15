import type {
  Activity,
  AiDraftResponse,
  Appointment,
  AppointmentInput,
  ChangeResult,
  Checkin,
  Comment,
  Contact,
  Dose,
  Emergency,
  EmergencyInput,
  Me,
  Medication,
  MedicationInput,
  Mood,
  NotifyType,
  OutboxEmail,
  PasscodeInfo,
  Pending,
  Role,
  SummaryResponse,
  Weekly,
} from "./types";

const TOKEN_KEY = "carecircle.token";

export const tokenStore = {
  get: (): string | null => {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (t: string | null): void => {
    try {
      if (t) sessionStorage.setItem(TOKEN_KEY, t);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable: the session lasts until reload */
    }
  },
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${String(d.loc?.slice(-1)[0] ?? "field")}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return "Something went wrong. Please try again.";
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(describe((data as { detail?: unknown }).detail), res.status);
  return data as T;
}

export const api = {
  login: (passcode: string) => request<{ token: string; role: Role }>("POST", "/auth/login", { passcode }),
  logout: () => request<void>("POST", "/auth/logout"),
  createProfile: (name: string, contacts: { name: string; email: string; role: Role }[]) =>
    request<{ passcodes: Record<Role, string> }>("POST", "/profiles", { name, contacts }),
  me: () => request<Me>("GET", "/me"),
  setApproval: (require_approval: boolean) =>
    request<{ require_approval: boolean }>("PUT", "/settings", { require_approval }),
  today: () => request<{ now: string; doses: Dose[] }>("GET", "/doses/today"),
  logDose: (medication_id: number, scheduled_at: string, action: "taken" | "skipped" | "undo") =>
    request<{ status: string }>("POST", "/doses", { medication_id, scheduled_at, action }),
  weekly: () => request<Weekly>("GET", "/adherence/weekly"),
  medications: () => request<Medication[]>("GET", "/medications"),
  addMedication: (m: MedicationInput, allowDuplicate = false) =>
    request<ChangeResult>("POST", `/medications${allowDuplicate ? "?allow_duplicate=true" : ""}`, m),
  editMedication: (id: number, m: MedicationInput, allowDuplicate = false) =>
    request<ChangeResult>("PUT", `/medications/${id}${allowDuplicate ? "?allow_duplicate=true" : ""}`, m),
  deleteMedication: (id: number) => request<ChangeResult>("DELETE", `/medications/${id}`),
  appointments: () => request<Appointment[]>("GET", "/appointments"),
  addAppointment: (a: AppointmentInput) => request<ChangeResult>("POST", "/appointments", a),
  editAppointment: (id: number, a: AppointmentInput) => request<ChangeResult>("PUT", `/appointments/${id}`, a),
  deleteAppointment: (id: number) => request<ChangeResult>("DELETE", `/appointments/${id}`),
  pending: () => request<Pending[]>("GET", "/pending"),
  decide: (id: number, decision: "approve" | "reject") =>
    request<{ status: string }>("POST", `/pending/${id}/${decision}`),
  activity: (offset = 0) => request<Activity[]>("GET", `/activity?limit=20&offset=${offset}`),
  comments: () => request<Comment[]>("GET", "/comments"),
  addComment: (text: string) => request<{ status: string }>("POST", "/comments", { text }),
  contacts: () => request<Contact[]>("GET", "/contacts"),
  addContact: (c: { name: string; email: string; role: Role }) => request<{ status: string }>("POST", "/contacts", c),
  deleteContact: (id: number) => request<void>("DELETE", `/contacts/${id}`),
  setNotify: (id: number, notify: NotifyType[]) =>
    request<{ notify: NotifyType[] }>("PUT", `/contacts/${id}/notify`, { notify }),
  outbox: (offset = 0) =>
    request<{ smtp_configured: boolean; emails: OutboxEmail[] }>("GET", `/outbox?limit=20&offset=${offset}`),
  testEmail: (email: string) =>
    request<{ delivered: boolean; smtp_configured: boolean; message: string }>("POST", "/settings/test-email", {
      email,
    }),
  passcodes: () => request<PasscodeInfo[]>("GET", "/passcodes"),
  rotatePasscode: (role: Role) => request<{ passcode: string }>("POST", `/passcodes/${role}/rotate`),
  revokePasscode: (role: Role) => request<{ status: string }>("DELETE", `/passcodes/${role}`),
  emergency: () => request<Emergency>("GET", "/emergency"),
  saveEmergency: (e: EmergencyInput) => request<{ status: string }>("PUT", "/emergency", e),
  checkins: () => request<Checkin[]>("GET", "/checkins?limit=14"),
  checkin: (mood: Mood, note: string) => request<{ alerted: number }>("POST", "/checkins", { mood, note }),
  readPrescription: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<AiDraftResponse>("POST", "/ai/prescription", undefined, form);
  },
  weeklySummary: () => request<SummaryResponse>("GET", "/ai/weekly-summary"),
};
