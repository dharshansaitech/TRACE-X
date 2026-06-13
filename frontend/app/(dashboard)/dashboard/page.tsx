// frontend/app/(dashboard)/dashboard/page.tsx
import type { Metadata } from "next";
import { FlightDeck } from "@/components/dashboard/FlightDeck";

export const metadata: Metadata = {
  title: "Flight Deck",
};

export default function DashboardPage() {
  return <FlightDeck />;
}
