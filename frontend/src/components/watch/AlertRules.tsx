import { Trash2 } from "lucide-react";
import { useId, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { describeParams, initialValues, paramFields, parseParams } from "../../lib/alertParams";
import type { JsonSchema, ParamField, ParamValues } from "../../lib/alertParams";
import { useCreateAlert, useDeleteAlert, useUpdateAlert } from "../../lib/queries";
import type { Alert, AlertEventType } from "../../types";
import { Badge } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Switch } from "../ui/Switch";

type Channel = Alert["channels"][number];
const CHANNELS: { value: Channel; label: string }[] = [
  { value: "in_app", label: "In app" },
  { value: "email", label: "Email" },
];
const CHECKBOX = "size-4 rounded accent-primary";

function fieldsOf(type: AlertEventType | undefined): ParamField[] {
  return paramFields(type?.params_schema as JsonSchema | undefined);
}

/** The user's alert rules: toggle or delete each. A rule whose type the server no longer offers
 *  stays listed, marked, so it never disappears without a word (FR-AL-017). */
export function AlertRuleList({ alerts, types }: { alerts: Alert[]; types: AlertEventType[] }) {
  const update = useUpdateAlert();
  const remove = useDeleteAlert();
  const byKey = useMemo(() => new Map(types.map((t) => [t.key, t])), [types]);

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-border/60">
        {alerts.map((alert) => {
          const type = byKey.get(alert.event_type);
          const name = type?.label ?? alert.event_type;
          const scope = alert.ticker ?? "All watched companies";
          const detail = [
            type ? describeParams(fieldsOf(type), alert.params) : "",
            alert.channels.map((c) => CHANNELS.find((x) => x.value === c)?.label ?? c).join(" + "),
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <li key={alert.id} className="flex items-center justify-between gap-4 py-3">
              <Switch
                checked={alert.enabled}
                disabled={!type || update.isPending}
                onCheckedChange={(enabled) => update.mutate({ id: alert.id, enabled })}
              >
                <span>
                  {name} <span className="text-muted">· {scope}</span>
                  {!type && (
                    <span className="ml-2 align-middle">
                      <Badge tone="warning">No longer supported</Badge>
                    </span>
                  )}
                  {detail && <span className="block text-caption text-subtle">{detail}</span>}
                </span>
              </Switch>
              <IconButton
                variant="ghost"
                label={`Delete ${name} alert for ${scope}`}
                disabled={remove.isPending}
                onClick={() => remove.mutate(alert.id)}
              >
                <Trash2 aria-hidden className="size-4" />
              </IconButton>
            </li>
          );
        })}
      </ul>
      {(update.isError || remove.isError) && (
        <p role="alert" className="text-caption text-negative">
          Could not update that alert. Try again.
        </p>
      )}
    </div>
  );
}

function ParamInput({
  field,
  value,
  error,
  onChange,
}: {
  field: ParamField;
  value: ParamValues[string];
  error: string | undefined;
  onChange: (value: ParamValues[string]) => void;
}) {
  const id = useId();
  const hint = field.description ? `${id}-hint` : undefined;
  const err = error ? `${id}-error` : undefined;
  const describedBy = [hint, err].filter(Boolean).join(" ") || undefined;
  const messages = (
    <>
      {field.description && (
        <p id={hint} className="text-caption text-subtle">
          {field.description}
        </p>
      )}
      {error && (
        <p id={err} className="text-caption text-negative">
          {error}
        </p>
      )}
    </>
  );

  if (field.kind === "choices") {
    const chosen = value as string[];
    return (
      <fieldset aria-describedby={describedBy} aria-invalid={error ? true : undefined} className="space-y-1.5">
        <legend className="text-sm">{field.label}</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {field.options.map((option) => (
            <label key={option} className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                className={CHECKBOX}
                checked={chosen.includes(option)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...chosen, option] : chosen.filter((o) => o !== option))
                }
              />
              {option}
            </label>
          ))}
        </div>
        {messages}
      </fieldset>
    );
  }
  if (field.kind === "boolean") {
    return (
      <div className="space-y-1">
        <label className="inline-flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={value as boolean}
            aria-describedby={describedBy}
            onChange={(e) => onChange(e.target.checked)}
          />
          {field.label}
        </label>
        {messages}
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm">
        {field.label}
      </label>
      {field.kind === "choice" ? (
        <Select id={id} value={value as string} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy}>
          {field.options.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </Select>
      ) : (
        <Input
          id={id}
          value={value as string}
          inputMode={field.kind === "number" ? "decimal" : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {messages}
    </div>
  );
}

/** "New alert": every input comes from the chosen type's params schema, so a new event type
 *  needs no form code (FR-AL-016). With `ticker` the scope is fixed to that company. */
export function NewAlertForm({ types, ticker, onCreated }: { types: AlertEventType[]; ticker?: string; onCreated?: () => void }) {
  const create = useCreateAlert();
  const ids = useId();
  const [typeKey, setTypeKey] = useState(types[0]?.key ?? "");
  const type = types.find((t) => t.key === typeKey);
  const fields = useMemo(() => fieldsOf(type), [type]);
  const [values, setValues] = useState<ParamValues>(() => initialValues(fields));
  const [scope, setScope] = useState(ticker ?? "");
  const [channels, setChannels] = useState<Channel[]>(["in_app"]);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const chooseType = (key: string) => {
    setTypeKey(key);
    setValues(initialValues(fieldsOf(types.find((t) => t.key === key))));
    setErrors({});
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const parsed = parseParams(fields, values);
    const problems = parsed.ok ? {} : { ...parsed.errors };
    if (channels.length === 0) problems.channels = "Choose at least one.";
    setErrors(problems);
    if (!parsed.ok || Object.keys(problems).length > 0) return;
    create.mutate(
      { event_type: typeKey, ticker: scope.trim() ? scope.trim().toUpperCase() : null, params: parsed.params, channels },
      {
        onSuccess: () => {
          setValues(initialValues(fields));
          onCreated?.();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor={`${ids}-type`} className="block text-sm">
          Notify me about
        </label>
        <Select id={`${ids}-type`} value={typeKey} onChange={(e) => chooseType(e.target.value)} className="w-full">
          {types.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </Select>
        {type && <p className="text-caption text-subtle">{type.description}</p>}
      </div>

      {ticker === undefined && (
        <div className="space-y-1.5">
          <label htmlFor={`${ids}-scope`} className="block text-sm">
            Company
          </label>
          <Input
            id={`${ids}-scope`}
            value={scope}
            maxLength={16}
            placeholder="Ticker, e.g. NVDA"
            aria-describedby={`${ids}-scope-hint`}
            onChange={(e) => setScope(e.target.value)}
          />
          <p id={`${ids}-scope-hint`} className="text-caption text-subtle">
            Leave empty to cover every company on your watchlist, including ones you add later.
          </p>
        </div>
      )}

      {fields.map((field) => (
        <ParamInput
          key={`${typeKey}.${field.name}`}
          field={field}
          value={values[field.name] ?? field.initial}
          error={errors[field.name]}
          onChange={(value) => setValues((v) => ({ ...v, [field.name]: value }))}
        />
      ))}

      <fieldset className="space-y-1.5" aria-describedby={errors.channels ? `${ids}-channels-error` : undefined}>
        <legend className="text-sm">Deliver by</legend>
        <div className="flex gap-4">
          {CHANNELS.map(({ value, label }) => (
            <label key={value} className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                className={CHECKBOX}
                checked={channels.includes(value)}
                onChange={(e) =>
                  setChannels((c) => (e.target.checked ? [...c, value] : c.filter((x) => x !== value)))
                }
              />
              {label}
            </label>
          ))}
        </div>
        {errors.channels && (
          <p id={`${ids}-channels-error`} className="text-caption text-negative">
            {errors.channels}
          </p>
        )}
      </fieldset>

      {create.isError && (
        <p role="alert" className="text-caption text-negative">
          {create.error.message}
        </p>
      )}
      <Button type="submit" loading={create.isPending} disabled={!type}>
        Create alert
      </Button>
    </form>
  );
}
