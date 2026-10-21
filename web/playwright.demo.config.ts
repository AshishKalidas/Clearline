import { defineConfig } from '@playwright/test';

const remote = process.env.CLEARLINE_DEMO_URL;

export default defineConfig({
  testDir: './demo-e2e',
  testIgnore: '**/._*',
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: remote ?? 'http://127.0.0.1:4173',
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
  },
  webServer: remote
    ? undefined
    : {
        command:
          'npm run build:demo && npm exec vite preview -- --host 127.0.0.1 --port 4173 --strictPort',
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: false,
      },
});
