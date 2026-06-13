"use client";
// frontend/components/replay/ReplayCenter.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { useReplay } from "@/hooks/useTraces";
import { TimelineScrubber } from "./TimelineScrubber";
import { FrameContent } from "./FrameContent";
import { ArizeInsightsPanel } from "./ArizeInsightsPanel";
import { IncidentReportButton } from "./IncidentReportButton";
import { RootCauseStoryCard } from "./RootCauseStoryCard";
import { NarrationBar } from "./NarrationBar";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import {
  Play, Pause, SkipBack, SkipForward, Rewind, FastForward,
  ArrowLeft, Loader2, AlertTriangle
} from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import type { ReplayFrame } from "@/types";

interface Props {
  traceId: string;
}

const SPEED_OPTIONS = [0.25, 0.5, 1, 2, 5, 10];

export function ReplayCenter({ traceId }: Props) {
  const { data: replayData, isLoading, error } = useReplay(traceId);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const session = replayData?.session;
  const frames = session?.frames ?? [];
  const totalFrames = frames.length;
  const currentFrame: ReplayFrame | undefined = frames[currentFrameIndex];

  // Auto-play to first failure frame on load
  useEffect(() => {
    if (session && session.divergence_frame_index != null) {
      setCurrentFrameIndex(session.divergence_frame_index);
    }
  }, [session?.session_id]);

  // Playback interval
  useEffect(() => {
    if (isPlaying && totalFrames > 0) {
      const fps = (session?.replay_fps ?? 10) * speed;
      const interval = 1000 / fps;
      intervalRef.current = setInterval(() => {
        setCurrentFrameIndex((prev) => {
          if (prev >= totalFrames - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, interval);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, speed, totalFrames, session?.replay_fps]);

  const seekToFrame = useCallback((index: number) => {
    setCurrentFrameIndex(Math.max(0, Math.min(index, totalFrames - 1)));
  }, [totalFrames]);

  const togglePlay = () => setIsPlaying((p) => !p);
  const goToStart = () => { seekToFrame(0); setIsPlaying(false); };
  const goToEnd = () => { seekToFrame(totalFrames - 1); setIsPlaying(false); };
  const stepBack = () => seekToFrame(currentFrameIndex - 1);
  const stepForward = () => seekToFrame(currentFrameIndex + 1);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-tracex-400" />
        <p className="text-muted-foreground text-sm">Building replay session...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
        <AlertTriangle className="w-12 h-12 text-warning" />
        <p>Failed to load replay for trace {traceId}</p>
        <Link href={`/traces/${traceId}`} className="text-tracex-400 text-sm">← Back to trace</Link>
      </div>
    );
  }

  const progressPercent = totalFrames > 0 ? (currentFrameIndex / (totalFrames - 1)) * 100 : 0;

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link href={`/traces/${traceId}`} className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm">
          <ArrowLeft className="w-4 h-4" />
          Back to Trace
        </Link>
        <div className="flex-1">
          <p className="story-label mb-0.5">Replay Center</p>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{session.agent_name}</h1>
          <p className="text-xs text-muted-foreground mt-0.5">{session.trace_id.slice(0, 16)}... · {totalFrames} frames · {(session.total_duration_ms / 1000).toFixed(2)}s</p>
        </div>
        {session.failure_frame_indices.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-danger/10 border border-danger/30 rounded-lg text-sm text-danger pulse-critical">
            <AlertTriangle className="w-4 h-4" />
            {session.failure_frame_indices.length} failure frame{session.failure_frame_indices.length === 1 ? "" : "s"}
          </div>
        )}
      </div>

      {/* Root cause discovery story */}
      <RootCauseStoryCard traceId={traceId} />

      {/* Main Replay Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Frame content */}
        <div className="lg:col-span-2 glass-card rounded-xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-mono">
              Frame {currentFrameIndex + 1} / {totalFrames}
            </span>
            <span className="text-xs text-tracex-400 font-mono">
              +{currentFrame?.relative_time_ms?.toFixed(0) ?? 0}ms
            </span>
          </div>
          <div className="px-4 pt-3">
            <NarrationBar frame={currentFrame} agentName={session.agent_name} />
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <AnimatePresence mode="wait">
              {currentFrame ? (
                <FrameContent key={currentFrame.frame_id} frame={currentFrame} />
              ) : (
                <div className="text-center py-10 text-muted-foreground text-sm">No frame selected</div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Sidebar: frame list + annotations */}
        <div className="glass-card rounded-xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border/50">
            <h3 className="text-sm font-medium">Key Events</h3>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-border/20">
            {session.key_event_indices.map((idx: number) => {
              const frame = frames[idx];
              if (!frame) return null;
              return (
                <button
                  key={idx}
                  onClick={() => seekToFrame(idx)}
                  className={`w-full flex items-start gap-2 px-4 py-3 text-left hover:bg-surface-elevated/50 transition-colors ${
                    currentFrameIndex === idx ? "bg-tracex-500/10" : ""
                  }`}
                >
                  <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${
                    frame.is_failure_frame ? "bg-danger" : frame.is_divergence_point ? "bg-warning" : "bg-tracex-400"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{frame.frame_type.replace(/_/g, " ")}</p>
                    <p className="text-xs text-muted-foreground">+{frame.relative_time_ms?.toFixed(0)}ms</p>
                  </div>
                  <span className="text-xs text-muted-foreground">{idx + 1}</span>
                </button>
              );
            })}
            {session.key_event_indices.length === 0 && (
              <p className="text-center py-6 text-sm text-muted-foreground">No key events</p>
            )}
          </div>
        </div>
      </div>

      {/* Arize MCP insights + AI incident report */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <ArizeInsightsPanel traceId={traceId} />
        </div>
        <IncidentReportButton traceId={traceId} />
      </div>

      {/* Timeline scrubber */}
      <TimelineScrubber
        frames={frames}
        currentIndex={currentFrameIndex}
        failureIndices={session.failure_frame_indices}
        divergenceIndex={session.divergence_frame_index ?? undefined}
        onSeek={seekToFrame}
      />

      {/* Playback Controls */}
      <div className="glass-card p-4 rounded-xl">
        <div className="flex items-center justify-center gap-2 flex-wrap">
          <button onClick={goToStart} className="p-2 rounded-lg hover:bg-surface-elevated transition-colors" title="Start">
            <Rewind className="w-4 h-4" />
          </button>
          <button onClick={stepBack} disabled={currentFrameIndex === 0} className="p-2 rounded-lg hover:bg-surface-elevated transition-colors disabled:opacity-40">
            <SkipBack className="w-4 h-4" />
          </button>
          <button
            onClick={togglePlay}
            className="w-10 h-10 rounded-full bg-tracex-500/20 hover:bg-tracex-500/30 border border-tracex-500/40 flex items-center justify-center transition-all"
          >
            {isPlaying ? <Pause className="w-4 h-4 text-tracex-300" /> : <Play className="w-4 h-4 text-tracex-300 ml-0.5" />}
          </button>
          <button onClick={stepForward} disabled={currentFrameIndex >= totalFrames - 1} className="p-2 rounded-lg hover:bg-surface-elevated transition-colors disabled:opacity-40">
            <SkipForward className="w-4 h-4" />
          </button>
          <button onClick={goToEnd} className="p-2 rounded-lg hover:bg-surface-elevated transition-colors" title="End">
            <FastForward className="w-4 h-4" />
          </button>

          <div className="ml-4 flex items-center gap-1">
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
                  speed === s ? "bg-tracex-500/20 text-tracex-300" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          {session.failure_frame_indices.length > 0 && (
            <button
              onClick={() => seekToFrame(session.failure_frame_indices[0])}
              className="ml-2 px-3 py-1.5 rounded-lg bg-danger/20 text-danger border border-danger/30 text-xs hover:bg-danger/30 transition-colors"
            >
              Jump to Failure
            </button>
          )}

          {session.divergence_frame_index != null && (
            <button
              onClick={() => seekToFrame(session.divergence_frame_index!)}
              className="px-3 py-1.5 rounded-lg bg-warning/20 text-warning border border-warning/30 text-xs hover:bg-warning/30 transition-colors"
            >
              Jump to Divergence
            </button>
          )}

          {session.repair_id && (
            <Link
              href={`/repairs?repair=${session.repair_id}`}
              className="px-3 py-1.5 rounded-lg bg-success/20 text-success border border-success/30 text-xs hover:bg-success/30 transition-colors"
            >
              View Repair →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
