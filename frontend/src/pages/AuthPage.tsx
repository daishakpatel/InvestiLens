import { useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Wordmark } from "../components/AppShell";
import { DemoBanner } from "../components/DemoBanner";
import { Footer } from "../components/chrome";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useAuth } from "../lib/auth";
import { PASSWORD_MIN_LENGTH } from "../lib/config";
import { useDemoInfo } from "../lib/queries";
import { useDocumentTitle } from "../lib/useDocumentTitle";

type Mode = "login" | "register";
interface FieldErrors {
  email?: string | undefined;
  password?: string | undefined;
}

const COPY: Record<Mode, { title: string; submit: string; prompt: string; switchTo: string }> = {
  login: {
    title: "Sign in",
    submit: "Sign in",
    prompt: "New to Assay Desk?",
    switchTo: "Create an account",
  },
  register: {
    title: "Create your account",
    submit: "Create account",
    prompt: "Already have an account?",
    switchTo: "Sign in",
  },
};

function validate(mode: Mode, email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^\S+@\S+\.\S+$/.test(email.trim())) errors.email = "Enter a valid email address.";
  if (!password) errors.password = "Enter your password.";
  else if (mode === "register" && password.length < PASSWORD_MIN_LENGTH) {
    errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  return errors;
}

/** Where to go after signing in: back to the page that sent the user here, else home. */
function useReturnPath(): string {
  const state = useLocation().state as { from?: unknown } | null;
  const from = state?.from;
  return typeof from === "string" && from.startsWith("/") && !from.startsWith("//") ? from : "/";
}

export default function AuthPage() {
  const { user, login, register, enterDemo } = useAuth();
  const demo = useDemoInfo().data?.enabled === true;
  const navigate = useNavigate();
  const returnPath = useReturnPath();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const copy = COPY[mode];
  useDocumentTitle(copy.title);

  if (user) return <Navigate to={returnPath} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validate(mode, email, password);
    setErrors(found);
    setFailure(null);
    if (found.email) return emailRef.current?.focus();
    if (found.password) return passwordRef.current?.focus();

    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password);
      navigate(returnPath, { replace: true });
    } catch (error) {
      // A rejected fetch is a network failure; anything else is the API's own message, verbatim.
      setFailure(
        error instanceof TypeError
          ? "Can’t reach Assay Desk. Check your connection and try again."
          : error instanceof Error
            ? error.message
            : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  };

  const openDemo = async () => {
    setFailure(null);
    setBusy(true);
    try {
      await enterDemo();
      navigate(returnPath, { replace: true });
    } catch {
      setFailure("The demo account couldn’t be opened. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = () => {
    setMode((current) => (current === "login" ? "register" : "login"));
    setErrors({});
    setFailure(null);
  };

  return (
    <div className="flex min-h-full flex-col">
      <DemoBanner />
      <main className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-[400px]">
          <Wordmark />
          <h1 className="mt-10 text-heading font-semibold">{copy.title}</h1>
          <p className="mt-1 text-muted">
            An account lets you generate research reports and ask questions about a company.
          </p>

          <form onSubmit={(event) => void submit(event)} noValidate className="mt-8 space-y-5">
            <div>
              <label htmlFor={`${id}-email`} className="mb-1.5 block text-label text-muted">
                Email
              </label>
              <Input
                ref={emailRef}
                id={`${id}-email`}
                type="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setErrors((current) => ({ ...current, email: undefined }));
                }}
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? `${id}-email-error` : undefined}
                className="h-10"
              />
              {errors.email && (
                <p id={`${id}-email-error`} className="mt-1.5 text-label text-negative">
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <label htmlFor={`${id}-password`} className="mb-1.5 block text-label text-muted">
                Password
              </label>
              <Input
                ref={passwordRef}
                id={`${id}-password`}
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setErrors((current) => ({ ...current, password: undefined }));
                }}
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={`${id}-password-note`}
                className="h-10"
              />
              <p
                id={`${id}-password-note`}
                className={`mt-1.5 text-label ${errors.password ? "text-negative" : "text-subtle"}`}
              >
                {errors.password ??
                  (mode === "register" ? `At least ${PASSWORD_MIN_LENGTH} characters.` : "")}
              </p>
            </div>

            {failure && (
              <p role="alert" className="text-sm text-negative">
                {failure}
              </p>
            )}

            <Button type="submit" variant="primary" loading={busy} className="h-10 w-full">
              {copy.submit}
            </Button>
          </form>

          {demo && (
            <div className="mt-8 border-t border-border pt-6">
              <p className="text-sm text-muted">
                This is the public demo. Accounts are closed; everyone shares one sandbox that resets
                nightly.
              </p>
              <Button variant="primary" loading={busy} onClick={() => void openDemo()} className="mt-4 h-10 w-full">
                Enter the demo
              </Button>
            </div>
          )}

          {!demo && (
            <p className="mt-6 text-sm text-muted">
              {copy.prompt}{" "}
              <button
                type="button"
                onClick={switchMode}
                className="font-medium text-primary hover:underline"
              >
                {copy.switchTo}
              </button>
            </p>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
