// frontend/app/layout.tsx
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "TRACE-X — Flight Recorder for AI Agents",
    template: "%s | TRACE-X",
  },
  description:
    "TRACE-X is an autonomous AI agent reliability platform. Capture every trace, detect failures, diagnose root causes, and auto-repair AI agents.",
  keywords: ["AI agents", "reliability", "observability", "LLM monitoring", "agent debugging"],
  authors: [{ name: "TRACE-X Team" }],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "TRACE-X — Flight Recorder for AI Agents",
    description: "Autonomous reliability for AI agents — detect, diagnose, repair.",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0ea5e9",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} font-sans min-h-screen bg-background text-foreground antialiased`}
        suppressHydrationWarning
      >
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
