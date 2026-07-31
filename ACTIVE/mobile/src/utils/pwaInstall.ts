export type PwaInstallStatus = 'unsupported' | 'installable' | 'ios' | 'android' | 'installed'

export interface PwaInstallGuide {
  title: string
  steps: string[]
  note: string
}

export function getPwaInstallStatus(): PwaInstallStatus {
  return 'unsupported'
}

export function subscribePwaInstallStatus(_listener: (status: PwaInstallStatus) => void) {
  return () => {}
}

export async function promptPwaInstall(): Promise<boolean> {
  return false
}

export function getPwaInstallGuide(_status: PwaInstallStatus): PwaInstallGuide {
  return {
    title: 'Установка на телефон',
    steps: [],
    note: '',
  }
}
