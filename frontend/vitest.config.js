// 단위·컴포넌트 테스트 (Vitest + Vue Test Utils, jsdom). Vite 설정(@ 별칭, Vue 플러그인)을 그대로 이어받는다.
import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config.js'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      include: ['src/**/*.spec.js'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      setupFiles: ['./src/test/setup.js'],
      restoreMocks: true,
    },
  }),
)
