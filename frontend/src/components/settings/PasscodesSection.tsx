import { useState } from "react";
import { api } from "../../api";
import type { Me, Role } from "../../types";
import { Notify, ROLE_LABEL, useLoad } from "../../util";

/** Create a new passcode for a role (signs that role out) or turn it off. */
export function PasscodesSection({ me, notify }: { me: Me; notify: Notify }) {
  const passcodes = useLoad(api.passcodes);
  const [fresh, setFresh] = useState<{ role: Role; passcode: string } | null>(null);

  async function rotate(role: Role) {
    if (
      !window.confirm(
        `Create a new ${ROLE_LABEL[role]} passcode? The old one stops working and that role is signed out.`,
      )
    )
      return;
    try {
      const r = await api.rotatePasscode(role);
      setFresh({ role, passcode: r.passcode });
      void passcodes.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  async function revoke(role: Role) {
    if (
      !window.confirm(
        `Turn off the ${ROLE_LABEL[role]} passcode? Nobody can sign in with it until you create a new one.`,
      )
    )
      return;
    try {
      await api.revokePasscode(role);
      notify(`${ROLE_LABEL[role]} passcode turned off.`);
      void passcodes.reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  return (
    <section className="card" aria-labelledby="pass-h">
      <h2 id="pass-h">Passcodes</h2>
      <p className="muted">
        {me.role === "elder"
          ? "Create a new passcode if one is shared with the wrong person, or turn one off."
          : "You can manage the family passcode."}
      </p>
      {fresh && (
        <div className="subcard" role="status">
          New {ROLE_LABEL[fresh.role]} passcode: <code>{fresh.passcode}</code>
          <p className="muted">Share it now. It is shown only once.</p>
        </div>
      )}
      {passcodes.error && (
        <p role="alert" className="error">
          {passcodes.error}
        </p>
      )}
      <ul className="list">
        {passcodes.data?.map((p) => (
          <li key={p.role} className="list-item">
            <div>
              <strong>{ROLE_LABEL[p.role]}</strong>{" "}
              <span className={`badge ${p.active ? "badge-taken_on_time" : "badge-missed"}`}>
                {p.active ? "On" : "Turned off"}
              </span>
            </div>
            {p.can_manage && (
              <div className="row wrap">
                <button
                  className="btn btn-secondary"
                  onClick={() => void rotate(p.role)}
                  aria-label={`Create a new ${ROLE_LABEL[p.role]} passcode`}
                >
                  New passcode
                </button>
                {p.role !== me.role && p.active && (
                  <button
                    className="btn btn-danger"
                    onClick={() => void revoke(p.role)}
                    aria-label={`Turn off the ${ROLE_LABEL[p.role]} passcode`}
                  >
                    Turn off
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
