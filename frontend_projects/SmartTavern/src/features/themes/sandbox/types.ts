export type TrustLevel = 'trusted' | 'guarded' | 'strict'

export interface SandboxCapabilities {
  allowSameOrigin: boolean
  allowScripts: boolean
  bridgeMode: 'full' | 'rpc' | 'none'
  readState: boolean
  writeState: boolean
  llmAccess: boolean
  uiActions: 'full' | 'readonly' | 'none'
  hostEvents: boolean
}

export const CAPABILITIES: Record<TrustLevel, SandboxCapabilities> = {
  trusted: {
    allowSameOrigin: true,
    allowScripts: true,
    bridgeMode: 'full',
    readState: true,
    writeState: true,
    llmAccess: true,
    uiActions: 'full',
    hostEvents: true,
  },
  guarded: {
    allowSameOrigin: false,
    allowScripts: true,
    bridgeMode: 'rpc',
    readState: true,
    writeState: false,
    llmAccess: false,
    uiActions: 'readonly',
    hostEvents: false,
  },
  strict: {
    allowSameOrigin: false,
    allowScripts: false,
    bridgeMode: 'none',
    readState: false,
    writeState: false,
    llmAccess: false,
    uiActions: 'none',
    hostEvents: false,
  },
}

export const SANDBOX_ATTRS: Record<TrustLevel, string> = {
  trusted:
    'allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-popups-to-escape-sandbox allow-presentation allow-pointer-lock allow-orientation-lock allow-top-navigation-by-user-activation allow-storage-access-by-user-activation',
  guarded: 'allow-scripts allow-forms allow-modals allow-presentation',
  strict: '',
}

export const ALLOW_ATTRS: Record<TrustLevel, string> = {
  trusted:
    'fullscreen *; clipboard-read *; clipboard-write *; geolocation *; microphone *; camera *; autoplay *; encrypted-media *; payment *; usb *; serial *; midi *; gyroscope *; magnetometer *; xr-spatial-tracking *; display-capture *; gamepad *; idle-detection *',
  guarded: 'fullscreen *; clipboard-read *; autoplay *',
  strict: '',
}
