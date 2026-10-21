/**
 * Smart Face Detection and Recognition System
 * Face Registration Logic (Webcam capture + Photo upload, validation & consent)
 */

document.addEventListener('DOMContentLoaded', function () {
  const video = document.getElementById('registerVideo');
  const overlayCanvas = document.getElementById('registerOverlayCanvas');
  const startCameraBtn = document.getElementById('startCameraBtn');
  const captureBtn = document.getElementById('captureFaceBtn');
  const switchCameraBtn = document.getElementById('switchCameraBtn');
  const mirrorToggle = document.getElementById('mirrorToggle');
  const nameInput = document.getElementById('personName');
  const notesInput = document.getElementById('personNotes');
  const consentCheck = document.getElementById('consentCheck');
  const webcamPlaceholder = document.getElementById('webcamPlaceholder');
  const statusBadge = document.getElementById('registerStatusBadge');
  const registerSpinner = document.getElementById('registerSpinner');

  // File upload alternative elements
  const fileInput = document.getElementById('photoUploadInput');
  const dropZone = document.getElementById('dropZone');
  const uploadPreview = document.getElementById('uploadPreview');
  const submitUploadBtn = document.getElementById('submitUploadBtn');

  // Success Modal elements
  const successModal = new bootstrap.Modal(document.getElementById('registerSuccessModal'));
  const successThumbnail = document.getElementById('successThumbnail');
  const successName = document.getElementById('successName');
  const successUid = document.getElementById('successUid');
  const successDate = document.getElementById('successDate');

  let stream = null;
  let currentFacingMode = 'user';
  let isMirrored = true;
  let uploadedBase64 = null;

  // Initialize Camera
  async function startCamera() {
    try {
      if (stream) {
        stopCamera();
      }

      statusBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Requesting Camera Access...';

      const constraints = {
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: currentFacingMode
        },
        audio: false
      };

      stream = await navigator.mediaDevices.getUserMedia(constraints);
      video.srcObject = stream;
      await video.play();

      webcamPlaceholder.style.display = 'none';
      captureBtn.disabled = false;
      startCameraBtn.innerHTML = '<i class="bi bi-camera-video-off"></i> Stop Camera';
      startCameraBtn.classList.remove('btn-modern-primary');
      startCameraBtn.classList.add('btn-modern-secondary');

      statusBadge.innerHTML = '<span class="pulse-dot me-1"></span> Camera Active (Ready to Capture)';
      statusBadge.className = 'badge-recognized';

      App.showToast('Webcam connected successfully.', 'info');
    } catch (err) {
      console.error('Error accessing camera:', err);
      statusBadge.innerHTML = '<i class="bi bi-x-circle text-danger me-1"></i> Camera Inactive';
      statusBadge.className = 'badge-unknown';

      let msg = 'Could not access webcam. Please check browser camera permissions.';
      if (err.name === 'NotAllowedError') {
        msg = 'Camera permission was denied. Please allow camera access in browser address bar.';
      } else if (err.name === 'NotFoundError') {
        msg = 'No webcam hardware detected. You can use the Photo Upload option below.';
      }
      App.showToast(msg, 'error', 'Webcam Permission Error');
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    video.srcObject = null;
    webcamPlaceholder.style.display = 'flex';
    captureBtn.disabled = true;
    startCameraBtn.innerHTML = '<i class="bi bi-camera-video"></i> Start Camera';
    startCameraBtn.classList.remove('btn-modern-secondary');
    startCameraBtn.classList.add('btn-modern-primary');

    statusBadge.innerHTML = '<i class="bi bi-pause-circle me-1"></i> Camera Inactive';
    statusBadge.className = 'hud-corner-badge hud-top-left';
  }

  startCameraBtn.addEventListener('click', () => {
    if (stream) {
      stopCamera();
    } else {
      startCamera();
    }
  });

  if (switchCameraBtn) {
    switchCameraBtn.addEventListener('click', () => {
      currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
      if (stream) {
        startCamera();
      }
    });
  }

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

  // Capture frame from webcam video stream
  function captureWebcamFrame() {
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');

    // If mirrored, flip the canvas horizontally
    if (isMirrored) {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.95);
  }

  // Handle Capture & Register
  captureBtn.addEventListener('click', async () => {
    const name = nameInput.value.trim();
    if (!name) {
      App.showToast('Please enter the person\'s name before capturing.', 'warning', 'Missing Name');
      nameInput.focus();
      return;
    }

    if (!consentCheck.checked) {
      App.showToast('Please confirm consent checkbox before registering facial data.', 'warning', 'Consent Required');
      consentCheck.focus();
      return;
    }

    if (!stream || video.readyState < 2) {
      App.showToast('Please start camera first and ensure video is active.', 'warning');
      return;
    }

    // Capture frame
    const imageData = captureWebcamFrame();
    await submitRegistration(name, imageData, notesInput.value.trim());
  });

  // Submit registration payload to backend
  async function submitRegistration(name, imageB64, notes = '') {
    captureBtn.disabled = true;
    registerSpinner.style.display = 'inline-block';
    statusBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing Face Detection...';

    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          image: imageB64,
          notes: notes
        })
      });

      const data = await response.json();

      if (data.success) {
        // Play recognition chime
        App.playRecognitionSound();
        App.showToast(data.message || 'Face Registered Successfully!', 'success', 'Registration Complete');

        // Populate success modal
        successThumbnail.src = data.person.thumbnail_path;
        successName.textContent = data.person.name;
        successUid.textContent = data.person.uid;
        successDate.textContent = App.formatDate(data.person.created_at);

        successModal.show();

        // Reset form inputs
        nameInput.value = '';
        notesInput.value = '';
        if (uploadPreview) uploadPreview.style.display = 'none';
        uploadedBase64 = null;
      } else {
        // Display specific error returned by backend
        // (e.g. "No face detected. Please try again.", "Multiple faces detected...")
        App.showToast(data.error, 'error', 'Registration Notice');
      }
    } catch (err) {
      console.error('Registration request error:', err);
      App.showToast('Network or server error during registration. Please try again.', 'error');
    } finally {
      captureBtn.disabled = false;
      registerSpinner.style.display = 'none';
      if (stream) {
        statusBadge.innerHTML = '<span class="pulse-dot me-1"></span> Camera Active (Ready to Capture)';
        statusBadge.className = 'badge-recognized';
      }
    }
  }

  // --- Photo Upload Support ---
  if (fileInput) {
    fileInput.addEventListener('change', function (e) {
      const file = e.target.files[0];
      if (file) {
        handleImageFile(file);
      }
    });
  }

  if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('border-primary');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('border-primary');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-primary');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleImageFile(e.dataTransfer.files[0]);
      }
    });
  }

  function handleImageFile(file) {
    if (!file.type.startsWith('image/')) {
      App.showToast('Please select a valid image file (JPEG, PNG).', 'warning');
      return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
      uploadedBase64 = e.target.result;
      if (uploadPreview) {
        uploadPreview.src = uploadedBase64;
        uploadPreview.style.display = 'block';
      }
      if (submitUploadBtn) submitUploadBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  }

  if (submitUploadBtn) {
    submitUploadBtn.addEventListener('click', async () => {
      const name = nameInput.value.trim();
      if (!name) {
        App.showToast('Please enter person\'s name.', 'warning');
        nameInput.focus();
        return;
      }
      if (!consentCheck.checked) {
        App.showToast('Please confirm consent checkbox before registering.', 'warning');
        return;
      }
      if (!uploadedBase64) {
        App.showToast('Please select or drop an image file first.', 'warning');
        return;
      }
      await submitRegistration(name, uploadedBase64, notesInput.value.trim());
    });
  }
});
