import type { ReactElement } from "react";

import { colors, type } from "@/styles/tokens";

/**
 * Renders an LLM answer string as readable, sectioned content (CLAUDE.md 9.5:
 * "bulleted/sectioned, not one dense paragraph"). Lightweight structural parse —
 * no markdown dependency:
 *  - "Label: rest"           → bold section header + text
 *  - "- " / "• " / "* "      → bullet list item
 *  - "1. " / "1) "           → numbered list item
 *  - blank line              → paragraph break
 *  - **bold** inline         → bold span
 * Also strips the mock-LLM "[mock-llm <hash>]" tag noise so mock-mode output reads
 * cleanly (real Azure/Claude output has no such tag).
 */
function inlineBold(text: string, keyBase: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={`${keyBase}-${i}`} style={{ color: colors.text.primary }}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyBase}-${i}`}>{p}</span>
    ),
  );
}

export function FormattedAnswer({ text }: { text: string }) {
  const clean = (text || "")
    .replace(/\[mock-llm [0-9a-f]+\]\s*/gi, "")
    .replace(/\s+—\s*Deterministic draft based on:/gi, " —");
  const lines = clean.split(/\n/);

  const blocks: ReactElement[] = [];
  let bullets: string[] = [];
  let numbers: string[] = [];
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (!tableRows.length) return;
    const [head, ...body] = tableRows;
    blocks.push(
      <div key={`t-${blocks.length}`} className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="border-b text-left text-[10px] uppercase tracking-wide" style={{ color: colors.text.muted }}>
              {head.map((c, i) => <th key={i} className="px-2 py-1.5">{inlineBold(c, `th${blocks.length}-${i}`)}</th>)}
            </tr>
          </thead>
          <tbody>
            {body.map((r, ri) => (
              <tr key={ri} className="border-b last:border-0">
                {r.map((c, ci) => (
                  <td key={ci} className="px-2 py-1.5" style={{ color: colors.text.secondary }}>{inlineBold(c, `td${blocks.length}-${ri}-${ci}`)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    tableRows = [];
  };

  const flush = () => {
    flushTable();
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="ml-1 space-y-1">
          {bullets.map((b, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: colors.primary }} />
              <span className={type.data} style={{ color: colors.text.secondary }}>{inlineBold(b, `b${blocks.length}-${i}`)}</span>
            </li>
          ))}
        </ul>,
      );
      bullets = [];
    }
    if (numbers.length) {
      blocks.push(
        <ol key={`ol-${blocks.length}`} className="ml-1 space-y-1">
          {numbers.map((n, i) => (
            <li key={i} className="flex gap-2">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white" style={{ backgroundColor: colors.aiAccent }}>{i + 1}</span>
              <span className={type.data} style={{ color: colors.text.secondary }}>{inlineBold(n, `n${blocks.length}-${i}`)}</span>
            </li>
          ))}
        </ol>,
      );
      numbers = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    // markdown table rows: "| a | b |" — separator rows (|---|---|) are skipped
    if (/^\|.*\|$/.test(line)) {
      if (!/^[|\s:-]+$/.test(line)) {
        tableRows.push(line.slice(1, -1).split("|").map((c) => c.trim()));
      }
      continue;
    }
    flushTable();
    if (/^-{3,}$/.test(line)) { flush(); continue; } // horizontal rule → paragraph break
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (heading) {
      flush();
      blocks.push(
        <p key={`md-h-${blocks.length}`} className="mt-1.5 text-[13px] font-bold" style={{ color: colors.text.primary }}>
          {inlineBold(heading[1], `mdh${blocks.length}`)}
        </p>,
      );
      continue;
    }
    const bullet = line.match(/^[-•*]\s+(.*)$/);
    const number = line.match(/^\d+[.)]\s+(.*)$/);
    const header = line.match(/^([A-Z][A-Za-z0-9 /&-]{2,40}):\s*(.*)$/);
    if (bullet) { numbers.length && flush(); bullets.push(bullet[1]); continue; }
    if (number) { bullets.length && flush(); numbers.push(number[1]); continue; }
    flush();
    if (header) {
      blocks.push(
        <p key={`h-${blocks.length}`} className="mt-1">
          <span className={type.label} style={{ color: colors.aiAccent }}>{header[1]}</span>
          {header[2] ? <span className={`ml-1 ${type.body}`} style={{ color: colors.text.primary }}>{inlineBold(header[2], `hb${blocks.length}`)}</span> : null}
        </p>,
      );
    } else {
      blocks.push(
        <p key={`p-${blocks.length}`} className={type.body} style={{ color: colors.text.primary }}>{inlineBold(line, `p${blocks.length}`)}</p>,
      );
    }
  }
  flush();

  return <div className="space-y-2">{blocks}</div>;
}
