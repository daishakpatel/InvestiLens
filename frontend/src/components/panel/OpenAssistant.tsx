import { useEffect } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../lib/auth";
import { MAX_QUESTION_LENGTH } from "../assistant/useConversation";
import { useAssistant } from "./PanelProvider";

/** `/company/:ticker/chat`: a shareable way to land on a company with the assistant open. The
 *  assistant is a panel, not a page, so this opens it and hands over to the company page.
 *  `?ask=` also asks a question, for a signed-in reader (the demo's guided path links here). */
export default function OpenAssistant() {
  const { open, ask } = useAssistant();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const question = (params.get("ask") ?? "").trim().slice(0, MAX_QUESTION_LENGTH);
  useEffect(() => {
    // A conversation already in flight ignores a second ask, so StrictMode's rerun is harmless.
    if (question && user) ask(question);
    else open();
  }, [open, ask, question, user]);
  return <Navigate to=".." replace />;
}
