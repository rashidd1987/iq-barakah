export type PwaInstallStatus = 'unsupported' | 'installable' | 'ios' | 'android' | 'installed'

export interface PwaInstallGuide {
  title: string
  steps: string[]
  note: string
}

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

let deferredPrompt: BeforeInstallPromptEvent | null = null
const listeners = new Set<(status: PwaInstallStatus) => void>()

const isStandalone = () =>
  window.matchMedia('(display-mode: standalone)').matches ||
  (window.navigator as Navigator & { standalone?: boolean }).standalone === true

const isIos = () =>
  /iphone|ipad|ipod/i.test(window.navigator.userAgent) ||
  (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1)
const isAndroid = () => /android/i.test(window.navigator.userAgent)

export function getPwaInstallStatus(): PwaInstallStatus {
  if (isStandalone()) return 'installed'
  if (deferredPrompt) return 'installable'
  if (isIos()) return 'ios'
  if (isAndroid()) return 'android'
  return 'unsupported'
}

export function getPwaInstallGuide(status: PwaInstallStatus): PwaInstallGuide {
  if (status === 'ios') {
    return {
      title: 'Установка на iPhone',
      steps: [
        'Откройте IQ Barakah именно в Safari.',
        'Нажмите кнопку «Поделиться» внизу экрана.',
        'Выберите «На экран Домой», затем нажмите «Добавить».',
      ],
      note: 'После установки IQ Barakah откроется отдельным приложением с главного экрана.',
    }
  }
  if (status === 'android') {
    return {
      title: 'Установка на Android',
      steps: [
        'Откройте меню браузера — значок ⋮ в правом верхнем углу.',
        'Выберите «Установить приложение» или «Добавить на главный экран».',
        'Подтвердите установку.',
      ],
      note: 'Название пункта может немного отличаться в Chrome, Samsung Internet и других браузерах.',
    }
  }
  return {
    title: 'Установка на телефон',
    steps: [
      'Откройте эту страницу на iPhone или Android.',
      'На iPhone используйте Safari, на Android — меню браузера.',
      'Выберите добавление IQ Barakah на главный экран.',
    ],
    note: 'На компьютере установка на экран телефона недоступна.',
  }
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
