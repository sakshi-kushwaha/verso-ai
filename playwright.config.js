const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: false,
    viewport: { width: 1280, height: 720 },
  },
});
