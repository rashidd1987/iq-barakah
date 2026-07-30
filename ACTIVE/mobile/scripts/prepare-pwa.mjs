import { copyFile, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const projectRoot = resolve(import.meta.dirname, '..')
const distDir = resolve(projectRoot, 'dist-pwa')
const indexPath = resolve(distDir, 'index.html')
const requestedBasePath = process.env.PWA_BASE_PATH || '/pwa'
const basePath = `/${requestedBasePath.replace(/^\/+|\/+$/g, '')}`
const releaseMarker = 'diagnostic-20260730'

let html = await readFile(indexPath, 'utf8')
html = html.replace(
  '</head>',
  [
    `<link rel="manifest" href="${basePath}/manifest.webmanifest">`,
    `<link rel="apple-touch-icon" href="${basePath}/icon.png">`,
    '<meta name="apple-mobile-web-app-capable" content="yes">',
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
    `<script src="${basePath}/registerSW.js?v=${releaseMarker}" defer></script>`,
    '</head>',
  ].join(''),
)
await writeFile(indexPath, html)
await copyFile(resolve(projectRoot, 'assets/icon.png'), resolve(distDir, 'icon.png'))

for (const fileName of ['manifest.webmanifest', 'registerSW.js', 'sw.js', 'sw-native-v2.js']) {
  const filePath = resolve(distDir, fileName)
  const content = await readFile(filePath, 'utf8')
  await writeFile(filePath, content.replaceAll('/pwa/', `${basePath}/`))
}
