const staticConfig = require('./app.json')

const requestedBasePath = process.env.PWA_BASE_PATH || '/pwa'
const basePath = `/${requestedBasePath.replace(/^\/+|\/+$/g, '')}`

module.exports = {
  ...staticConfig.expo,
  web: {
    ...staticConfig.expo.web,
    scope: `${basePath}/`,
  },
  experiments: {
    ...staticConfig.expo.experiments,
    baseUrl: basePath,
  },
}
