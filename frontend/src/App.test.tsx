import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { violations } from "./test/a11y";
import { installApi } from "./test/mockApi";
import type { Role } from "./types";

beforeEach(() => {
  sessionStorage.clear();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(cleanup);

async function signInAs(role: Role) {
  const calls = installApi(role);
  const user = userEvent.setup();
  const view = render(<App />);
  await user.click(screen.getByRole("button", { name: new RegExp(`Try as ${role}`, "i") }));
  return { calls, user, view };
}

describe("Landing and login", () => {
  it("explains the product, shows the passcode form and demo passcodes, with no a11y violations", async () => {
    installApi("elder");
    const { container } = render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/elder at the centre/i);
    expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
    expect(screen.getByText("DEMO-FAMILY24")).toBeInTheDocument();
    expect(await violations(container)).toEqual([]);
  });

  it("one-click buttons sign in with the matching demo passcode", async () => {
    const { calls } = await signInAs("caretaker");
    expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({ passcode: "DEMO-CARER24" });
    expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });

  it("shows the server's message for a wrong passcode", async () => {
    installApi("elder", {
      "POST /auth/login": () => ({ status: 401, body: { detail: "That passcode is not correct." } }),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Passcode"), "WRONG-1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not correct");
  });
});

describe("Elder mode", () => {
  it("lands in elder mode with big buttons, read aloud, check-in and no a11y violations", async () => {
    const { view } = await signInAs("elder");
    expect(await screen.findByRole("heading", { name: /Hello, Margaret Sharma/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Read today's medicines aloud/ })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Mark Evening walk at 5:30 PM as done/ })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Choose how you feel" })).toBeInTheDocument();
    expect(await screen.findByText(/Dr. Rao/)).toBeInTheDocument();
    expect(await violations(view.container)).toEqual([]);
  });

  it("marking a routine done calls the API", async () => {
    const { calls, user } = await signInAs("elder");
    await user.click(await screen.findByRole("button", { name: /Mark Evening walk at 5:30 PM as done/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/doses")).toBe(true));
    expect(calls.find((c) => c.path === "/doses")?.body).toMatchObject({ medication_id: 3, action: "taken" });
  });

  it("a one-tap check-in is sent", async () => {
    const { calls, user } = await signInAs("elder");
    await user.click(await screen.findByRole("button", { name: /Not well/ }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/checkins" && c.method === "POST")?.body).toEqual({
        mood: "unwell",
        note: "",
      }),
    );
  });

  it("uses speech synthesis for read aloud", async () => {
    const speak = vi.fn();
    vi.stubGlobal("speechSynthesis", { speak, cancel: vi.fn() });
    vi.stubGlobal(
      "SpeechSynthesisUtterance",
      class {
        constructor(public text: string) {}
      },
    );
    const { user } = await signInAs("elder");
    await screen.findByText("Evening walk");
    await user.click(screen.getByRole("button", { name: /Read today's medicines aloud/ }));
    expect(speak).toHaveBeenCalledTimes(1);
    expect((speak.mock.calls[0][0] as { text: string }).text).toContain("Metformin");
  });
});

describe("Elder mode redesign", () => {
  it("groups doses, shows a calm taken line with Undo, and only pending doses have Taken/Skip", async () => {
    const { calls, user } = await signInAs("elder");
    await screen.findByRole("heading", { name: /Now and next/ });
    expect(screen.getByRole("heading", { name: /Later today/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Done today/ })).toBeInTheDocument();
    expect(screen.getByText(/Taken at 8:02 AM by Margaret/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Mark Metformin at 8:00 AM as taken/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Mark Amlodipine at 9:00 AM as taken/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Undo Metformin at 8:00 AM/ }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/doses")?.body).toMatchObject({ medication_id: 1, action: "undo" }),
    );
  });

  it("defaults to the light theme; the Dark theme switch changes and remembers it, with no a11y violations", async () => {
    localStorage.clear();
    const { user, view } = await signInAs("elder");
    await screen.findByRole("heading", { name: /Now and next/ });
    const root = view.container.querySelector(".elder");
    expect(root).toHaveAttribute("data-theme", "light");
    const toggle = screen.getByRole("switch", { name: /Dark theme/ });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await user.click(toggle);
    expect(root).toHaveAttribute("data-theme", "dark");
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(localStorage.getItem("carecircle.theme")).toBe("dark");
    expect(await violations(view.container)).toEqual([]);
    await user.click(toggle);
    expect(root).toHaveAttribute("data-theme", "light");
  });
});

describe("Standard view", () => {
  it("caretaker: every tab renders with no a11y violations", async () => {
    const { user, view } = await signInAs("caretaker");
    await screen.findByRole("heading", { name: "Today" });
    const tabs = [
      "Today",
      "Medicines & routines",
      "Appointments",
      "Care circle",
      "Emergency card",
      "Email reminders",
      "Settings",
    ];
    for (const tab of tabs) {
      await user.click(screen.getByRole("button", { name: tab }));
      await screen.findAllByRole("heading", { level: 2 });
      await waitFor(() => expect(screen.queryByText(/^Loading/)).toBeNull());
      expect(await violations(view.container), tab).toEqual([]);
    }
  });

  it("family sees no add/edit buttons and no Taken/Skip", async () => {
    const { user } = await signInAs("family");
    await screen.findByRole("heading", { name: "Today" });
    expect(screen.queryByRole("button", { name: /Mark .* as taken/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Medicines & routines" }));
    expect(await screen.findByText(/Only the elder and caretakers can change them/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add medicine" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Appointments" }));
    expect(screen.queryByRole("button", { name: "Add appointment" })).toBeNull();
  });

  it("duplicate medicine asks for confirmation, then resends with allow_duplicate", async () => {
    let n = 0;
    const calls = installApi("caretaker", {
      "POST /medications": () =>
        n++ === 0
          ? {
              status: 409,
              body: { detail: "'Metformin' is already on the list. Adding it twice can mean a double dose." },
            }
          : { status: 201, body: { status: "applied", id: 9 } },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Try as caretaker/i }));
    await user.click(await screen.findByRole("button", { name: "Medicines & routines" }));
    await user.click(await screen.findByRole("button", { name: "Add medicine" }));
    await user.type(screen.getByLabelText("Medicine name"), "Metformin");
    await user.type(screen.getByLabelText(/^Dose/), "500 mg");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "POST" && c.path.startsWith("/medications")).length).toBe(2),
    );
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("already on the list"));
    expect(calls.filter((c) => c.method === "POST" && c.path.startsWith("/medications")).at(-1)?.path).toContain(
      "allow_duplicate=true",
    );
  });

  it("elder can open the doctor view of the emergency card", async () => {
    const { user } = await signInAs("elder");
    await user.click(await screen.findByRole("button", { name: "Standard view" }));
    await user.click(await screen.findByRole("button", { name: "Emergency card" }));
    await user.click(await screen.findByRole("button", { name: "Show to doctor" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Penicillin")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Print" })).toBeInTheDocument();
    expect(await violations(dialog)).toEqual([]);
  });

  it("settings: sends a test email and shows the result", async () => {
    const calls = installApi("elder", {
      "POST /settings/test-email": () => ({
        body: { delivered: false, smtp_configured: false, message: "Added to the demo outbox." },
      }),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Try as elder/i }));
    await user.click(await screen.findByRole("button", { name: "Standard view" }));
    await user.click(await screen.findByRole("button", { name: "Settings" }));
    await user.type(await screen.findByLabelText("Send to"), "judge@example.com");
    await user.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("Added to the demo outbox.")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/settings/test-email")?.body).toEqual({ email: "judge@example.com" });
  });
});
