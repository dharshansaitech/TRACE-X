"use client";
// frontend/components/layout/Header.tsx
import { Bell, Search, Wifi, WifiOff } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useState, useEffect } from "react";

export function Header() {
  const { isConnected, lastMessage } = useWebSocket();
  const [notifications, setNotifications] = useState<string[]>([]);
  const [showNotif, setShowNotif] = useState(false);

  useEffect(() => {
    if (lastMessage?.type === "failure_detected" || lastMessage?.type === "diagnosis_complete") {
      setNotifications((prev) => [
        `${lastMessage.type.replace(/_/g, " ")}: ${lastMessage.trace_id?.slice(0, 8) ?? ""}`,
        ...prev.slice(0, 9),
      ]);
    }
  }, [lastMessage]);

  return (
    <header className="h-14 border-b border-border/50 bg-card/50 backdrop-blur-sm flex items-center justify-between px-6 flex-shrink-0">
      {/* Search */}
      <div className="relative w-72">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search traces, agents..."
          className="w-full pl-10 pr-4 py-1.5 bg-surface-elevated border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-tracex-500/50 text-foreground placeholder:text-muted-foreground"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground/50 font-mono">
          ⌘K
        </kbd>
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        {/* Connection status */}
        <div className="flex items-center gap-1.5">
          {isConnected ? (
            <>
              <div className="live-dot" />
              <span className="text-xs text-success">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-warning" />
              <span className="text-xs text-warning">Reconnecting...</span>
            </>
          )}
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotif(!showNotif)}
            className="relative p-1.5 rounded-lg hover:bg-surface-elevated transition-colors"
          >
            <Bell className="w-4.5 h-4.5 text-muted-foreground" />
            {notifications.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-danger rounded-full" />
            )}
          </button>

          {showNotif && (
            <div className="absolute right-0 top-full mt-2 w-80 glass-card rounded-xl border border-border/50 shadow-xl z-50">
              <div className="px-4 py-3 border-b border-border/30">
                <p className="font-medium text-sm">Notifications</p>
              </div>
              {notifications.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground text-center">No new notifications</p>
              ) : (
                <div className="max-h-64 overflow-y-auto">
                  {notifications.map((n, i) => (
                    <div key={i} className="px-4 py-2.5 border-b border-border/20 last:border-0 text-sm">
                      {n}
                    </div>
                  ))}
                </div>
              )}
              {notifications.length > 0 && (
                <button
                  onClick={() => setNotifications([])}
                  className="w-full px-4 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>
          )}
        </div>

        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-tracex-500/30 border border-tracex-500/50 flex items-center justify-center text-tracex-300 text-xs font-bold">
          TX
        </div>
      </div>
    </header>
  );
}
