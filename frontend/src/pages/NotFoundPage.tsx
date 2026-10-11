import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

import { SearchTrigger } from "../components/SearchTrigger";
import { Container } from "../components/ui/Container";
import { useDocumentTitle } from "../lib/useDocumentTitle";

/** A dead end with a way out: search for a company, or go home. Also used for an unknown ticker. */
export function NotFound({
  title = "Page not found",
  message = "That address doesn’t lead anywhere. Search for a company to get back on track.",
}: {
  title?: string;
  message?: string;
}) {
  useDocumentTitle(title);
  return (
    <Container>
      <div className="flex min-h-[60svh] flex-col items-center justify-center gap-4 py-16 text-center">
        <Compass aria-hidden className="size-6 text-subtle" />
        <h1 className="text-heading font-semibold">{title}</h1>
        <p className="max-w-md text-muted">{message}</p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <SearchTrigger variant="button" />
          <Link to="/" className="text-sm font-medium text-muted hover:text-text">
            Go to home
          </Link>
        </div>
      </div>
    </Container>
  );
}
