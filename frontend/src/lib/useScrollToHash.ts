import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Scroll to the element named by the URL hash once the calling page has mounted. Client-side
 *  navigation does not do this on its own, and old tab URLs redirect to in-page anchors. */
export function useScrollToHash(): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash]);
}
