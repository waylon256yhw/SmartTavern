/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
}

declare global {
  interface Window {
    ST_BACKEND_BASE?: string
    STPromptRouter?: {
      call: (action: string, payload: any, callbacks: any) => Promise<any>
    }
  }
}

export {}
