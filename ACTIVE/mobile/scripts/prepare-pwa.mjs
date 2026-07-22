import { copyFile, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const projectRoot = resolve(import.meta.dirname, '..')
const distDir = resolve(projectRoot, 'dist-pwa')
const indexPath = resolve(distDir, 'index.html')

let html = await readFile(indexPath, 'utf8')
html = html.replace(
  '</head>',
  [
    '<link rel="manifest" href="/pwa/manifest.webmanifest">',
    '<link rel="apple-touch-icon" href="/pwa/icon.png">',
    '<meta name="apple-mobile-web-app-capable" content="yes">',
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
    '<script src="/pwa/registerSW.js" defer></script>',
    '</head>',
  ].join(''),
)
await writeFile(indexPath, html)
await copyFile(resolve(projectRoot, 'assets/icon.png'), resolve(distDir, 'icon.png'))
