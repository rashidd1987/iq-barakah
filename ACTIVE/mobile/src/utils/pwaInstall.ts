export type PwaInstallStatus = 'unsupported' | 'installable' | 'ios' | 'installed'

export function getPwaInstallStatus(): PwaInstallStatus {
  return 'unsupported'
}

export function subscribePwaInstallStatus(_listener: (status: PwaInstallStatus) => void) {
  return () => {}
}

export async function promptPwaInstall(): Promise<boolean> {
  return false
}
