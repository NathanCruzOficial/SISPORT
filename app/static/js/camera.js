// =====================================================================
// camera.js — SISPORT V2
// Câmera com detecção de rosto obrigatória para liberar a captura.
// Reconexão contínua a cada 2s enquanto não houver stream.
// Erro definitivo somente quando NÃO existir câmera (device) no sistema.
// =====================================================================

(function () {
  "use strict";

  function log(...args) { console.log("[camera]", ...args); }

  const RECONNECT_MS = 2000;          // intervalo entre tentativas de reconexão
  const SKIP_TIMEOUT_MS = 20000;      // após isso, libera "continuar sem foto"

  // ── Dispositivos ──────────────────────────────────────────────────
  async function listVideoInputs() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter((d) => d.kind === "videoinput");
    } catch {
      return [];
    }
  }

  function isProbablyVirtualCamera(label = "") {
    const s = label.toLowerCase();
    return ["obs", "virtual", "nvidia", "broadcast", "manycam", "droidcam"]
      .some((k) => s.includes(k));
  }

  async function openCamera(videoEl) {
    if (!videoEl) throw new Error("Elemento <video> não encontrado.");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    } catch (err1) {
      log("Tentativa padrão falhou:", err1?.name, err1?.message);

      const cams = await listVideoInputs();
      const preferred =
        cams.find((c) => c.label && !isProbablyVirtualCamera(c.label)) || cams[0];
      if (!preferred) throw err1;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: { exact: preferred.deviceId },
          width: { ideal: 1280 },
          height: { ideal: 960 },
        },
        audio: false,
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    }
  }

  function stopStream(stream) {
    if (stream) stream.getTracks().forEach((t) => t.stop());
  }

  function captureToCanvas(videoEl, canvasEl) {
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvasEl.toDataURL("image/jpeg", 0.85);
  }

  function hide(el) {
    if (!el) return;
    el.classList.add("d-none");
    el.classList.remove("d-flex");
  }
  function showFlex(el) {
    if (!el) return;
    el.classList.add("d-flex");
    el.classList.remove("d-none");
  }

  // ── Controlador ───────────────────────────────────────────────────
  let active = null;

  function initCamera() {
    if (active) return; // já inicializado

    const video        = document.getElementById("cam-video");
    const canvas       = document.getElementById("cam-canvas");
    const container    = document.getElementById("camera-container");
    const loading      = document.getElementById("cam-loading");
    const errorOverlay = document.getElementById("cam-error");
    const hiddenInput  = document.getElementById("photo_data_url");
    const btnCapture   = document.getElementById("btn-capture");
    const btnRetake    = document.getElementById("btn-retake");
    const btnNext      = document.getElementById("btn-next");
    const btnSkip      = document.getElementById("skip-btn");
    const faceStatus   = document.getElementById("face-status");
    const permission   = document.getElementById("cam-permission");

    if (!video || !container) return;

    const ctrl = {
      video, canvas, container, loading, errorOverlay, hiddenInput,
      btnCapture, btnRetake, btnNext, btnSkip, faceStatus, permission,
      stream: null,
      faceCropperActive: false,
      faceDetected: false,
      retryTimer: null,
      skipTimer: null,
      destroyed: false,
      fcCanvas: null,
    };

    active = ctrl;

    const hasFaceCropper = typeof window.FaceCropper !== "undefined";

    if (hasFaceCropper) {
      ctrl.fcCanvas = document.createElement("canvas");
      ctrl.fcCanvas.style.cssText =
        "position:absolute; top:0; left:0; width:100%; height:100%; " +
        "object-fit:cover; display:none; z-index:1; pointer-events:none;";
      container.appendChild(ctrl.fcCanvas);
    }

    function setFaceStatus(text, kind) {
      if (!faceStatus) return;
      faceStatus.textContent = text;
      faceStatus.className = "muted mb-2 face-status" + (kind ? " " + kind : "");
    }

    function onFaceStatus(status) {
      if (ctrl.destroyed) return;
      ctrl.faceDetected = status === "found";
      if (status === "found") {
        setFaceStatus("Rosto detectado — pode tirar a foto.", "ok");
      } else if (status === "searching") {
        setFaceStatus("Centralize o rosto no enquadramento.");
      } else {
        setFaceStatus("Reposicione o rosto para continuar.");
      }
      updateCaptureButton();
    }

    function updateCaptureButton() {
      if (btnCapture) {
        const ready = !!ctrl.stream && ctrl.faceDetected && !video.paused;
        btnCapture.disabled = !ready;
      }
    }

    function setStateLive() {
      video.style.display = "block";
      canvas.style.display = "none";
      if (ctrl.fcCanvas && ctrl.faceCropperActive) ctrl.fcCanvas.style.display = "block";
      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      if (btnCapture) { btnCapture.style.display = "block"; btnCapture.disabled = true; }
      if (btnRetake) btnRetake.style.display = "none";
      if (btnNext) btnNext.disabled = true;
      if (hiddenInput) hiddenInput.value = "";
    }

    function setStateCaptured(dataUrl) {
      video.style.display = "none";
      canvas.style.display = "block";
      if (ctrl.fcCanvas) ctrl.fcCanvas.style.display = "none";
      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      if (btnCapture) btnCapture.style.display = "none";
      if (btnRetake) btnRetake.style.display = "block";
      if (btnNext) btnNext.disabled = false;
      if (hiddenInput) hiddenInput.value = dataUrl;
      setFaceStatus("Foto capturada.", "ok");
      window.dispatchEvent(new CustomEvent("sisport:photo-captured"));
    }

    function setStateNoCamera() {
      hide(loading);
      showFlex(errorOverlay);
      if (btnCapture) { btnCapture.style.display = "block"; btnCapture.disabled = true; }
      setFaceStatus("");
      enableSkip();
      window.dispatchEvent(new CustomEvent("sisport:camera-error"));
    }

    function setStateRetrying() {
      hide(errorOverlay);
      showFlex(loading);
      const span = loading && loading.querySelector("span");
      if (span) span.textContent = "Aguardando câmera...";
    }

    function setStateReady() {
      hide(loading);
      hide(errorOverlay);
      setStateLive();
      updateCaptureButton();
    }

    function enableSkip() {
      if (btnSkip) btnSkip.disabled = false;
    }

    function scheduleSkipTimeout() {
      if (ctrl.skipTimer) return;
      ctrl.skipTimer = setTimeout(() => {
        ctrl.skipTimer = null;
        if (ctrl.destroyed || ctrl.stream) return;
        enableSkip();
        setFaceStatus("A câmera está demorando. Você pode continuar sem foto.");
      }, SKIP_TIMEOUT_MS);
    }

    function scheduleRetry() {
      if (ctrl.destroyed) return;
      if (ctrl.retryTimer) clearTimeout(ctrl.retryTimer);
      ctrl.retryTimer = setTimeout(() => {
        ctrl.retryTimer = null;
        startCamera();
      }, RECONNECT_MS);
    }

    async function startCamera() {
      if (ctrl.destroyed) return;

      const devices = await listVideoInputs();
      if (devices.length === 0) {
        // Não há câmera conectada → erro definitivo
        setStateNoCamera();
        return;
      }

      try {
        setStateRetrying();
        ctrl.stream = await openCamera(video);
        if (ctrl.destroyed) { stopStream(ctrl.stream); ctrl.stream = null; return; }
        log("Câmera aberta.");

        if (hasFaceCropper && ctrl.fcCanvas) {
          try {
            ctrl.faceCropperActive = await window.FaceCropper.start(
              video, ctrl.fcCanvas, onFaceStatus
            );
            log(ctrl.faceCropperActive ? "FaceCropper ativo." : "FaceCropper indisponível.");
          } catch (e) {
            ctrl.faceCropperActive = false;
            log("FaceCropper falhou:", e?.message);
          }
        }

        if (!ctrl.faceCropperActive) {
          setFaceStatus("Não foi possível ativar a detecção de rosto.");
          enableSkip();
        }

        setStateReady();
      } catch (err) {
        log("Falha ao abrir câmera:", err?.name, err?.message);
        if (ctrl.destroyed) return;
        scheduleRetry();
        scheduleSkipTimeout();
      }
    }

    // ── Botão TIRAR FOTO (só com rosto detectado) ───────────────────
    btnCapture?.addEventListener("click", () => {
      if (!ctrl.stream || !video || !ctrl.faceDetected) return;

      let dataUrl = null;

      if (ctrl.faceCropperActive && window.FaceCropper) {
        dataUrl = window.FaceCropper.capture();
        if (dataUrl) {
          log("Foto via FaceCropper (crop).");
          const img = new Image();
          img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            canvas.getContext("2d").drawImage(img, 0, 0);
            setStateCaptured(dataUrl);
          };
          img.src = dataUrl;
          return;
        }
      }

      dataUrl = captureToCanvas(video, canvas);
      setStateCaptured(dataUrl);
      log("Foto capturada (frame inteiro).");
    });

    // ── Botão TIRAR OUTRA ───────────────────────────────────────────
    btnRetake?.addEventListener("click", () => {
      ctrl.faceDetected = false;
      setStateLive();
      updateCaptureButton();

      if (!ctrl.stream || !video.srcObject) {
        startCamera();
      }
      window.dispatchEvent(new CustomEvent("sisport:photo-retake"));
    });

    // ── Permissão (janelinha amigável) ──────────────────────────────
    // ── Persistência da permissão (caixinha customizada) ──────────
    const CAM_PERMISSION_KEY = "sisport_camera_permission";

    function hasStoredPermission() {
      try { return localStorage.getItem(CAM_PERMISSION_KEY) === "allowed"; } catch { return false; }
    }

    function storePermission() {
      try { localStorage.setItem(CAM_PERMISSION_KEY, "allowed"); } catch {}
    }

    const allowBtn = permission && permission.querySelector("[data-action='allow']");
    if (allowBtn) {
      allowBtn.addEventListener("click", () => {
        storePermission();
        hide(permission);
        startCamera();
      });
    }

    window.addEventListener("beforeunload", () => destroyCamera());

    // ── Início ──────────────────────────────────────────────────────
    if (permission) {
      if (hasStoredPermission()) {
        hide(permission);
        startCamera();
      } else {
        showFlex(permission); // primeira vez apenas
      }
    } else {
      startCamera();
    }
  }

  function destroyCamera() {
    const ctrl = active;
    if (!ctrl) return;
    ctrl.destroyed = true;
    if (ctrl.retryTimer) clearTimeout(ctrl.retryTimer);
    if (ctrl.skipTimer) clearTimeout(ctrl.skipTimer);
    if (window.FaceCropper && ctrl.faceCropperActive) {
      try { window.FaceCropper.stop(); } catch (e) {}
    }
    stopStream(ctrl.stream);
    ctrl.stream = null;
    active = null;
  }

  // ── Inicialização automática (wizard) ─────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    const block = document.querySelector('[data-camera="1"]');
    if (!block) return;
    if (block.offsetParent === null) return; // oculto (edição aguarda evento)
    initCamera();
  });

  // ── Abertura sob demanda (edição) ─────────────────────────────────
  window.addEventListener("sisport:open-camera", () => {
    const video = document.getElementById("cam-video");
    if (!video) return;
    if (video.srcObject) {
      hide(document.getElementById("cam-loading"));
      return;
    }
    initCamera();
  });

  window.SisportCamera = { init: initCamera, destroy: destroyCamera };
})();
