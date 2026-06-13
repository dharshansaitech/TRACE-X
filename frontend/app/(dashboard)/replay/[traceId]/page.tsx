// frontend/app/(dashboard)/replay/[traceId]/page.tsx
import type { Metadata } from "next";
import { ReplayCenter } from "@/components/replay/ReplayCenter";

export const metadata: Metadata = {
  title: "Replay Center",
};

interface Props {
  params: Promise<{ traceId: string }>;
}

export default async function ReplayPage({ params }: Props) {
  const { traceId } = await params;
  return <ReplayCenter traceId={traceId} />;
}
