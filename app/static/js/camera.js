(function () {
  async function openCamera(videoEl) {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false
    });
    videoEl.srcObject = stream;
    await videoEl.play();
    return stream;
  }

  function stopCamera(stream) {
    if (stream) stream.getTracks().forEach(t => t.stop());
  }

  function captureToDataURL(videoEl, mime = "image/jpeg", quality = 0.85) {
    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvas.toDataURL(mime, quality);
  }

  // Inicializa qualquer bloco com data-camera="1"
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

      btnOpen?.addEventListener("click", async () => {
        try {
          stream = await openCamera(video);
          video.style.display = "block";
          btnCapture.disabled = false;
          btnClose.disabled = false;
        } catch (e) {
          alert("Não foi possível acessar a câmera. Verifique permissões do navegador.");
        }
      });

      btnCapture?.addEventListener("click", () => {
        if (!stream) return;
        const dataUrl = captureToDataURL(video);
        input.value = dataUrl;
        if (imgPreview) {
          imgPreview.src = dataUrl;
          imgPreview.style.display = "block";
        }
        if (btnEnableOnCapture) btnEnableOnCapture.disabled = false;
      });

      btnClose?.addEventListener("click", () => {
        stopCamera(stream);
        stream = null;
        video.srcObject = null;
        video.style.display = "none";
        btnCapture.disabled = true;
        btnClose.disabled = true;
      });

      window.addEventListener("beforeunload", () => stopCamera(stream));
    });
  };
})();
