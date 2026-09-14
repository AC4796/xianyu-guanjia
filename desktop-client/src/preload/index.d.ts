import { ElectronAPI } from '@electron-toolkit/preload'

export interface DesktopApi {
  getVersion: () => Promise<string>
  getOpenAtLogin: () => Promise<{ openAtLogin: boolean; openAsHidden?: boolean }>
  setOpenAtLogin: (
    enabled: boolean
  ) => Promise<{ ok: boolean; openAtLogin: boolean; message?: string }>
  setWindowMode: (mode: 'login' | 'workbench') => Promise<boolean>
  saveRemoteFile: (url: string, defaultName?: string) => Promise<{ ok: boolean; path?: string }>
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: DesktopApi
  }
}

export {}
