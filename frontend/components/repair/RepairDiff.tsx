"use client";
// frontend/components/repair/RepairDiff.tsx
import { useState } from "react";
import type { RepairDiff } from "@/types";
import { Copy, Check } from "lucide-react";

interface Props {
  diff: RepairDiff;
}

export function RepairDiffView({ diff }: Props) {
  const [view, setView] = useState<"split" | "unified">("split");
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(diff.after ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="font-medium text-sm">Repair Diff</h3>
        <div className="flex items-center gap-2">
          {["split", "unified"].map((v) => (
            <button
              key={v}
              onClick={() => setView(v as "split" | "unified")}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                view === v ? "bg-tracex-500/20 text-tracex-300" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {v}
            </button>
          ))}
          <button
            onClick={copyToClipboard}
            className="p-1.5 rounded hover:bg-surface-elevated transition-colors text-muted-foreground"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {view === "split" ? (
        <div className="grid grid-cols-2 divide-x divide-border/50 max-h-96 overflow-auto">
          <div className="p-4">
            <p className="text-xs font-medium text-danger mb-2">BEFORE</p>
            <pre className="text-xs font-mono whitespace-pre-wrap text-red-300/80">
              {diff.before ?? ""}
            </pre>
          </div>
          <div className="p-4">
            <p className="text-xs font-medium text-success mb-2">AFTER</p>
            <pre className="text-xs font-mono whitespace-pre-wrap text-green-300/80">
              {diff.after ?? ""}
            </pre>
          </div>
        </div>
      ) : (
        <div className="p-4 max-h-96 overflow-auto">
          {diff.diff_lines && diff.diff_lines.length > 0 ? (
            <div className="space-y-0.5">
              {diff.diff_lines.map((line, i) => (
                <div
                  key={i}
                  className={`text-xs font-mono px-2 py-0.5 rounded ${
                    line.change_type === "added"
                      ? "diff-added text-green-300"
                      : line.change_type === "removed"
                      ? "diff-removed text-red-300"
                      : "text-muted-foreground"
                  }`}
                >
                  <span className="mr-3 text-muted-foreground/40 select-none">
                    {line.change_type === "added" ? "+" : line.change_type === "removed" ? "-" : " "}
                  </span>
                  {line.content}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {(diff.before ?? "").split("\n").map((line, i) => (
                <div key={`b-${i}`} className="diff-removed text-xs font-mono px-2 py-0.5 text-red-300">
                  - {line}
                </div>
              ))}
              {(diff.after ?? "").split("\n").map((line, i) => (
                <div key={`a-${i}`} className="diff-added text-xs font-mono px-2 py-0.5 text-green-300">
                  + {line}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {diff.description && (
        <div className="px-4 py-3 border-t border-border/30 text-xs text-muted-foreground">
          {diff.description}
        </div>
      )}
    </div>
  );
}
