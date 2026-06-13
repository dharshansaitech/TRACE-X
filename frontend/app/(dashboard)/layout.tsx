// frontend/app/(dashboard)/layout.tsx
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { DemoModeBanner } from "@/components/layout/DemoModeBanner";
import { IncidentAlertOverlay } from "@/components/dashboard/IncidentAlertOverlay";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Global incident alert overlay */}
      <IncidentAlertOverlay />

      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header />
        <DemoModeBanner />
        <main className="flex-1 overflow-y-auto p-6 aviation-grid">
          {children}
        </main>
      </div>
    </div>
  );
}
