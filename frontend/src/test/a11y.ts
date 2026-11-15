import axe from "axe-core";

/** Run axe-core on a container and return readable violations (colour contrast is checked in contrast.test.ts). */
export async function violations(container: Element): Promise<string[]> {
  const result = await axe.run(container, {
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
  });
  return result.violations.map(
    (v) =>
      `${v.id}: ${v.help} (${v.nodes
        .map((n) => n.target.join(" "))
        .slice(0, 3)
        .join(", ")})`,
  );
}
