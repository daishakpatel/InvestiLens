import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Scroll to the element named by the URL hash once the calling page has mounted. Client-side
 *  navigation does not do this on its own, and old tab URLs redirect to in-page anchors.
 *  A page whose anchors arrive with its data passes `ready` as false until they are rendered. */
export function useScrollToHash(ready = true): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (ready && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash, ready]);
}
