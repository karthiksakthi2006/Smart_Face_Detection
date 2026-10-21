/**
 * Smart Face Detection and Recognition System
 * Live Webcam Recognition Engine
 * Real-time continuous detection, green/yellow bounding boxes, HUD metrics
 */

document.addEventListener('DOMContentLoaded', function () {
  const video = document.getElementById('recognizeVideo');
  const canvas = document.getElementById('recognizeOverlayCanvas');
  const ctx = canvas.getContext('2d');

  const startBtn = document.getElementById('startLiveCameraBtn');
  const stopBtn = document.getElementById('stopLiveCameraBtn');
  const mirrorToggle = document.getElementById('liveMirrorToggle');
  const soundToggle = document.getElementById('soundToggle');
  const cameraSelect = document.getElementById('cameraSelect');
  const thresholdSlider = document.getElementById('thresholdSlider');
  const thresholdVal = document.getElementById('thresholdVal');

  // HUD elements
  const activeFacesCountEl = document.getElementById('hudActiveFaces');
  const recognizedCountEl = document.getElementById('hudRecognizedCount');
  const fpsDisplayEl = document.getElementById('hudFps');
  const liveStatusBadge = document.getElementById('liveStatusBadge');
  const recentDetectionsFeed = document.getElementById('recentDetectionsFeed');
  const placeholder = document.getElementById('recognizePlaceholder');

  let stream = null;
  let isRunning = false;
  let isMirrored = true;
  let playAudio = true;
  let processingFrame = false;
  let lastFrameTime = performance.now();
  let frameCount = 0;
  let currentFps = 0;
  let fpsTimer = null;

  // Throttled audio chime tracking (UID -> last played timestamp)
  const soundCooldown = new Map();

  // Populate available video devices
  async function loadCameras() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === 'videoinput');
      
      if (cameraSelect) {
        cameraSelect.innerHTML = '';
        videoDevices.forEach((device, index) => {
          const opt = document.createElement('option');
          opt.value = device.deviceId;
          opt.text = device.label || `Camera ${index + 1}`;
          cameraSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Could not enumerate camera devices:', e);
    }
  }

  loadCameras();

  // Start Camera
  async function startLiveCamera() {
    try {
      if (stream) stopLiveCamera();

      liveStatusBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Initializing Camera...';

      const selectedDeviceId = cameraSelect && cameraSelect.value ? { exact: cameraSelect.value } : undefined;

      const constraints = {
        video: {
          deviceId: selectedDeviceId,
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        },
        audio: false
      };

      stream = await navigator.mediaDevices.getUserMedia(constraints);
      video.srcObject = stream;
      await video.play();

      placeholder.style.display = 'none';
      isRunning = true;
      startBtn.disabled = true;
      stopBtn.disabled = false;

      liveStatusBadge.innerHTML = '<span class="pulse-dot me-1"></span> Live Recognition Running';
      liveStatusBadge.className = 'badge-recognized';

      // Update available devices in case labels were restricted before permission
      loadCameras();

      // Start FPS counter loop
      fpsTimer = setInterval(() => {
        currentFps = frameCount;
        frameCount = 0;
        if (fpsDisplayEl) fpsDisplayEl.textContent = `${currentFps} FPS`;
      }, 1000);

      App.showToast('Webcam started. Continuous face detection active.', 'info');

      // Kick off continuous detection loop
      requestAnimationFrame(recognitionLoop);
    } catch (err) {
      console.error('Failed to start camera:', err);
      liveStatusBadge.innerHTML = '<i class="bi bi-x-circle text-danger me-1"></i> Camera Inactive';
      liveStatusBadge.className = 'badge-unknown';

      let msg = 'Could not access webcam. Please ensure permission is granted.';
      if (err.name === 'NotAllowedError') {
        msg = 'Camera permission denied. Please allow camera access in browser.';
      }
      App.showToast(msg, 'error', 'Camera Error');
    }
  }

  // Stop Camera
  function stopLiveCamera() {
    isRunning = false;
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    video.srcObject = null;
    placeholder.style.display = 'flex';

    if (fpsTimer) {
      clearInterval(fpsTimer);
      fpsTimer = null;
    }

    startBtn.disabled = false;
    stopBtn.disabled = true;

    liveStatusBadge.innerHTML = '<i class="bi bi-pause-circle me-1"></i> Camera Stopped';
    liveStatusBadge.className = 'hud-corner-badge hud-top-left';

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (activeFacesCountEl) activeFacesCountEl.textContent = '0 Faces';
    if (recognizedCountEl) recognizedCountEl.textContent = '0';
    if (fpsDisplayEl) fpsDisplayEl.textContent = '0 FPS';
  }

  startBtn.addEventListener('click', startLiveCamera);
  stopBtn.addEventListener('click', stopLiveCamera);

  if (mirrorToggle) {
    mirrorToggle.addEventListener('change', (e) => {
      isMirrored = e.target.checked;
      const wrapper = document.querySelector('.webcam-viewport-wrapper');
      if (isMirrored) {
        wrapper.classList.remove('unmirrored');
      } else {
        wrapper.classList.add('unmirrored');
      }
    });
  }

  if (soundToggle) {
    soundToggle.addEventListener('change', (e) => {
      playAudio = e.target.checked;
    });
  }

  if (thresholdSlider && thresholdVal) {
    thresholdSlider.addEventListener('input', (e) => {
      thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
    });
  }

  if (cameraSelect) {
    cameraSelect.addEventListener('change', () => {
      if (isRunning) {
        startLiveCamera();
      }
    });
  }

  // Real-time Recognition Loop
  async function recognitionLoop() {
    if (!isRunning) return;

    if (!processingFrame && video.readyState >= 2) {
      processingFrame = true;
      try {
        await processCurrentFrame();
        frameCount++;
      } catch (e) {
        console.error('Frame processing error:', e);
      } finally {
        processingFrame = false;
      }
    }

    // Schedule next frame
    if (isRunning) {
      // Small pause (e.g. 60-80ms) to ensure smooth 12-15 FPS without overloading network/CPU
      setTimeout(() => {
        requestAnimationFrame(recognitionLoop);
      }, 75);
    }
  }

  // Capture canvas image, send to backend API, and draw overlay results
  async function processCurrentFrame() {
    const videoW = video.videoWidth;
    const videoH = video.videoHeight;
    if (!videoW || !videoH) return;

    // Ensure overlay canvas dimensions match video display size
    const rect = video.getBoundingClientRect();
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width = rect.width;
      canvas.height = rect.height;
    }

    // Capture small/medium frame for fast server processing (max 640px wide for speed)
    const scaleFactor = Math.min(1.0, 640 / videoW);
    const sendW = Math.round(videoW * scaleFactor);
    const sendH = Math.round(videoH * scaleFactor);

    const offscreenCanvas = document.createElement('canvas');
    offscreenCanvas.width = sendW;
    offscreenCanvas.height = sendH;
    const offscreenCtx = offscreenCanvas.getContext('2d');
    offscreenCtx.drawImage(video, 0, 0, sendW, sendH);

    const frameDataUrl = offscreenCanvas.toDataURL('image/jpeg', 0.82);

    const currentThreshold = thresholdSlider ? parseFloat(thresholdSlider.value) : 0.38;

    const response = await fetch('/api/recognize_frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        frame: frameDataUrl,
        similarity_threshold: currentThreshold
      })
    });

    if (!response.ok) return;
    const result = await response.json();

    // Render bounding boxes and HUD
    renderOverlay(result, sendW, sendH);
  }

  // Draw Bounding Boxes and HUD Labels on Canvas
  function renderOverlay(data, frameW, frameH) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const faces = data.faces || [];
    const totalFaces = faces.length;
    const recognizedCount = data.recognized_count || 0;

    // Update HUD counters
    if (activeFacesCountEl) activeFacesCountEl.textContent = `${totalFaces} Face${totalFaces === 1 ? '' : 's'}`;
    if (recognizedCountEl) recognizedCountEl.textContent = `${recognizedCount}`;

    if (totalFaces === 0) return;

    const canvasW = canvas.width;
    const canvasH = canvas.height;

    // Scale factors from frame capture to display canvas
    const scaleX = canvasW / frameW;
    const scaleY = canvasH / frameH;

    const now = Date.now();

    faces.forEach((face) => {
      const isRecognized = face.status === 'Recognized';
      const box = face.box;

      // Scaled coordinates
      let sx = box.x * scaleX;
      let sy = box.y * scaleY;
      let sw = box.w * scaleX;
      let sh = box.h * scaleY;

      // Handle horizontal mirroring
      if (isMirrored) {
        sx = canvasW - (sx + sw);
      }

      // Box Styling
      // Recognized: GREEN (#10b981)
      // Unknown: YELLOW (#f59e0b)
      const themeColor = isRecognized ? '#10b981' : '#f59e0b';
      const glowColor = isRecognized ? 'rgba(16, 185, 129, 0.45)' : 'rgba(245, 158, 11, 0.45)';

      // 1. Draw glowing rectangular bounding box with rounded corners
      ctx.save();
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 12;
      ctx.strokeStyle = themeColor;
      ctx.lineWidth = 3;

      // Draw rounded rectangle
      drawRoundedRect(ctx, sx, sy, sw, sh, 8);
      ctx.stroke();

      // Draw futuristic corner brackets
      drawCornerBrackets(ctx, sx, sy, sw, sh, 14, themeColor);
      ctx.restore();

      // 2. Prepare Name & Status Label
      const displayName = isRecognized ? face.name : 'Unknown Person';
      const statusLabel = isRecognized ? 'Recognized' : 'Unknown';
      const confText = isRecognized ? `${Math.round(face.confidence * 100)}% match` : 'Unregistered';

      ctx.save();
      ctx.font = '600 13px Inter, sans-serif';
      const nameWidth = ctx.measureText(displayName).width;
      ctx.font = '500 11px Inter, sans-serif';
      const metaWidth = ctx.measureText(`${statusLabel} • ${confText}`).width;

      const pillWidth = Math.max(nameWidth, metaWidth) + 26;
      const pillHeight = 44;
      const pillX = sx;
      let pillY = sy - pillHeight - 8;

      // If box is too near top of video, place pill inside box top
      if (pillY < 10) {
        pillY = sy + 8;
      }

      // Draw pill background
      ctx.fillStyle = 'rgba(11, 17, 32, 0.88)';
      ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
      ctx.shadowBlur = 8;
      drawRoundedRect(ctx, pillX, pillY, pillWidth, pillHeight, 6);
      ctx.fill();

      // Draw accent left bar on pill
      ctx.fillStyle = themeColor;
      drawRoundedRect(ctx, pillX, pillY, 4, pillHeight, 2);
      ctx.fill();

      // Draw Name Text (White)
      ctx.fillStyle = '#ffffff';
      ctx.font = '600 13px Inter, sans-serif';
      ctx.fillText(displayName, pillX + 12, pillY + 18);

      // Draw Status indicator dot & label
      ctx.fillStyle = themeColor;
      ctx.beginPath();
      ctx.arc(pillX + 16, pillY + 31, 3.5, 0, 2 * Math.PI);
      ctx.fill();

      ctx.fillStyle = isRecognized ? '#34d399' : '#fbbf24';
      ctx.font = '500 11px Inter, sans-serif';
      ctx.fillText(`${statusLabel} (${confText})`, pillX + 24, pillY + 35);

      ctx.restore();

      // Trigger Audio Chime & Feed Item on new recognition
      if (isRecognized && face.uid) {
        const lastChime = soundCooldown.get(face.uid) || 0;
        if (now - lastChime > 8000) {
          soundCooldown.set(face.uid, now);
          if (playAudio) {
            App.playRecognitionSound();
          }
          addRecentDetectionCard(face);
        }
      }
    });
  }

  // Draw rounded rectangle helper
  function drawRoundedRect(c, x, y, w, h, r) {
    if (w < 2 * r) r = w / 2;
    if (h < 2 * r) r = h / 2;
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r);
    c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r);
    c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }

  // Draw futuristic corner brackets on face box
  function drawCornerBrackets(c, x, y, w, h, length, color) {
    c.strokeStyle = color;
    c.lineWidth = 3.5;
    c.beginPath();

    // Top-Left
    c.moveTo(x, y + length);
    c.lineTo(x, y);
    c.lineTo(x + length, y);

    // Top-Right
    c.moveTo(x + w - length, y);
    c.lineTo(x + w, y);
    c.lineTo(x + w, y + length);

    // Bottom-Left
    c.moveTo(x, y + h - length);
    c.lineTo(x, y + h);
    c.lineTo(x + length, y + h);

    // Bottom-Right
    c.moveTo(x + w - length, y + h);
    c.lineTo(x + w, y + h);
    c.lineTo(x + w, y + h - length);

    c.stroke();
  }

  // Add detection event to live sidebar feed
  function addRecentDetectionCard(face) {
    if (!recentDetectionsFeed) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
      <div class="d-flex align-items-center gap-2">
        <div class="stat-icon green" style="width: 32px; height: 32px; font-size: 1rem;">
          <i class="bi bi-person-check-fill"></i>
        </div>
        <div>
          <div class="fw-bold small text-white">${face.name}</div>
          <div class="text-muted" style="font-size: 0.75rem;">${timeStr}</div>
        </div>
      </div>
      <div class="badge-recognized" style="font-size: 0.72rem;">
        ${Math.round(face.confidence * 100)}%
      </div>
    `;

    recentDetectionsFeed.insertBefore(item, recentDetectionsFeed.firstChild);

    // Keep max 8 items in feed
    while (recentDetectionsFeed.children.length > 8) {
      recentDetectionsFeed.removeChild(recentDetectionsFeed.lastChild);
    }
  }
});
