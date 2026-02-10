import type { TrustLevel, SandboxCapabilities } from './types'
import { CAPABILITIES } from './types'

const DEFAULT_TIMEOUT = 4000

interface RpcRequest {
  id: number
  method: string
  args?: any[]
}

interface RpcResponse {
  id: number
  method: string
  result?: any
  error?: string
}

interface PendingRequest {
  resolve: (value: any) => void
  reject: (reason?: any) => void
  timer: ReturnType<typeof setTimeout>
}

type RpcHandler = (...args: any[]) => any | Promise<any>

export interface SandboxHostOptions {
  trustLevel?: TrustLevel
  timeoutMs?: number
  nonce?: string
}

export interface SandboxHost {
  post(method: string, args?: any[]): Promise<any>
  ping(): Promise<any>
  registerHandler(method: string, handler: RpcHandler): void
  unregisterHandler(method: string): void
  dispose(): void
  iframe: HTMLIFrameElement
  trustLevel: TrustLevel
  capabilities: SandboxCapabilities
}

export function createSandboxHost(
  iframe: HTMLIFrameElement,
  options: SandboxHostOptions = {},
): SandboxHost {
  if (!iframe || !(iframe instanceof HTMLIFrameElement)) {
    throw new Error('[SandboxHost] iframe element required')
  }

  const trustLevel = options.trustLevel ?? 'trusted'
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT
  const nonce = options.nonce ?? null
  const capabilities = CAPABILITIES[trustLevel]

  let seq = 0
  const pending = new Map<number, PendingRequest>()
  const handlers = new Map<string, RpcHandler>()

  function postToIframe(method: string, args: any[] = []): Promise<any> {
    const id = ++seq
    const msg: RpcRequest = { id, method, args }
    try {
      iframe.contentWindow?.postMessage({ __stSandbox: msg }, '*')
    } catch (e) {
      console.warn('[SandboxHost] postMessage failed:', e)
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id)
        reject(new Error(`Sandbox request timed out: ${method}`))
      }, timeoutMs)
      pending.set(id, { resolve, reject, timer })
    })
  }

  async function handleIncoming(msg: RpcRequest): Promise<RpcResponse> {
    const { id, method, args = [] } = msg
    const handler = handlers.get(method)
    if (!handler) {
      return { id, method, error: `No handler for method: ${method}` }
    }
    try {
      const result = await handler(...args)
      return { id, method, result }
    } catch (e: any) {
      return { id, method, error: e?.message || 'handler error' }
    }
  }

  function onMessage(ev: MessageEvent): void {
    if (ev.source !== iframe.contentWindow) return
    const data = ev.data
    if (!data || !data.__stSandbox) return
    if (nonce && data.__stNonce !== nonce) return
    const msg = data.__stSandbox

    if (msg.id && msg.method && !('result' in msg) && !('error' in msg)) {
      handleIncoming(msg as RpcRequest).then((response) => {
        try {
          iframe.contentWindow?.postMessage({ __stSandbox: response }, '*')
        } catch (_) {}
      })
      return
    }

    const { id, error, result } = msg as RpcResponse
    if (!id || !pending.has(id)) return
    const entry = pending.get(id)!
    clearTimeout(entry.timer)
    pending.delete(id)
    if (error) entry.reject(new Error(error))
    else entry.resolve(result)
  }

  window.addEventListener('message', onMessage)

  function dispose(): void {
    window.removeEventListener('message', onMessage)
    for (const [, entry] of pending) {
      clearTimeout(entry.timer)
      entry.reject(new Error('Sandbox disposed'))
    }
    pending.clear()
    handlers.clear()
  }

  async function ping(): Promise<any> {
    return postToIframe('ping', [Date.now()])
  }

  function registerHandler(method: string, handler: RpcHandler): void {
    handlers.set(method, handler)
  }

  function unregisterHandler(method: string): void {
    handlers.delete(method)
  }

  return {
    post: postToIframe,
    ping,
    registerHandler,
    unregisterHandler,
    dispose,
    iframe,
    trustLevel,
    capabilities,
  }
}

export default { createSandboxHost }
