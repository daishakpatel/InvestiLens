// Phase 7k (FR-TH-015/018): thesis text is the user's markdown, rendered safely by construction.
// It is parsed into React elements, never into an HTML string: raw HTML in the text shows as
// text, links are kept only for http(s) URLs (opened with noopener, noreferrer), and images are
// not loaded (their alt text is shown instead). No dependency and no raw-HTML injection.
import type { ReactNode } from "react";

const SAFE_URL = /^https?:\/\/[^\s<>"]+$/i;
// One inline token at a time: code, image (shown as its alt text), link, bold, italic.
const INLINE = /(`[^`]+`)|(!\[([^\]]*)\]\(([^)\s]*)\))|(\[([^\]]+)\]\(([^)\s]+)\))|(\*\*([^*]+)\*\*)|(\*([^*]+)\*|_([^_]+)_)/;

export function safeHref(url: string): string | null {
  return SAFE_URL.test(url) ? url : null;
}

export function inline(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let n = 0;
  while (rest) {
    const m = INLINE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index > 0) out.push(rest.slice(0, m.index));
    const k = `${key}-${n++}`;
    if (m[1]) out.push(<code key={k} className="rounded bg-surface-2 px-1 py-0.5 text-[0.92em]">{m[1].slice(1, -1)}</code>);
    else if (m[2]) out.push(m[3] ? `[image: ${m[3]}]` : "[image]");
    else if (m[5]) {
      const href = safeHref(m[7] ?? "");
      out.push(
        href ? (
          <a key={k} href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-primary underline underline-offset-2">
            {inline(m[6] ?? "", k)}
          </a>
        ) : (
          m[6]
        ),
      );
    } else if (m[8]) out.push(<strong key={k}>{inline(m[9] ?? "", k)}</strong>);
    else out.push(<em key={k}>{inline(m[11] ?? m[12] ?? "", k)}</em>);
    rest = rest.slice(m.index + m[0].length);
  }
  return out;
}

type Block =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "paragraph"; text: string };

export function blocks(source: string): Block[] {
  const out: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) out.push({ kind: "paragraph", text: para.join(" ") });
    para = [];
  };
  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const quote = /^>\s?(.*)$/.exec(line);
    const last = out[out.length - 1];
    if (!line.trim()) flush();
    else if (heading) {
      flush();
      out.push({ kind: "heading", level: (heading[1] ?? "#").length as 1 | 2 | 3, text: heading[2] ?? "" });
    } else if (bullet || numbered) {
      flush();
      const ordered = Boolean(numbered);
      const text = (bullet ?? numbered)?.[1] ?? "";
      if (last?.kind === "list" && last.ordered === ordered) last.items.push(text);
      else out.push({ kind: "list", ordered, items: [text] });
    } else if (quote) {
      flush();
      if (last?.kind === "quote") last.text += ` ${quote[1] ?? ""}`;
      else out.push({ kind: "quote", text: quote[1] ?? "" });
    } else para.push(line.trim());
  }
  flush();
  return out;
}

const HEADING = { 1: "text-title font-medium", 2: "text-body font-medium", 3: "text-sm font-medium" } as const;

export function renderMarkdown(source: string): ReactNode[] {
  return blocks(source).map((block, i) => {
    const key = `b${i}`;
    switch (block.kind) {
      case "heading": {
        const Tag = (["h3", "h4", "h5"] as const)[block.level - 1] ?? "h5";
        return <Tag key={key} className={HEADING[block.level]}>{inline(block.text, key)}</Tag>;
      }
      case "list": {
        const Tag = block.ordered ? "ol" : "ul";
        return (
          <Tag key={key} className={`${block.ordered ? "list-decimal" : "list-disc"} space-y-1 pl-5`}>
            {block.items.map((item, j) => <li key={`${key}-${j}`}>{inline(item, `${key}-${j}`)}</li>)}
          </Tag>
        );
      }
      case "quote":
        return <blockquote key={key} className="border-l-2 border-border-strong pl-3 text-muted">{inline(block.text, key)}</blockquote>;
      default:
        return <p key={key}>{inline(block.text, key)}</p>;
    }
  });
}
