const fs = require('node:fs')

const config = {
  apiBaseUrl: process.env.VITE_API_URL || '',
  googleClientId: process.env.VITE_GOOGLE_CLIENT_ID || '',
}

fs.writeFileSync(
  '/app/dist/runtime-config.js',
  `window.__ETF_RUNTIME_CONFIG__ = ${JSON.stringify(config)};\n`,
)
