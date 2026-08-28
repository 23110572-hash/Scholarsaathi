const rawBackendApiUrl = process.env.BACKEND_API_URL?.trim()

if (!rawBackendApiUrl) {
  throw new Error('BACKEND_API_URL must be set to the public Render backend URL')
}

const backendUrl = new URL(rawBackendApiUrl)
if (backendUrl.protocol !== 'https:') {
  throw new Error('BACKEND_API_URL must use HTTPS')
}

const backendOrigin = `${backendUrl.origin}${backendUrl.pathname.replace(/\/+$/, '')}`

export const config = {
  framework: 'vite',
  installCommand: 'npm ci',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    {
      source: '/api/:path*',
      destination: `${backendOrigin}/api/:path*`,
    },
    {
      source: '/:path*',
      destination: '/index.html',
    },
  ],
}
