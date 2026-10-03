import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { CitationChip } from "../../components/citations/CitationChip";
import { ReferenceList } from "../../components/citations/ReferenceList";
import { Panel } from "../../components/Panel";
import { Badge, EvidenceBadge, Spinner } from "../../components/primitives";
import { apiRequest } from "../../lib/apiClient";
import { useAuth } from "../../lib/auth";
import { streamChat } from "../../lib/chatStream";
import type { ChatCitation, EvidenceLabel, ToolTraceEntry } from "../../types";

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations: ChatCitation[];
  done: boolean;
  abstained?: boolean;
  refused?: boolean;
  evidenceLabel?: EvidenceLabel | null;
  toolTrace?: ToolTraceEntry[];
  suggested?: string[];
  messageId?: string | null;
}

export default function ChatTab() {
  const { ticker = "" } = useParams();
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  if (!user) {
    return (
      <Panel title="Chat" kind="ai">
        <p className="p-6 text-sm text-muted">
          <Link to="/login" className="text-primary hover:underline">
            Sign in
          </Link>{" "}
          to ask questions about {ticker}. Chat answers are grounded in the company’s filings and
          data, with citations.
        </p>
      </Panel>
    );
  }

  const update = (id: string, fn: (m: ChatMsg) => ChatMsg) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)));

  const ask = async (question: string) => {
    const q = question.trim();
    if (busy || !q) return;
    const aId = crypto.randomUUID();
    setMessages((ms) => [
      ...ms,
      { id: crypto.randomUUID(), role: "user", text: q, citations: [], done: true },
      { id: aId, role: "assistant", text: "", citations: [], done: false },
    ]);
    setInput("");
    setBusy(true);
    try {
      await streamChat(
        { company: ticker, question: q, session_id: sessionId },
        {
          onToken: (t) => update(aId, (m) => ({ ...m, text: m.text + t })),
          onCitations: (c) => update(aId, (m) => ({ ...m, citations: c })),
          onDone: (meta) => {
            update(aId, (m) => ({
              ...m,
              done: true,
              abstained: meta.abstained,
              refused: meta.refused,
              evidenceLabel: meta.evidence_label,
              toolTrace: meta.tool_trace,
              suggested: meta.suggested_questions,
              messageId: meta.message_id != null ? String(meta.message_id) : null,
            }));
            if (meta.session_id != null) setSessionId(String(meta.session_id));
          },
        },
      );
    } catch (e) {
      update(aId, (m) => ({
        ...m,
        done: true,
        text: m.text || (e instanceof Error ? e.message : "Something went wrong."),
      }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-4" aria-live="polite">
        {messages.length === 0 && (
          <p className="text-sm text-muted">
            Ask about {ticker} — e.g. “Why did revenue grow?” or “What was gross margin in FY2025?”
          </p>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="ml-auto max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-sm">
              {m.text}
            </div>
          ) : (
            <AssistantMessage key={m.id} msg={m} onAsk={ask} />
          ),
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          aria-label="Ask a question"
          placeholder={`Ask about ${ticker}…`}
          className="flex-1 rounded-lg border border-border bg-surface px-4 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-contrast hover:opacity-90 disabled:opacity-60"
        >
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}

function AssistantMessage({ msg, onAsk }: { msg: ChatMsg; onAsk: (q: string) => void }) {
  const refs = msg.citations.map((c) => ({
    number: c.number,
    sourceId: c.source_id,
    title: c.title ?? null,
    tier: c.tier ?? null,
  }));

  return (
    <div className="max-w-[85%] rounded-lg border border-border bg-surface px-3 py-2">
      {!msg.done && msg.text === "" ? (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> Thinking…
        </div>
      ) : msg.refused ? (
        <Notice tone="redirect" text={msg.text} />
      ) : msg.abstained ? (
        <Notice tone="abstain" text={msg.text} />
      ) : (
        <>
          <div className="text-sm leading-relaxed">
            <AnswerText text={msg.text} citations={msg.citations} />
          </div>
          {msg.done && <EvidenceBadge label={msg.evidenceLabel} />}
        </>
      )}

      {msg.toolTrace && msg.toolTrace.length > 0 && <ToolTrace entries={msg.toolTrace} />}
      {refs.length > 0 && <ReferenceList entries={refs} />}
      {msg.done && !msg.abstained && !msg.refused && msg.messageId && (
        <Feedback messageId={msg.messageId} />
      )}
      {msg.suggested && msg.suggested.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {msg.suggested.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onAsk(q)}
              className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:bg-surface-2 hover:text-text"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Render answer text, turning inline [n] markers into clickable chips once citations resolve. */
function AnswerText({ text, citations }: { text: string; citations: ChatCitation[] }) {
  const byNumber = new Map(citations.map((c) => [c.number, c.source_id]));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part);
        if (match) {
          const n = Number(match[1]);
          const sourceId = byNumber.get(n);
          if (sourceId) return <CitationChip key={i} number={n} sourceId={sourceId} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function Notice({ tone, text }: { tone: "abstain" | "redirect"; text: string }) {
  const title = tone === "abstain" ? "Insufficient evidence" : "Out of scope";
  return (
    <div className="rounded-md border border-border bg-surface-2 p-3 text-sm">
      <div className="mb-1 flex items-center gap-2">
        <Badge tone="warning">{title}</Badge>
      </div>
      <p className="text-muted">{text}</p>
    </div>
  );
}

function ToolTrace({ entries }: { entries: ToolTraceEntry[] }) {
  return (
    <details className="mt-2 text-xs text-muted">
      <summary className="cursor-pointer">Checked {entries.length} source tool(s)</summary>
      <ul className="mt-1 list-disc pl-5">
        {entries.map((t, i) => (
          <li key={i}>
            {t.tool}
            {t.latency_ms != null ? ` · ${t.latency_ms}ms` : ""}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Feedback({ messageId }: { messageId: string }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  const send = async (rating: "up" | "down") => {
    setSent(rating);
    try {
      await apiRequest(`/chat/messages/${messageId}/feedback`, { method: "POST", body: { rating } });
    } catch {
      setSent(null); // allow retry on failure
    }
  };
  return (
    <div className="mt-2 flex items-center gap-2 text-sm">
      <button
        type="button"
        aria-label="Helpful"
        aria-pressed={sent === "up"}
        onClick={() => void send("up")}
        className={`rounded px-1 ${sent === "up" ? "text-positive" : "text-muted hover:text-text"}`}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        aria-pressed={sent === "down"}
        onClick={() => void send("down")}
        className={`rounded px-1 ${sent === "down" ? "text-negative" : "text-muted hover:text-text"}`}
      >
        👎
      </button>
      {sent && <span className="text-xs text-muted">Thanks for the feedback.</span>}
    </div>
  );
}
