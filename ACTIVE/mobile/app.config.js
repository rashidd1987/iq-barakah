const staticConfig = require('./app.json')

const requestedBasePath = process.env.PWA_BASE_PATH || '/pwa'
const basePath = `/${requestedBasePath.replace(/^\/+|\/+$/g, '')}`
const isPreview = process.env.APP_VARIANT === 'preview'

module.exports = {
  ...staticConfig.expo,
  name: isPreview ? 'IQ Barakah Preview' : staticConfig.expo.name,
  ios: {
    ...staticConfig.expo.ios,
    bundleIdentifier: isPreview ? 'ru.iqbarakah.mobile.preview' : staticConfig.expo.ios.bundleIdentifier,
  },
  android: {
    ...staticConfig.expo.android,
    package: isPreview ? 'ru.iqbarakah.mobile.preview' : staticConfig.expo.android.package,
    googleServicesFile: isPreview ? undefined : staticConfig.expo.android.googleServicesFile,
  },
  web: {
    ...staticConfig.expo.web,
    scope: `${basePath}/`,
  },
  experiments: {
    ...staticConfig.expo.experiments,
    baseUrl: basePath,
  },
}
