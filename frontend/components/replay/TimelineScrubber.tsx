"use client";
// frontend/components/replay/TimelineScrubber.tsx
import { useRef, useCallback } from "react";
import type { ReplayFrame } from "@/types";

interface Props {
  frames: ReplayFrame[];
  currentIndex: number;
  failureIndices: number[];
  divergenceIndex?: number;
  onSeek: (index: number) => void;
}

export function TimelineScrubber({
  frames,
  currentIndex,
  failureIndices,
  divergenceIndex,
  onSeek,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!trackRef.current || frames.length === 0) return;
      const rect = trackRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, x / rect.width));
      const frameIndex = Math.round(ratio * (frames.length - 1));
      onSeek(frameIndex);
    },
    [frames.length, onSeek]
  );

  const failureSet = new Set(failureIndices);
  const progress = frames.length > 0 ? (currentIndex / (frames.length - 1)) * 100 : 0;

  return (
    <div className="glass-card p-4 rounded-xl">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
        <span>0ms</span>
        <span className="text-tracex-400 font-mono">
          {frames[currentIndex]?.relative_time_ms?.toFixed(0) ?? 0}ms
        </span>
        <span>
          {frames[frames.length - 1]?.relative_time_ms?.toFixed(0) ?? 0}ms
        </span>
      </div>

      <div
        ref={trackRef}
        onClick={handleClick}
        className="relative h-6 bg-muted/30 rounded-full cursor-pointer overflow-hidden border border-border/30"
      >
        {/* Progress fill */}
        <div
          className="absolute left-0 top-0 h-full bg-tracex-500/20 transition-all duration-300 ease-out pointer-events-none"
          style={{ width: `${progress}%` }}
        />

        {/* Frame type indicators */}
        <div className="absolute inset-0 pointer-events-none">
          {frames.map((frame, idx) => {
            const pos = frames.length > 1 ? (idx / (frames.length - 1)) * 100 : 0;
            let color = "bg-tracex-500/40";
            if (failureSet.has(idx)) color = "bg-danger/80";
            else if (idx === divergenceIndex) color = "bg-warning/80";
            else if (frame.frame_type === "tool_call") color = "bg-blue-500/40";
            else if (frame.frame_type === "llm_response") color = "bg-purple-500/40";

            return (
              <div
                key={frame.frame_id}
                className={`absolute top-1/2 -translate-y-1/2 w-0.5 h-3 rounded-full ${color} opacity-60`}
                style={{ left: `${pos}%` }}
              />
            );
          })}
        </div>

        {/* Current position cursor */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 shadow-glow transition-all duration-300 ease-out pointer-events-none ${
            failureSet.has(currentIndex)
              ? "bg-danger border-red-200 pulse-critical"
              : "bg-tracex-400 border-tracex-200"
          }`}
          style={{ left: `${progress}%`, marginLeft: "-6px" }}
        />
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-1 bg-tracex-500/60 rounded" /> Normal
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-1 bg-warning/80 rounded" /> Divergence
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-1 bg-danger/80 rounded" /> Failure
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-1 bg-blue-500/60 rounded" /> Tool Call
        </div>
        <div className="ml-auto font-mono">
          Frame {currentIndex + 1}/{frames.length}
        </div>
      </div>
    </div>
  );
}
