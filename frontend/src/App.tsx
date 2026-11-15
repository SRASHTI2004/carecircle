import { useCallback, useEffect, useState } from "react";
import { api, tokenStore } from "./api";
import { AppointmentsTab } from "./components/AppointmentsTab";
import { CareTab } from "./components/CareTab";
import { ElderMode } from "./components/ElderMode";
import { EmergencyTab } from "./components/EmergencyTab";
import { Login } from "./components/Login";
import { MedicationsTab } from "./components/MedicationsTab";
import { OutboxTab } from "./components/OutboxTab";
import { PendingPanel } from "./components/PendingPanel";
import { SettingsTab } from "./components/SettingsTab";
import { TodayTab } from "./components/TodayTab";
import type { Me, Role } from "./types";
import { DISCLAIMER, Notify, ROLE_LABEL } from "./util";

type Tab = "today" | "meds" | "appts" | "care" | "emergency" | "inbox" | "settings";
const TABS: { id: Tab; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "meds", label: "Medicines & routines" },
  { id: "appts", label: "Appointments" },
  { id: "care", label: "Care circle" },
  { id: "emergency", label: "Emergency card" },
  { id: "inbox", label: "Email reminders" },
  { id: "settings", label: "Settings" },
];

/** Application shell: session handling, navigation tabs and Elder mode switching. */
export function App() {
  const [authed, setAuthed] = useState<boolean>(() => tokenStore.get() !== null);
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [elderMode, setElderMode] = useState(false);
  const [version, setVersion] = useState(0);
  const [toast, setToast] = useState<{ text: string; kind: "ok" | "error" } | null>(null);

  const notify: Notify = useCallback((text, kind = "ok") => {
    setToast({ text, kind });
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), 6000);
  }, []);

  const loadMe = useCallback(async () => {
    try {
      setMe(await api.me());
    } catch {
      tokenStore.set(null);
      setAuthed(false);
      setMe(null);
    }
  }, []);

  useEffect(() => {
    if (authed) void loadMe();
  }, [authed, loadMe]);

  const pendingChanged = useCallback(() => {
    setVersion((v) => v + 1);
    void loadMe();
  }, [loadMe]);

  function onLogin(token: string, role: Role) {
    tokenStore.set(token);
    setElderMode(role === "elder");
    setTab("today");
    setAuthed(true);
  }

  async function logout() {
    try {
      await api.logout();
    } catch {
      /* already signed out */
    }
    tokenStore.set(null);
    setAuthed(false);
    setMe(null);
    setElderMode(false);
  }

  const toastEl = toast && (
    <div className={`toast ${toast.kind}`} role={toast.kind === "error" ? "alert" : "status"}>
      {toast.text}
    </div>
  );

  if (!authed)
    return (
      <>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <Login onLogin={onLogin} />
        {toastEl}
      </>
    );
  if (!me)
    return (
      <p className="center loading" role="status">
        Loading CareCircle...
      </p>
    );

  if (elderMode) {
    return (
      <main id="main">
        <ElderMode
          me={me}
          notify={notify}
          pendingVersion={version}
          onResolved={pendingChanged}
          onExit={() => setElderMode(false)}
          onLogout={() => void logout()}
        />
        {toastEl}
      </main>
    );
  }

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <h1 className="brand">
          CareCircle <span className="muted">for {me.profile.name}</span>
        </h1>
        <div className="row wrap">
          <span className="badge" aria-label={`Signed in as ${ROLE_LABEL[me.role]}`}>
            {ROLE_LABEL[me.role]}
          </span>
          <button className="btn btn-secondary" onClick={() => setElderMode(true)}>
            Elder mode
          </button>
          <button className="btn btn-secondary" onClick={() => void logout()}>
            Sign out
          </button>
        </div>
      </header>
      <nav aria-label="Main" className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab${tab === t.id ? " active" : ""}`}
            aria-current={tab === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "settings" && me.pending_count > 0 ? (
              <span className="dot" aria-label={`${me.pending_count} waiting for approval`}>
                {me.pending_count}
              </span>
            ) : null}
          </button>
        ))}
      </nav>
      <main id="main" className="page" tabIndex={-1}>
        <PendingPanel me={me} notify={notify} version={version} onResolved={pendingChanged} />
        {tab === "today" && <TodayTab me={me} notify={notify} />}
        {tab === "meds" && <MedicationsTab me={me} notify={notify} onPendingChange={pendingChanged} />}
        {tab === "appts" && <AppointmentsTab me={me} notify={notify} onPendingChange={pendingChanged} />}
        {tab === "care" && <CareTab me={me} notify={notify} />}
        {tab === "emergency" && <EmergencyTab me={me} notify={notify} />}
        {tab === "inbox" && <OutboxTab />}
        {tab === "settings" && <SettingsTab me={me} notify={notify} onChanged={pendingChanged} />}
      </main>
      <footer className="footer">{DISCLAIMER}</footer>
      {toastEl}
    </>
  );
}
