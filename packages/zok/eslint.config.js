export default [
  {
    ignores: ['dist/**', 'build/**', '.next/**', 'node_modules/**', 'pages/**'],
  },
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: 'readonly',
        document: 'readonly',
        fetch: 'readonly',
        console: 'readonly',
        Headers: 'readonly',
        CustomEvent: 'readonly',
        navigator: 'readonly',
        setTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        alert: 'readonly',
        global: 'readonly',
        PerformanceObserver: 'readonly',
        performance: 'readonly',
        requestAnimationFrame: 'readonly',
      },
    },
    rules: {
      'no-constant-condition': 'warn',
      'no-undef': 'error',
      'no-unreachable': 'error',
      // Core ESLint does not mark JSX references as variable use without a React plugin.
      'no-unused-vars': 'off',
    },
  },
  {
    files: ['server.js', 'server/**/*.js', 'test/**/*.js', 'scripts/**/*.mjs', 'vite.config.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        Buffer: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        process: 'readonly',
        setTimeout: 'readonly',
        URL: 'readonly',
        test: 'readonly',
        assert: 'readonly',
      },
    },
    rules: {
      'no-constant-condition': 'warn',
      'no-undef': 'error',
      'no-unreachable': 'error',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
];
