if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/pwa/sw-native-v2.js?v=diagnostic-20260730', { scope: '/pwa/', updateViaCache: 'none' })
      .then((registration) => registration.update().catch(() => {}))
      .catch(() => {})
  })
}
