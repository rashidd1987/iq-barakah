if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/pwa/sw-native-v2.js', { scope: '/pwa/', updateViaCache: 'none' })
      .then((registration) => registration.update().catch(() => {}))
      .catch(() => {})
  })
}
