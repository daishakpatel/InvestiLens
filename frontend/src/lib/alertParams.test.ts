import { describe, expect, it } from "vitest";

import { describeParams, initialValues, paramFields, parseParams } from "./alertParams";
import type { JsonSchema } from "./alertParams";

// The schemas the backend registry emits today (FR-AL-016).
const PRICE: JsonSchema = {
  type: "object",
  properties: {
    threshold: { type: "number", title: "Move threshold", default: 0.05, exclusiveMinimum: 0, maximum: 1 },
  },
};
const FILING: JsonSchema = {
  type: "object",
  properties: {
    form_types: {
      type: "array",
      title: "Forms",
      items: { type: "string", enum: ["10-K", "10-Q", "8-K"] },
      minItems: 1,
      default: ["10-K", "10-Q", "8-K"],
    },
  },
};
const NEWS: JsonSchema = {
  type: "object",
  properties: { category: { anyOf: [{ type: "string", maxLength: 64 }, { type: "null" }], default: null, title: "Category" } },
};

describe("alert params form (FR-AL-016)", () => {
  it("derives typed fields with the schema defaults", () => {
    expect(initialValues(paramFields(PRICE))).toEqual({ threshold: "0.05" });
    expect(initialValues(paramFields(FILING))).toEqual({ form_types: ["10-K", "10-Q", "8-K"] });
    const [category] = paramFields(NEWS);
    expect(category).toMatchObject({ kind: "text", label: "Category", initial: "" });
    expect(paramFields({ type: "object", properties: {} })).toEqual([]);
  });

  it("sends numbers as numbers and leaves blanks to the server default", () => {
    expect(parseParams(paramFields(PRICE), { threshold: "0.1" })).toEqual({ ok: true, params: { threshold: 0.1 } });
    expect(parseParams(paramFields(NEWS), { category: "" })).toEqual({ ok: true, params: {} });
  });

  it("rejects values outside the schema's bounds, per field", () => {
    const tooBig = parseParams(paramFields(PRICE), { threshold: "5" });
    expect(tooBig.ok).toBe(false);
    expect(!tooBig.ok && tooBig.errors.threshold).toBeTruthy();
    const none = parseParams(paramFields(FILING), { form_types: [] });
    expect(!none.ok && none.errors.form_types).toBe("Choose at least one.");
  });

  it("describes stored params in one line", () => {
    expect(describeParams(paramFields(FILING), { form_types: ["10-K", "8-K"] })).toBe("Forms: 10-K, 8-K");
    expect(describeParams(paramFields(NEWS), { category: null })).toBe("");
  });
});
