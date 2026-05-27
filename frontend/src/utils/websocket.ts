/**
 * WebSocket 实时通信
 */

import { ref, onUnmounted } from 'vue'
import { useTradeStore, useCandidateStore, useSystemStore } from '@/stores'

type EventHandler = (data: any) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private handlers: Map<string, EventHandler[]> = new Map()
  private _connected = ref(false)
  private _lastMessage = ref<any>(null)
  
  constructor(url?: string) {
    // 自动检测 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = url || `${protocol}//${window.location.host}/ws`
  }
  
  get connected() {
    return this._connected.value
  }
  
  get lastMessage() {
    return this._lastMessage.value
  }
  
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }
    
    try {
      this.ws = new WebSocket(this.url)
      
      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this._connected.value = true
        this.reconnectAttempts = 0
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this._lastMessage.value = message
          this.handleMessage(message)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }
      
      this.ws.onclose = () => {
        console.log('WebSocket disconnected')
        this._connected.value = false
        this.scheduleReconnect()
      }
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      this.scheduleReconnect()
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._connected.value = false
  }
  
  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached')
      return
    }
    
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => this.connect(), delay)
  }
  
  private handleMessage(message: any) {
    const { type, data } = message
    
    // 调用注册的处理器
    const handlers = this.handlers.get(type) || []
    handlers.forEach(handler => {
      try {
        handler(data)
      } catch (e) {
        console.error(`Event handler error for ${type}:`, e)
      }
    })
    
    // 通配符处理器
    const wildcardHandlers = this.handlers.get('*') || []
    wildcardHandlers.forEach(handler => {
      try {
        handler({ type, data })
      } catch (e) {
        console.error('Wildcard handler error:', e)
      }
    })
  }
  
  on(eventType: string, handler: EventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, [])
    }
    this.handlers.get(eventType)!.push(handler)
  }
  
  off(eventType: string, handler: EventHandler) {
    const handlers = this.handlers.get(eventType)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }
  
  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }
}

// 全局单例
let client: WebSocketClient | null = null

export function useWebSocket() {
  if (!client) {
    client = new WebSocketClient()
  }
  
  return {
    client,
    connected: client.connected,
    lastMessage: client.lastMessage,
  }
}

export function useRealtimeSync() {
  const tradeStore = useTradeStore()
  const candidateStore = useCandidateStore()
  const systemStore = useSystemStore()
  
  const { client } = useWebSocket()
  
  // 注册事件处理器
  function setupHandlers() {
    // 交易事件
    client.on('trade.opened', (data) => {
      console.log('Trade opened:', data)
      tradeStore.fetchTrades()
    })
    
    client.on('trade.closed', (data) => {
      console.log('Trade closed:', data)
      tradeStore.fetchTrades()
    })
    
    client.on('trade.updated', (data) => {
      console.log('Trade updated:', data)
      tradeStore.fetchTrades()
    })
    
    // 候选事件
    client.on('candidate.added', (data) => {
      console.log('Candidate added:', data)
      candidateStore.fetchCandidates()
    })
    
    client.on('candidate.triggered', (data) => {
      console.log('Candidate triggered:', data)
      candidateStore.fetchCandidates()
    })
    
    // 风控事件
    client.on('risk.alert', (data) => {
      console.warn('Risk alert:', data)
      // 可以显示通知
      showNotification('风控告警', data.message || data.alert_type)
    })
    
    client.on('risk.state_changed', (data) => {
      console.log('Risk state changed:', data)
    })
    
    // 系统事件
    client.on('system.panic', (data) => {
      console.error('SYSTEM PANIC:', data)
      showNotification('系统警告', '紧急全平仓已触发', 'error')
    })
    
    client.on('system.health', (data) => {
      console.log('System health:', data)
    })
    
    // 信号事件
    client.on('signal.triggered', (data) => {
      console.log('Signal triggered:', data)
      showNotification('新信号', `${data.symbol} ${data.direction}`, 'info')
    })
    
    // 执行事件
    client.on('execution.order_filled', (data) => {
      console.log('Order filled:', data)
    })
    
    client.on('execution.order_failed', (data) => {
      console.error('Order failed:', data)
      showNotification('下单失败', data.error, 'error')
    })
    
    // 配置变更
    client.on('config.changed', (data) => {
      console.log('Config changed:', data)
      systemStore.fetchConfig()
    })
  }
  
  // 通知显示（简单实现）
  function showNotification(title: string, message: string, type: string = 'info') {
    // 使用浏览器通知 API
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { body: message })
    }
    
    // 或者可以集成到 UI 通知系统
    console.log(`[${type.toUpperCase()}] ${title}: ${message}`)
  }
  
  // 请求通知权限
  async function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission()
    }
  }
  
  // 连接并启动同步
  function startSync() {
    setupHandlers()
    client.connect()
    requestNotificationPermission()
  }
  
  // 断开连接
  function stopSync() {
    client.disconnect()
  }
  
  return {
    startSync,
    stopSync,
    connected: client.connected,
  }
}
