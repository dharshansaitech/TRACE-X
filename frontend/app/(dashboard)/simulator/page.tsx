// frontend/app/(dashboard)/simulator/page.tsx
import type { Metadata } from "next";
import { WhatIfPanel } from "@/components/simulator/WhatIfPanel";

export const metadata: Metadata = {
  title: "What-If Simulator",
};

export default function SimulatorPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">What-If Simulator</h1>
        <p className="text-muted-foreground mt-1">
          Simulate failure scenarios and validate repairs in a Digital Twin environment
        </p>
      </div>
      <WhatIfPanel />
    </div>
  );
}
