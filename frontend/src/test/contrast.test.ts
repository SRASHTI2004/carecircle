import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(`${process.cwd()}/src/styles.css`, "utf8");

function lum(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const ratio = (a: string, b: string): number => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const token = (name: string): string => {
  const m = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token ${name} missing`);
  return m[1];
};

describe("WCAG AA contrast of the standard theme (>= 4.5:1)", () => {
  const pairs: [string, string][] = [
    ["text", "bg"],
    ["text", "surface"],
    ["muted", "surface"],
    ["muted", "bg"],
    ["primary-text", "primary"],
    ["primary", "surface"],
    ["primary-text", "primary-dark"],
    ["danger", "surface"],
    ["ok-text", "ok-bg"],
    ["warn-text", "warn-bg"],
    ["bad-text", "bad-bg"],
    ["info-text", "info-bg"],
    ["primary", "info-bg"],
  ];
  it.each(pairs)("%s on %s", (fg, bg) => {
    expect(ratio(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5);
  });
});

describe.each([
  ["light", "el"],
  ["dark", "ed"],
] as const)("Elder mode %s theme meets WCAG AAA (>= 7:1 for text)", (_theme, p) => {
  const t = (n: string) => token(`${p}-${n}`);
  const textPairs: [string, string][] = [
    ["text", "bg"],
    ["text", "card"],
    ["muted", "card"],
    ["muted", "bg"],
    ["accent", "card"],
    ["accent", "bg"],
    ["accent-text", "accent"],
    ["ok-fg", "ok-bg"],
    ["up-fg", "up-bg"],
    ["miss-fg", "miss-bg"],
    ["skip-fg", "skip-bg"],
    ["due-fg", "due-bg"],
  ];
  it.each(textPairs)("%s on %s", (fg, bg) => {
    expect(ratio(t(fg), t(bg))).toBeGreaterThanOrEqual(7);
  });
  it.each(["st-taken", "st-up", "st-miss", "st-skip", "st-due", "line"])(
    "%s is visible against the card (>= 3:1)",
    (name) => {
      expect(ratio(t(name), t("card"))).toBeGreaterThanOrEqual(3);
    },
  );
});
