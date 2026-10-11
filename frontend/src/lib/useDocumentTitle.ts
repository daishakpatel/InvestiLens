import { useEffect } from "react";

const BASE = "InvestiLens";

/** Name the browser tab after the page, so history and bookmarks are readable. */
export function useDocumentTitle(title: string | null | undefined): void {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : BASE;
    return () => {
      document.title = BASE;
    };
  }, [title]);
}
