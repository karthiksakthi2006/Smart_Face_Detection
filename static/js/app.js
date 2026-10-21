/**
 * Smart Face Detection and Recognition System
 * Shared Utilities, Toast Notifications, and Audio Feedback
 */

const App = (function () {
  // Web Audio Context for synthesized feedback sounds
  let audioCtx = null;

  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtx = new AudioContext();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return audioCtx;
  }

  /**
   * Plays a pleasant chime sound when a person is recognized
   */
  function playRecognitionSound() {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      // Harmonic pleasant chord (E5 -> B5)
      osc.frequency.setValueAtTime(659.25, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(987.77, ctx.currentTime + 0.15);

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      console.warn('Audio playback not permitted yet:', e);
    }
  }

  /**
   * Modern Toast Notification System
   */
  function showToast(message, type = 'info', title = null) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container-custom';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-custom ${type}`;

    let icon = 'bi-info-circle';
    if (type === 'success') icon = 'bi-check-circle-fill text-success';
    else if (type === 'error') icon = 'bi-exclamation-triangle-fill text-danger';
    else if (type === 'warning') icon = 'bi-exclamation-circle-fill text-warning';

    toast.innerHTML = `
      <i class="bi ${icon} fs-5 mt-1"></i>
      <div style="flex: 1;">
        ${title ? `<div class="fw-bold mb-1">${title}</div>` : ''}
        <div class="small">${message}</div>
      </div>
      <button type="button" class="btn-close btn-close-white btn-sm" aria-label="Close" style="font-size: 0.65rem;"></button>
    `;

    const closeBtn = toast.querySelector('.btn-close');
    closeBtn.addEventListener('click', () => {
      toast.remove();
    });

    container.appendChild(toast);

    // Auto dismiss after 4.5 seconds
    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
      }
    }, 4500);
  }

  /**
   * Format ISO date string into readable format
   */
  function formatDate(isoString) {
    if (!isoString) return 'Never';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  }

  return {
    showToast,
    playRecognitionSound,
    formatDate,
    getAudioContext
  };
})();
