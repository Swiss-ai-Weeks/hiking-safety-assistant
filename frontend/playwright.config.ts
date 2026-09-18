import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end over the built app: `pnpm e2e` at the repo root builds, then runs these.
 *
 * By default the backend is started on its own port to serve the build, with the model switched off
 * explicitly (a deployed `backend/.env` turns it on). The specs tagged @stubbed answer the app's API
 * calls in the browser from the test fixtures (`e2e/api.ts`), so every outcome state is reachable and
 * nothing leaves the machine. `E2E_BASE_URL` points the suite at a running app instead, where the
 * @stubbed specs are skipped.
 */
const PORT = 8210
const external = process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  fullyParallel: true,
  reporter: [['list']],
  use: {
    ...devices['iPhone 13'],
    // Chromium, not WebKit: the device only sets the viewport, touch and user agent.
    browserName: 'chromium',
    baseURL: external ?? `http://127.0.0.1:${PORT}`,
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  grepInvert: external ? /@stubbed/ : undefined,
  webServer: external
    ? undefined
    : {
        command: `uv run --directory ../backend uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
        url: `http://127.0.0.1:${PORT}/api/health`,
        reuseExistingServer: false,
        timeout: 60_000,
        env: {
          NARRATION_ENABLED: 'false',
          WARMUP_ENABLED: 'false',
          MCP_HTTP: 'false',
          FRONTEND_DIST: '../frontend/dist',
          CACHE_DIR: '.e2e-cache',
        },
      },
})
