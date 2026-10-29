import { z } from "zod";

/** The slice of JSON Schema that Pydantic emits for alert params (`GET /alerts/event-types`). */
export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: string[];
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  properties?: Record<string, JsonSchema>;
  required?: string[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minItems?: number;
  maxLength?: number;
  "x-unit"?: string; // "ratio": stored as 0.05, shown and typed as 5 (%)
}

interface FieldBase {
  name: string;
  label: string;
  description?: string | undefined;
  required: boolean;
}

/** One form input, derived from one params property. No per-event-type code (FR-AL-016). */
export type ParamField =
  | (FieldBase & { kind: "number"; schema: JsonSchema; initial: string; percent: boolean })
  | (FieldBase & { kind: "text"; schema: JsonSchema; initial: string })
  | (FieldBase & { kind: "boolean"; initial: boolean })
  | (FieldBase & { kind: "choice"; options: string[]; initial: string })
  | (FieldBase & { kind: "choices"; options: string[]; minItems: number; initial: string[] });

export type ParamValues = Record<string, string | boolean | string[]>;

/** `str | None` arrives as anyOf [string, null]: use the non-null branch. */
function unwrap(schema: JsonSchema): JsonSchema {
  const branch = schema.anyOf?.find((s) => s.type !== "null");
  return branch ? { ...schema, ...branch } : schema;
}

function humanize(name: string): string {
  const words = name.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function paramFields(schema: JsonSchema | null | undefined): ParamField[] {
  const required = new Set(schema?.required ?? []);
  return Object.entries(schema?.properties ?? {}).flatMap(([name, raw]): ParamField[] => {
    const s = unwrap(raw);
    const base = { name, label: s.title ?? humanize(name), description: s.description, required: required.has(name) };
    if (s.type === "array" && s.items?.enum) {
      const initial = Array.isArray(s.default) ? s.default.map(String) : [];
      return [{ ...base, kind: "choices", options: s.items.enum, minItems: s.minItems ?? 0, initial }];
    }
    if (s.enum) return [{ ...base, kind: "choice", options: s.enum, initial: String(s.default ?? s.enum[0]) }];
    if (s.type === "number" || s.type === "integer") {
      const percent = s["x-unit"] === "ratio";
      const initial = typeof s.default === "number" ? String(percent ? toPercent(s.default) : s.default) : "";
      return [{ ...base, label: percent ? `${base.label} (%)` : base.label, kind: "number", schema: s, initial, percent }];
    }
    if (s.type === "boolean") return [{ ...base, kind: "boolean", initial: s.default === true }];
    if (s.type === "string") return [{ ...base, kind: "text", schema: s, initial: s.default == null ? "" : String(s.default) }];
    return []; // a shape this form cannot edit: the server's default applies
  });
}

export function initialValues(fields: ParamField[]): ParamValues {
  return Object.fromEntries(fields.map((f) => [f.name, f.initial]));
}

const blankToUndefined = (v: unknown) => (v === "" ? undefined : v);
// Rounded so 0.07 reads 7, not 7.000000000000001.
const toPercent = (ratio: number) => Math.round(ratio * 100 * 1e6) / 1e6;

function fieldValidator(field: ParamField): z.ZodType {
  switch (field.kind) {
    case "number": {
      const s = field.schema;
      const bound = (b: number) => (field.percent ? toPercent(b) : b); // typed in %, bounded in %
      let n = s.type === "integer" ? z.coerce.number().int() : z.coerce.number();
      if (s.minimum !== undefined) n = n.gte(bound(s.minimum));
      if (s.exclusiveMinimum !== undefined) n = n.gt(bound(s.exclusiveMinimum));
      if (s.maximum !== undefined) n = n.lte(bound(s.maximum));
      if (s.exclusiveMaximum !== undefined) n = n.lt(bound(s.exclusiveMaximum));
      const value = field.percent ? n.transform((pct) => pct / 100) : n;
      return z.preprocess(blankToUndefined, field.required ? value : value.optional());
    }
    case "text": {
      let t = z.string().trim();
      if (field.schema.maxLength !== undefined) t = t.max(field.schema.maxLength);
      return z.preprocess(blankToUndefined, field.required ? t : t.optional());
    }
    case "boolean":
      return z.boolean();
    case "choice":
      return z.enum(field.options as [string, ...string[]]);
    case "choices":
      return z
        .array(z.enum(field.options as [string, ...string[]]))
        .min(Math.max(field.minItems, 1), "Choose at least one.");
  }
}

/** Validate the form and produce the `params` body: numbers as numbers, blanks left out so the
 *  server fills in its default. */
export function parseParams(
  fields: ParamField[],
  values: ParamValues,
): { ok: true; params: Record<string, unknown> } | { ok: false; errors: Record<string, string> } {
  const result = z.object(Object.fromEntries(fields.map((f) => [f.name, fieldValidator(f)]))).safeParse(values);
  if (result.success) {
    return {
      ok: true,
      params: Object.fromEntries(Object.entries(result.data).filter(([, v]) => v !== undefined)),
    };
  }
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) errors[String(issue.path[0])] ??= issue.message;
  return { ok: false, errors };
}

/** "Forms: 10-K, 10-Q" — a one-line reading of stored params for the rules list. */
export function describeParams(fields: ParamField[], params: Record<string, unknown>): string {
  return fields
    .filter((f) => params[f.name] !== undefined && params[f.name] !== null && params[f.name] !== "")
    .map((f) => {
      const value = params[f.name];
      if (f.kind === "number" && f.percent && typeof value === "number") {
        return `${f.label.replace(/ \(%\)$/, "")}: ${toPercent(value)}%`;
      }
      return `${f.label}: ${Array.isArray(value) ? value.join(", ") : String(value)}`;
    })
    .join(" · ");
}
