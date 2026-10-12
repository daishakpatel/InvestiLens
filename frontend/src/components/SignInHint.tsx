import { Link, useLocation } from "react-router-dom";

/** What a signed-out reader sees in place of a personal feature: why an account is needed, and a
 *  way to sign in that comes back to this page. */
export function SignInHint({ children }: { children: string }) {
  const { pathname, search } = useLocation();
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">{children}</p>
      <Link
        to="/login"
        state={{ from: pathname + search }}
        className="inline-flex h-9 items-center rounded-control bg-primary px-3.5 text-sm font-medium text-primary-contrast transition-colors hover:bg-primary/90"
      >
        Sign in
      </Link>
    </div>
  );
}
