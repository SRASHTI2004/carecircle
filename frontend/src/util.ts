import { useCallback, useEffect, useRef, useState } from "react";
import type { DoseStatus, Mood, NotifyType, Role } from "./types";

export const ROLE_LABEL: Record<Role, string> = { elder: "Elder", caretaker: "Caretaker", family: "Family" };

export const STATUS_LABEL: Record<DoseStatus, string> = {
  upcoming: "Upcoming",
  due: "Due now",
  taken_on_time: "Taken on time",
  taken_late: "Taken late",
  skipped: "Skipped",
  missed: "Missed",
};

export const DISCLAIMER = "CareCircle does not give medical advice and does not replace your doctor or pharmacist.";

/** "2025-03-03T08:00" (local wall-clock) -> "8:00 AM" */
export function formatTime(slot: string): string {
  const [h, m] = slot.slice(11, 16).split(":").map(Number);
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

export function formatDateTime(slot: string): string {
  const d = new Date(slot);
  return d.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatUtc(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function isTaken(s: DoseStatus): boolean {
  return s === "taken_on_time" || s === "taken_late";
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export interface Loader<T> {
  data: T | null;
  error: string;
  loading: boolean;
  reload: () => Promise<void>;
}

/** Load data on mount (and every `refreshMs`, if given). */
export function useLoad<T>(fn: () => Promise<T>, refreshMs?: number): Loader<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
    if (!refreshMs) return undefined;
    const id = window.setInterval(() => void reload(), refreshMs);
    return () => window.clearInterval(id);
  }, [reload, refreshMs]);
  return { data, error, loading, reload };
}

export interface Notify {
  (message: string, kind?: "ok" | "error"): void;
}

export function speak(text: string): boolean {
  if (!("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.9;
  window.speechSynthesis.speak(u);
  return true;
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

export const STATUS_ICON: Record<DoseStatus, string> = {
  upcoming: "⏳", // hourglass
  due: "⏰", // alarm clock
  taken_on_time: "✔", // check
  taken_late: "✔",
  skipped: "⏭", // skip
  missed: "⚠", // warning
};

export const NOTIFY_LABEL: Record<NotifyType, string> = {
  dose_upcoming: "Upcoming doses",
  dose_missed: "Missed doses",
  routine: "Routine reminders",
  appointment: "Appointments",
  low_stock: "Low stock",
  wellbeing: "Wellbeing alerts",
};

export const NOTIFY_ALL = Object.keys(NOTIFY_LABEL) as NotifyType[];

export const MOODS: { mood: Mood; label: string; icon: string }[] = [
  { mood: "good", label: "Good", icon: "🙂" },
  { mood: "okay", label: "Okay", icon: "😐" },
  { mood: "unwell", label: "Not well", icon: "🙁" },
];
