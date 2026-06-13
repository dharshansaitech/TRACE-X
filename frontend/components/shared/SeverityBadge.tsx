"use client";
// frontend/components/shared/SeverityBadge.tsx
interface Props {
  severity: string;
  size?: "sm" | "md";
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: "badge-critical",
  high: "badge-high",
  medium: "badge-medium",
  low: "badge-low",
  info: "badge-info",
  // Also handle success/warning for status
  success: "badge-low",
  warning: "badge-medium",
  error: "badge-high",
};

export function SeverityBadge({ severity, size = "sm" }: Props) {
  const style = SEVERITY_STYLES[severity?.toLowerCase()] ?? "badge-info";
  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span className={`inline-flex items-center rounded font-medium ${style} ${sizeClass}`}>
      {severity}
    </span>
  );
}
