(function () {
  function log(...args) {
    console.log("[camera]", ...args);
  }

  async function listVideoInputs() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(d => d.kind === "videoinput");
  }

  function isProbablyVirtualCamera(label = "") {
    const s = label.toLowerCase();
    // heurística simples: ajuste se você usa OBS/NVIDIA etc.
    return (
      s.includes("obs") ||
      s.includes("virtual") ||
      s.includes("nvidia") ||
      s.includes("broadcast") ||
      s.includes("manycam") ||
      s.includes("droidcam")
    );
  }

  async function openCamera(videoEl) {
    if (!videoEl) {
      throw new Error("Elemento <video> não encontrado no bloco data-camera.");
    }

    // tentativa 1: bem compatível
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });

      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    } catch (err1) {
      console.error("[camera] getUserMedia attempt #1 failed:", err1?.name, err1?.message, err1);

      // fallback: escolher device explicitamente (preferindo não-virtual)
      const cams = await listVideoInputs();
      log("videoinput devices:", cams.map(c => ({ label: c.label, id: c.deviceId })));

      const preferred =
        cams.find(c => c.label && !isProbablyVirtualCamera(c.label)) ||
        cams[0];

      if (!preferred) throw err1;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: { exact: preferred.deviceId },
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false
      });

      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    }
  }

  function stopCamera(stream) {
    if (stream) stream.getTracks().forEach(t => t.stop());
  }

  function captureToDataURL(videoEl, mime = "image/jpeg", quality = 0.85) {
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvas.toDataURL(mime, quality);
  }

// Substitua a versão atual por esta:
window.ensurePhoto = function ensurePhoto(e) {
  const submitter = e && e.submitter;
  if (submitter && submitter.name === 'skip') {
    return true; // não valida quando for "Pular"
  }
  const input = document.querySelector('[data-camera="1"] input[name="photo_data_url"]');
  if (!input || !input.value) {
    alert('Capture a foto antes de continuar. Ou clique em "Pular sem foto".');
    return false;
  }
  return true;
};

document.addEventListener("DOMContentLoaded", () => {
  window.initCameraBlocks?.();

  // Opcional: garante que não vai nenhuma foto residual ao pular
  document.getElementById('skip-btn')?.addEventListener('click', () => {
    const h = document.getElementById('photo_data_url');
    if (h) h.value = '';
  });
});


  window.initCameraBlocks = function initCameraBlocks() {
    document.querySelectorAll('[data-camera="1"]').forEach(block => {
      const video = block.querySelector("video");
      const imgPreview = block.querySelector("[data-preview]");
      const input = block.querySelector('input[type="hidden"][name="photo_data_url"]');

      const btnOpen = block.querySelector("[data-open]");
      const btnCapture = block.querySelector("[data-capture]");
      const btnClose = block.querySelector("[data-close]");
      const btnEnableOnCapture = block.querySelector("[data-enable-on-capture]");

      let stream = null;

      // estado inicial seguro
      if (btnCapture) btnCapture.disabled = true;
      if (btnClose) btnClose.disabled = true;
      if (btnEnableOnCapture) btnEnableOnCapture.disabled = true;

      btnOpen?.addEventListener("click", async () => {
        try {
          stopCamera(stream);
          stream = await openCamera(video);

          if (btnCapture) btnCapture.disabled = false;
          if (btnClose) btnClose.disabled = false;
        } catch (err) {
          console.error("[camera] open failed:", err?.name, err?.message, err);
          alert(`Câmera falhou: ${err?.name || "Erro"} - ${err?.message || String(err)}`);
        }
      });

      btnCapture?.addEventListener("click", () => {
        if (!stream || !video) return;
        const dataUrl = captureToDataURL(video);

        if (input) input.value = dataUrl;
        if (imgPreview) {
          imgPreview.src = dataUrl;
          imgPreview.style.display = "block";
        }
        if (btnEnableOnCapture) btnEnableOnCapture.disabled = false;
      });

      btnClose?.addEventListener("click", () => {
        stopCamera(stream);
        stream = null;

        if (video) {
          video.pause?.();
          video.srcObject = null;
        }

        if (btnCapture) btnCapture.disabled = true;
        if (btnClose) btnClose.disabled = true;
      });

      window.addEventListener("beforeunload", () => stopCamera(stream));
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    window.initCameraBlocks?.();
  });
})();
