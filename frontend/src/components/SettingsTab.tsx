import type { Me } from "../types";
import type { Notify } from "../util";
import { ApprovalSection } from "./settings/ApprovalSection";
import { ContactsSection } from "./settings/ContactsSection";
import { PasscodesSection } from "./settings/PasscodesSection";
import { TestEmailSection } from "./settings/TestEmailSection";

interface Props {
  me: Me;
  notify: Notify;
  onChanged: () => void;
}

/** Settings screen: composes the approval switch, reminder contacts, test email and passcode sections. */
export function SettingsTab({ me, notify, onChanged }: Props) {
  return (
    <div className="stack">
      <ApprovalSection me={me} notify={notify} onChanged={onChanged} />
      <ContactsSection notify={notify} />
      <TestEmailSection notify={notify} />
      <PasscodesSection me={me} notify={notify} />
    </div>
  );
}
