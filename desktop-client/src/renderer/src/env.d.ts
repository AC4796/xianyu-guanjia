/// <reference types="vite/client" />

type BackendStatus = {
  ready: boolean
  starting: boolean
  message: string
  projectRoot: string
  python: string
}

interface Window {
  api?: {
    getVersion?: () => Promise<string>
    getBackendStatus?: () => Promise<BackendStatus>
    ensureBackend?: () => Promise<BackendStatus>
    resetAdmin?: () => Promise<{ ok: boolean; message: string }>
    getOpenAtLogin?: () => Promise<{ openAtLogin: boolean; openAsHidden?: boolean }>
    setOpenAtLogin?: (
      enabled: boolean
    ) => Promise<{ ok: boolean; openAtLogin: boolean; message?: string }>
    setWindowMode?: (mode: 'login' | 'workbench') => Promise<boolean>
    saveRemoteFile?: (url: string, defaultName?: string) => Promise<{ ok: boolean; path?: string }>
  }
}
