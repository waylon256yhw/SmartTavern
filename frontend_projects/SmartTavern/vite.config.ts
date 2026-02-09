import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'node:path'
import { defineConfig, build as viteBuild, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const srcDir = fileURLToPath(new URL('./src', import.meta.url))

function workflowBundlePlugin(): Plugin {
  return {
    name: 'workflow-bundle',
    apply: 'build',
    async closeBundle() {
      await viteBuild({
        configFile: false,
        logLevel: 'warn',
        resolve: {
          alias: { '/src': srcDir },
        },
        publicDir: false,
        build: {
          emptyOutDir: false,
          outDir: 'dist/assets/workflows',
          lib: {
            entry: resolve(srcDir, 'workflow/workflows/default-thread-orchestrator.js'),
            formats: ['es'],
            fileName: () => 'default-thread-orchestrator.js',
          },
        },
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools(), workflowBundlePlugin()],
  resolve: {
    alias: {
      '@': srcDir,
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          'pinia-vendor': ['pinia'],
          'workflow-core': [
            './src/services/dataCatalog.ts',
            './src/workflow/core/host.ts',
            './src/stores/chatVariables.ts',
          ],
        },
      },
    },
  },
})
