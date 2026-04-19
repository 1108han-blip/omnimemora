import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiTarget = process.env.OMNIMEMORA_UI_API_TARGET || 'http://localhost:18011'

function rewriteUiEntry(url: string | undefined): string | undefined {
  if (!url) return url
  const [pathname, query = ''] = url.split('?', 2)
  if (pathname === '/agents' || pathname === '/agents/') {
    return query ? `/?${query}` : '/'
  }
  return url
}

function omnimemoraSpaEntryPlugin() {
  return {
    name: 'omnimemora-spa-entry-rewrite',
    configureServer(server: { middlewares: { use: (fn: (req: { method?: string; url?: string; headers: Record<string, string | string[] | undefined> }, res: unknown, next: () => void) => void) => void } }) {
      server.middlewares.use((req, _res, next) => {
        const acceptsHtml = String(req.headers.accept || '').includes('text/html')
        if (req.method === 'GET' && acceptsHtml) {
          req.url = rewriteUiEntry(req.url)
        }
        next()
      })
    },
    configurePreviewServer(server: { middlewares: { use: (fn: (req: { method?: string; url?: string; headers: Record<string, string | string[] | undefined> }, res: unknown, next: () => void) => void) => void } }) {
      server.middlewares.use((req, _res, next) => {
        const acceptsHtml = String(req.headers.accept || '').includes('text/html')
        if (req.method === 'GET' && acceptsHtml) {
          req.url = rewriteUiEntry(req.url)
        }
        next()
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), omnimemoraSpaEntryPlugin()],
  server: {
    port: 5173,
    proxy: {
      '/metrics': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/usage': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/debug': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/agents/live': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/agents/metrics': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/agents/control': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/proxy': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
