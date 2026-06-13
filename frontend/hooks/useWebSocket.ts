"use client";
// frontend/hooks/useWebSocket.ts
import { useEffect, useState, useCallback, useRef } from "react";
import { wsClient } from "@/lib/websocket";

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: any | null;
  subscribe: (channels: string[]) => void;
  send: (data: any) => void;
}

export function useWebSocket(
  channels: string[] = ["traces", "failures", "repairs"]
): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    // Connect
    wsClient.connect(channels.join(","));
    setIsConnected(wsClient.isConnected);

    // Register handlers
    const unsubMessage = wsClient.onMessage((msg) => {
      if (mountedRef.current && msg.type !== "pong" && msg.type !== "heartbeat") {
        setLastMessage(msg);
      }
    });

    const unsubConnection = wsClient.onConnectionChange((connected) => {
      if (mountedRef.current) {
        setIsConnected(connected);
      }
    });

    // Heartbeat
    const heartbeat = setInterval(() => {
      wsClient.ping();
    }, 25000);

    return () => {
      mountedRef.current = false;
      unsubMessage();
      unsubConnection();
      clearInterval(heartbeat);
    };
  }, []);

  const subscribe = useCallback((newChannels: string[]) => {
    wsClient.subscribe(newChannels);
  }, []);

  const send = useCallback((data: any) => {
    wsClient.ping();
  }, []);

  return { isConnected, lastMessage, subscribe, send };
}

// Hook for specific channel
export function useWebSocketChannel(channel: string) {
  const [messages, setMessages] = useState<any[]>([]);
  const { lastMessage } = useWebSocket([channel]);

  useEffect(() => {
    if (lastMessage) {
      setMessages((prev) => [lastMessage, ...prev.slice(0, 49)]);
    }
  }, [lastMessage]);

  return { messages, lastMessage };
}
