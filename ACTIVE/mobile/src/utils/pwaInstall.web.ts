export type PwaInstallStatus = 'unsupported' | 'installable' | 'ios' | 'installed'

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

let deferredPrompt: BeforeInstallPromptEvent | null = null
const listeners = new Set<(status: PwaInstallStatus) => void>()

const isStandalone = () =>
  window.matchMedia('(display-mode: standalone)').matches ||
  (window.navigator as Navigator & { standalone?: boolean }).standalone === true

const isIos = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent)

export function getPwaInstallStatus(): PwaInstallStatus {
  if (isStandalone()) return 'installed'
  if (deferredPrompt) return 'installable'
  if (isIos()) return 'ios'
  return 'unsupported'
}

function notify() {
  const status = getPwaInstallStatus()
  listeners.forEach((listener) => listener(status))
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault()
  deferredPrompt = event as BeforeInstallPromptEvent
  notify()
})

window.addEventListener('appinstalled', () => {
  deferredPrompt = null
  notify()
})

export function subscribePwaInstallStatus(listener: (status: PwaInstallStatus) => void) {
  listeners.add(listener)
  listener(getPwaInstallStatus())
  return () => listeners.delete(listener)
}

export async function promptPwaInstall(): Promise<boolean> {
  if (!deferredPrompt) return false
  const prompt = deferredPrompt
  deferredPrompt = null
  await prompt.prompt()
  const choice = await prompt.userChoice
  notify()
  return choice.outcome === 'accepted'
}
