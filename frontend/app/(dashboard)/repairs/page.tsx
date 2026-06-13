// frontend/app/(dashboard)/repairs/page.tsx
import type { Metadata } from "next";
import { RepairQueue } from "@/components/repair/RepairQueue";

export const metadata: Metadata = {
  title: "Repair Queue",
};

export default function RepairsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Repair Queue</h1>
        <p className="text-muted-foreground mt-1">
          Review and apply AI-generated repairs for detected failures
        </p>
      </div>
      <RepairQueue />
    </div>
  );
}
