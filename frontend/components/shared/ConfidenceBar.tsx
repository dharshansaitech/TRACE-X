"use client";
// frontend/components/shared/ConfidenceBar.tsx
interface Props {
  value: number; // 0-1
  small?: boolean;
  showLabel?: boolean;
}

export function ConfidenceBar({ value, small = false, showLabel = false }: Props) {
  const pct = Math.max(0, Math.min(1, value)) * 100;

  const color =
    pct >= 80 ? "bg-success" :
    pct >= 60 ? "bg-tracex-400" :
    pct >= 40 ? "bg-warning" :
    "bg-danger";

  const height = small ? "h-1" : "h-1.5";

  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 ${height} bg-muted/50 rounded-full overflow-hidden`}>
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono text-muted-foreground w-10 text-right">
          {pct.toFixed(0)}%
        </span>
      )}
    </div>
  );
}
