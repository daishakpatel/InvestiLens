import { useOutletContext } from "react-router-dom";

/** What the company page frame hands to the tab rendered inside it. */
export interface CompanyOutletContext {
  /** Ref callback for the element that shows the current price on a tab (the Overview hero).
   *  While that element is on screen the pinned bar keeps its own copy of the price hidden. */
  quoteAnchor: (element: HTMLElement | null) => void;
}

export function useCompanyOutlet(): CompanyOutletContext {
  return useOutletContext<CompanyOutletContext>();
}
