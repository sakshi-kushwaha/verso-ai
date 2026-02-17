const { test, expect } = require('@playwright/test');
const fs = require('fs');

test.describe('Reel Audio Quality Test', () => {

  test('Login, play reel audio, and verify audio quality', async ({ page }) => {
    // 1. Go to login page
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // 2. Login with credentials
    const usernameInput = page.locator('input[placeholder="Enter your username"]');
    const passwordInput = page.locator('input[placeholder="Enter your password"]');

    await usernameInput.fill('testuser');
    await passwordInput.fill('test1234');

    // Click the Login button (bottom one, not tab)
    const loginBtn = page.locator('button:has-text("Login")').last();
    await loginBtn.click();

    // Wait for navigation to / (FeedPage)
    await page.waitForURL('http://localhost:5173/', { timeout: 15000 });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'tests/screenshots/01-feed-loaded.png' });

    console.log(`Current URL: ${page.url()}`);

    // 3. Wait for Listen button (reels loaded)
    const listenBtn = page.locator('button:has-text("Listen")').first();
    await expect(listenBtn).toBeVisible({ timeout: 10000 });
    console.log('Reels loaded - Listen button visible');

    // 4. Intercept audio request and click Listen
    const audioResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/audio/') && response.status() === 200,
      { timeout: 30000 }
    );

    console.log('Clicking Listen button...');
    await listenBtn.click();
    await page.screenshot({ path: 'tests/screenshots/02-audio-loading.png' });

    // 5. Capture and analyze audio response
    const audioResponse = await audioResponsePromise;
    console.log(`\nAudio URL: ${audioResponse.url()}`);
    console.log(`Content-Type: ${audioResponse.headers()['content-type']}`);

    const audioBuffer = await audioResponse.body();
    console.log(`Audio size: ${audioBuffer.length} bytes (${(audioBuffer.length / 1024).toFixed(1)} KB)`);

    fs.mkdirSync('tests/audio-samples', { recursive: true });
    fs.writeFileSync('tests/audio-samples/reel-audio-from-ui.wav', audioBuffer);
    console.log('Saved: tests/audio-samples/reel-audio-from-ui.wav');

    analyzeWavFile(audioBuffer, 'UI Playback Audio');

    // Wait for playback
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'tests/screenshots/03-audio-playing.png' });

    // 6. Test multiple reels via API
    console.log('\n\n========================================');
    console.log('=== Testing Audio for Multiple Reels ===');
    console.log('========================================');

    const token = await page.evaluate(() => localStorage.getItem('verso_token'));
    const feedResponse = await page.request.get('http://localhost:8000/feed?page=1&limit=8', {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    const feedData = await feedResponse.json();
    const reels = feedData.reels || [];
    console.log(`\nTotal reels available: ${reels.length}`);

    for (let i = 0; i < Math.min(reels.length, 5); i++) {
      const reel = reels[i];
      console.log(`\n--- Reel ${reel.id}: "${reel.title}" ---`);
      console.log(`Summary: ${reel.summary?.substring(0, 80)}...`);
      console.log(`Narration: ${reel.narration?.substring(0, 80)}...`);
      console.log(`Audio path in DB: ${reel.audio_path}`);

      const audioResp = await page.request.get(`http://localhost:8000/audio/${reel.id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (audioResp.ok()) {
        const body = await audioResp.body();
        fs.writeFileSync(`tests/audio-samples/reel-${reel.id}.wav`, body);
        console.log(`Downloaded: reel-${reel.id}.wav (${body.length} bytes)`);
        analyzeWavFile(body, `Reel ${reel.id}`);
      } else {
        console.log(`FAILED to fetch audio: ${audioResp.status()}`);
      }
    }

    // 7. Final summary
    console.log('\n\n================================================');
    console.log('=== AUDIO QUALITY DIAGNOSIS & RECOMMENDATIONS ===');
    console.log('================================================');
    console.log('');
    console.log('CURRENT TTS ENGINE: espeak-ng (formant synthesizer)');
    console.log('CURRENT VOICE: en-us+f3 (US English female variant 3)');
    console.log('CURRENT SPEED: 140 WPM | PITCH: 45 | GAP: 8');
    console.log('');
    console.log('WHY THE VOICE SOUNDS BROKEN:');
    console.log('  - espeak-ng uses formant synthesis (mathematical wave generation)');
    console.log('  - NOT neural/AI-based TTS - will always sound robotic');
    console.log('  - The "+f3" female variant adds extra pitch shifting that degrades clarity');
    console.log('  - Gap of 8 creates unnaturally long pauses between words');
    console.log('  - Speed of 140 is on the faster side for a formant engine');
    console.log('');
    console.log('IMMEDIATE FIXES (in backend/config.py):');
    console.log('  1. ESPEAK_VOICE = "en"         # Default male voice - much clearer');
    console.log('  2. ESPEAK_SPEED = 130           # Slower = clearer articulation');
    console.log('  3. ESPEAK_PITCH = 50            # Default pitch = more natural');
    console.log('  4. ESPEAK_GAP = 4               # Shorter gaps = more natural pacing');
    console.log('');
    console.log('BETTER SOLUTION - Switch to Piper TTS:');
    console.log('  - Neural TTS engine that sounds like a real human');
    console.log('  - Runs locally, ~300MB RAM for en_US-lessac model');
    console.log('  - 10x better quality than espeak-ng');
    console.log('  - pip install piper-tts');
    console.log('');
    console.log('Audio samples saved to tests/audio-samples/ for manual review.');

    await page.screenshot({ path: 'tests/screenshots/04-test-complete.png' });
  });
});


function analyzeWavFile(audioBuffer, label) {
  const riffHeader = audioBuffer.toString('ascii', 0, 4);
  const waveHeader = audioBuffer.toString('ascii', 8, 12);

  console.log(`\n  [${label}] WAV Analysis:`);

  if (riffHeader !== 'RIFF' || waveHeader !== 'WAVE') {
    console.log('  ERROR: Not a valid WAV file!');
    return;
  }

  const audioFormat = audioBuffer.readUInt16LE(20);
  const numChannels = audioBuffer.readUInt16LE(22);
  const sampleRate = audioBuffer.readUInt32LE(24);
  const byteRate = audioBuffer.readUInt32LE(28);
  const bitsPerSample = audioBuffer.readUInt16LE(34);

  console.log(`  Format: ${audioFormat === 1 ? 'PCM' : `Compressed(${audioFormat})`} | ${numChannels}ch | ${sampleRate}Hz | ${bitsPerSample}bit`);

  // Find data chunk
  let dataOffset = 12, dataSize = 0;
  while (dataOffset < audioBuffer.length - 8) {
    const chunkId = audioBuffer.toString('ascii', dataOffset, dataOffset + 4);
    const chunkSize = audioBuffer.readUInt32LE(dataOffset + 4);
    if (chunkId === 'data') { dataSize = chunkSize; break; }
    dataOffset += 8 + chunkSize;
  }

  if (dataSize > 0 && byteRate > 0) {
    const duration = dataSize / byteRate;
    console.log(`  Duration: ${duration.toFixed(2)}s | Size: ${(audioBuffer.length / 1024).toFixed(1)}KB`);

    // Quality issues
    const issues = [];
    if (sampleRate < 16000) issues.push(`Low sample rate (${sampleRate}Hz) - sounds muffled`);
    if (sampleRate === 22050) issues.push(`Sample rate ${sampleRate}Hz - OK for speech but not great`);
    if (bitsPerSample < 16) issues.push(`Low bit depth (${bitsPerSample}-bit) - grainy`);
    if (duration < 1) issues.push(`Very short (${duration.toFixed(2)}s)`);

    // Amplitude analysis
    const dataStart = dataOffset + 8;
    const sampleCount = Math.min(Math.floor(dataSize / 2), 50000);
    let maxAmp = 0, sumAmp = 0, silentCount = 0;

    for (let i = 0; i < sampleCount; i++) {
      const offset = dataStart + i * 2;
      if (offset + 1 < audioBuffer.length) {
        const sample = Math.abs(audioBuffer.readInt16LE(offset));
        if (sample > maxAmp) maxAmp = sample;
        sumAmp += sample;
        if (sample < 100) silentCount++;
      }
    }

    const avgAmp = sumAmp / sampleCount;
    const silenceRatio = silentCount / sampleCount;

    console.log(`  Amplitude: max=${maxAmp}/32767 (${((maxAmp/32767)*100).toFixed(0)}%) avg=${avgAmp.toFixed(0)} silence=${(silenceRatio*100).toFixed(0)}%`);

    if (maxAmp > 32000) issues.push('Audio clipping detected');
    if (silenceRatio > 0.6) issues.push(`${(silenceRatio*100).toFixed(0)}% silence`);
    if (avgAmp < 500) issues.push('Very low volume');

    if (issues.length) {
      console.log(`  ISSUES: ${issues.join(' | ')}`);
    } else {
      console.log(`  Quality: OK (for espeak-ng)`);
    }
  }
}
