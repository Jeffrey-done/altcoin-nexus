/**
 * WebSocket 客户端 - 自动重连，事件分发
 */
import { ref } from 'vue'

type Handler = (data: any) => void

class NexusWebSocket {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Handler[]>()
  private reconnectAttempts = 0
  public connected = ref(false)

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.ws = new WebSocket(`${proto}//${location.host}/ws`)
    this.ws.onopen = () => { this.connected.value = true; this.reconnectAttempts = 0 }
    this.ws.onclose = () => { this.connected.value = false; this.scheduleReconnect() }
    this.ws.onerror = () => { this.ws?.close() }
    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        this.dispatch(msg.type, msg.data)
      } catch {}
    }
  }

  disconnect() { this.ws?.close(); this.ws = null }

  on(type: string, handler: Handler) {
    if (!this.handlers.has(type)) this.handlers.set(type, [])
    this.handlers.get(type)!.push(handler)
  }

  off(type: string, handler: Handler) {
    const list = this.handlers.get(type)
    if (list) {
      const idx = list.indexOf(handler)
      if (idx > -1) list.splice(idx, 1)
    }
  }

  private dispatch(type: string, data: any) {
    this.handlers.get(type)?.forEach(h => { try { h(data) } catch {} })
    this.handlers.get('*')?.forEach(h => { try { h({ type, data }) } catch {} })
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= 10) return
    this.reconnectAttempts++
    setTimeout(() => this.connect(), Math.min(1000 * 2 ** this.reconnectAttempts, 30000))
  }
}

let instance: NexusWebSocket | null = null
export function useWebSocket() {
  if (!instance) instance = new NexusWebSocket()
  return instance
}
