"use client";
// frontend/components/replay/NarrationBar.tsx
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { ReplayFrame } from "@/types";
import { narrateFrame } from "@/lib/narration";

interface Props {
  frame?: ReplayFrame;
  agentName?: string;
}

export function NarrationBar({ frame, agentName }: Props) {
  if (!frame) return null;

  const text = narrateFrame(frame, agentName);

  return (
    <div className="narration-bar flex items-start gap-2.5">
      <Sparkles className="w-4 h-4 text-tracex-400 flex-shrink-0 mt-0.5" />
      <AnimatePresence mode="wait">
        <motion.p
          key={frame.frame_id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
        >
          {text}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}
