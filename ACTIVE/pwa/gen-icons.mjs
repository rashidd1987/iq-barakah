// Генерирует SVG иконки для PWA
import { writeFileSync } from 'fs'

function makeSVG(size) {
  const r = size / 2
  const innerR = r * 0.38
  const moonR = r * 0.22
  const moonOff = r * 0.09
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <defs>
    <radialGradient id="bg" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#2c5f2d"/>
      <stop offset="100%" stop-color="#0d2410"/>
    </radialGradient>
    <radialGradient id="glow" cx="70%" cy="15%" r="55%">
      <stop offset="0%" stop-color="#c9a84c" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#c9a84c" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <!-- Background -->
  <rect width="${size}" height="${size}" rx="${r * 0.22}" fill="url(#bg)"/>
  <rect width="${size}" height="${size}" rx="${r * 0.22}" fill="url(#glow)"/>
  <!-- Moon crescent -->
  <circle cx="${r + moonOff * 0.5}" cy="${r * 0.52}" r="${moonR}" fill="#e8c96a" opacity="0.95"/>
  <circle cx="${r + moonOff * 2.2}" cy="${r * 0.42}" r="${moonR * 0.82}" fill="#0d2410"/>
  <!-- IQ text -->
  <text x="${r}" y="${r * 1.35}" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif" font-weight="900" font-size="${r * 0.52}" fill="white" letter-spacing="-1">IQ</text>
  <!-- Barakah text -->
  <text x="${r}" y="${r * 1.72}" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif" font-weight="700" font-size="${r * 0.26}" fill="#e8c96a" letter-spacing="0.5">BARAKAH</text>
</svg>`
}

writeFileSync('public/icons/icon-192.svg', makeSVG(192))
writeFileSync('public/icons/icon-512.svg', makeSVG(512))
console.log('SVG icons generated')
