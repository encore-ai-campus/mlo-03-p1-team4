// 린트 설정 (ESLint flat config). create-vue 공식 템플릿 구성을 따르고, 접근성 규칙을 더했다.
// 실행 순서: oxlint(빠른 1차) → eslint(Vue 템플릿·접근성·테스트 규칙). oxlint가 보는 규칙은 eslint에서 끈다(마지막 줄).
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import pluginVueA11y from 'eslint-plugin-vuejs-accessibility'
import pluginPlaywright from 'eslint-plugin-playwright'
import pluginVitest from '@vitest/eslint-plugin'
import pluginOxlint from 'eslint-plugin-oxlint'

export default defineConfig([
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,js,mjs}'],
  },

  globalIgnores(['**/dist/**', '**/coverage/**', '**/playwright-report/**', '**/test-results/**']),

  {
    languageOptions: {
      globals: { ...globals.browser },
    },
  },
  {
    name: 'app/node-configs',
    files: ['*.config.js'],
    languageOptions: { globals: { ...globals.node } },
  },

  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  ...pluginVueA11y.configs['flat/recommended'],

  {
    name: 'app/rules',
    rules: {
      'vue/no-unused-vars': 'error',
      'vue/require-v-for-key': 'error',
      'vue/no-mutating-props': 'error',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
      // UiInput처럼 라벨을 컴포넌트 안에서 연결하는 래퍼가 있어 이 규칙은 경고로만 본다
      'vuejs-accessibility/label-has-for': 'off',
      'vuejs-accessibility/form-control-has-label': 'warn',
      // 오류 칸으로 포커스를 옮기는 등 의도한 경우가 있어 경고로만
      'vuejs-accessibility/no-autofocus': 'warn',
    },
  },

  {
    ...pluginPlaywright.configs['flat/recommended'],
    files: ['e2e/**/*.spec.js'],
    rules: {
      ...pluginPlaywright.configs['flat/recommended'].rules,
      // '빈 칸이 없으면 건너뜀'처럼 조건이 있는 skip은 허용
      'playwright/no-skipped-test': ['warn', { allowConditional: true }],
      // 접근성 검사 도우미(expectNoSerious) 안에 expect가 있다
      'playwright/expect-expect': ['warn', { assertFunctionNames: ['expectNoSerious', 'toastSettled'] }],
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*', 'src/**/*.spec.js'],
  },

  ...pluginOxlint.buildFromOxlintConfigFile('.oxlintrc.json'),
])
