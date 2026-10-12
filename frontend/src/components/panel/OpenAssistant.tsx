import { useEffect } from "react";
import { Navigate } from "react-router-dom";

import { useAssistant } from "./PanelProvider";

/** `/company/:ticker/chat`: a shareable way to land on a company with the assistant open. The
 *  assistant is a panel, not a page, so this opens it and hands over to the company page. */
export default function OpenAssistant() {
  const { open } = useAssistant();
  useEffect(open, [open]);
  return <Navigate to=".." replace />;
}
