import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  getVersion: (): Promise<string> => ipcRenderer.invoke('app:getVersion'),
  getOpenAtLogin: (): Promise<{ openAtLogin: boolean; openAsHidden?: boolean }> =>
    ipcRenderer.invoke('app:getOpenAtLogin'),
  setOpenAtLogin: (
    enabled: boolean
  ): Promise<{ ok: boolean; openAtLogin: boolean; message?: string }> =>
    ipcRenderer.invoke('app:setOpenAtLogin', enabled),
  setWindowMode: (mode: 'login' | 'workbench'): Promise<boolean> =>
    ipcRenderer.invoke('window:setMode', mode),
  saveRemoteFile: (url: string, defaultName?: string): Promise<{ ok: boolean; path?: string }> =>
    ipcRenderer.invoke('file:saveRemote', url, defaultName || '')
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore
  window.electron = electronAPI
  // @ts-ignore
  window.api = api
}
