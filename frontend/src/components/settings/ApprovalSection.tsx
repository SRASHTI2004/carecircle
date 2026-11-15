import { api } from "../../api";
import type { Me } from "../../types";
import type { Notify } from "../../util";

interface Props {
  me: Me;
  notify: Notify;
  onChanged: () => void;
}

/** The elder's "require my approval" switch. Only the elder can change it. */
export function ApprovalSection({ me, notify, onChanged }: Props) {
  async function toggle(value: boolean) {
    try {
      await api.setApproval(value);
      notify(value ? "Others' changes now need your approval." : "Changes by others apply immediately.");
      onChanged();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save.", "error");
    }
  }

  return (
    <section className="card" aria-labelledby="appr-h">
      <h2 id="appr-h">{me.profile.name} decides</h2>
      <div className="check">
        <input
          id="approval"
          type="checkbox"
          checked={me.profile.require_approval}
          disabled={me.role !== "elder"}
          onChange={(e) => void toggle(e.target.checked)}
          aria-describedby="approval-help"
        />
        <label htmlFor="approval">Require the elder's approval before others' changes take effect</label>
      </div>
      <p id="approval-help" className="muted">
        {me.role === "elder"
          ? 'When on, changes by caretakers appear as "pending elder approval" until you approve them. Your own changes always apply at once.'
          : "Only the elder can change this setting."}
      </p>
    </section>
  );
}
