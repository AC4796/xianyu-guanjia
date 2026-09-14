/** 安全调用主进程窗口模式切换（非 Electron 环境忽略） */
export async function setWindowMode(mode: 'login' | 'workbench'): Promise<void> {
  try {
    await window.api?.setWindowMode?.(mode)
  } catch {
    /* ignore */
  }
}
