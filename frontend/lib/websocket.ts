// frontend/lib/websocket.ts
type MessageHandler = (message: any) => void;

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

class WebSocketSingleton {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private connectionHandlers: Set<(connected: boolean) => void> = new Set();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;
  private _isConnected = false;

  connect(channels: string = "traces,failures,repairs,agents"): void {
    if (typeof window === "undefined") return;
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;
    this._connect(channels);
  }

  private _connect(channels: string): void {
    try {
      const url = `${WS_URL}?channels=${encodeURIComponent(channels)}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._isConnected = true;
        this.connectionHandlers.forEach((h) => h(true));
        console.debug("[TRACE-X WS] Connected");
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handlers.forEach((h) => h(data));
        } catch (err) {
          console.debug("[TRACE-X WS] Message parse error:", err);
        }
      };

      this.ws.onclose = (event) => {
        this._isConnected = false;
        this.connectionHandlers.forEach((h) => h(false));

        if (this.shouldReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_DELAY_MS * Math.pow(1.5, this.reconnectAttempts);
          this.reconnectAttempts++;
          this.reconnectTimer = setTimeout(() => this._connect(channels), delay);
          console.debug(`[TRACE-X WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        }
      };

      this.ws.onerror = (error) => {
        console.debug("[TRACE-X WS] Error:", error);
      };
    } catch (error) {
      console.debug("[TRACE-X WS] Connection failed:", error);
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
  }

  subscribe(channels: string[]): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "subscribe", channels }));
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionHandlers.add(handler);
    return () => this.connectionHandlers.delete(handler);
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  ping(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "ping" }));
    }
  }
}

// Singleton instance
export const wsClient = new WebSocketSingleton();
