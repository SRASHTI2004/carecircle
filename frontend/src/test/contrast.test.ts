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

describe("Elder mode meets WCAG AAA (>= 7:1 for text)", () => {
  const e = (n: string) => token(`e-${n}`);
  const pairs: [string, string][] = [
    ["text", "bg"],
    ["text", "card"],
    ["muted", "card"],
    ["muted", "bg"],
    ["accent", "bg"],
    ["accent", "card"],
  ];
  it.each(pairs)("%s on %s", (fg, bg) => {
    expect(ratio(e(fg), e(bg))).toBeGreaterThanOrEqual(7);
  });
  it("borders have at least 3:1 non-text contrast", () => {
    expect(ratio(e("line"), e("bg"))).toBeGreaterThanOrEqual(3);
  });
  it("primary button text on the accent colour", () => {
    expect(ratio("#0b1f3a", e("accent"))).toBeGreaterThanOrEqual(7);
  });
});
