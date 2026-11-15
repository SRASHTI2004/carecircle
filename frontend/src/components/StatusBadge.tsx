import type { DoseStatus } from "../types";
import { STATUS_ICON, STATUS_LABEL } from "../util";

/** Status is shown with an icon AND text AND colour, never colour alone. */
export function StatusBadge({ status }: { status: DoseStatus }) {
  return (
    <span className={`badge badge-${status}`}>
      <span aria-hidden="true">{STATUS_ICON[status]} </span>
      {STATUS_LABEL[status]}
    </span>
  );
}
