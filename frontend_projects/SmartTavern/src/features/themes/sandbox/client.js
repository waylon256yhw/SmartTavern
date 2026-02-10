// SmartTavern Theme Runtime - Sandbox RPC Client (v2)
// Runs inside sandboxed iframes (guarded mode). All API calls go through postMessage RPC.
// In guarded mode, window.parent is NOT accessible (no allow-same-origin).

;(function () {
  'use strict'

  let _seq = 0
  const _pending = Object.create(null)
  const _handlers = Object.create(null)
  const RPC_TIMEOUT = 8000
  const _nonce = window.__stSandboxNonce || null

  function _wrap(payload) {
    var msg = { __stSandbox: payload }
    if (_nonce) msg.__stNonce = _nonce
    return msg
  }

  function rpcCall(method, args) {
    return new Promise(function (resolve, reject) {
      var id = ++_seq
      var timer = setTimeout(function () {
        delete _pending[id]
        reject(new Error('RPC timeout: ' + method))
      }, RPC_TIMEOUT)
      _pending[id] = { resolve: resolve, reject: reject, timer: timer }
      try {
        window.parent.postMessage(_wrap({ id: id, method: method, args: args || [] }), '*')
      } catch (e) {
        clearTimeout(timer)
        delete _pending[id]
        reject(e)
      }
    })
  }

  function handleMessage(ev) {
    if (ev.source !== window.parent) return
    var data = ev.data
    if (!data || !data.__stSandbox) return
    var msg = data.__stSandbox

    // Incoming request from host (host calling into iframe)
    if (msg.id && msg.method && !('result' in msg) && !('error' in msg)) {
      var handler = _handlers[msg.method]
      if (!handler) {
        try {
          window.parent.postMessage(
            _wrap({ id: msg.id, method: msg.method, error: 'no handler' }),
            '*',
          )
        } catch (_) {}
        return
      }
      Promise.resolve()
        .then(function () {
          return handler.apply(null, msg.args || [])
        })
        .then(function (result) {
          window.parent.postMessage(_wrap({ id: msg.id, method: msg.method, result: result }), '*')
        })
        .catch(function (e) {
          window.parent.postMessage(
            _wrap({ id: msg.id, method: msg.method, error: (e && e.message) || 'error' }),
            '*',
          )
        })
      return
    }

    // Response to our outgoing request
    var id = msg.id
    var entry = _pending[id]
    if (!entry) return
    clearTimeout(entry.timer)
    delete _pending[id]
    if (msg.error) entry.reject(new Error(msg.error))
    else entry.resolve(msg.result)
  }

  // Register handler for incoming calls from host
  _handlers['ping'] = function (t) {
    return { ok: true, t: Date.now(), echo: t || null }
  }

  window.addEventListener('message', handleMessage)

  // Expose RPC primitives for guarded bridge script
  window.__stRpc = {
    call: rpcCall,
    registerHandler: function (method, fn) {
      _handlers[method] = fn
    },
    unregisterHandler: function (method) {
      delete _handlers[method]
    },
  }

  // Announce ready
  try {
    window.parent.postMessage(_wrap({ id: 0, method: 'ready', args: [Date.now()] }), '*')
  } catch (_) {}
})()
