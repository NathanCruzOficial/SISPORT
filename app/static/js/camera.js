// =====================================================================
// camera.js — SISPORT V2
// Câmera abre automaticamente. Preview no mesmo elemento.
// Borda verde ao capturar. Fluxo simplificado.
// Face Cropper integrado como camada OPCIONAL (não altera nada se ausente).
// =====================================================================

(function () {

  function log(...args) { console.log("[camera]", ...args); }

  // ── Listagem e filtro de câmeras ──────────────────────────────────

  async function listVideoInputs() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(d => d.kind === "videoinput");
  }

  function isProbablyVirtualCamera(label = "") {
    const s = label.toLowerCase();
    return ["obs","virtual","nvidia","broadcast","manycam","droidcam"]
      .some(k => s.includes(k));
  }

  // ── Abrir câmera ─────────────────────────────────────────────────

  async function openCamera(videoEl) {
    if (!videoEl) throw new Error("Elemento <video> não encontrado.");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    } catch (err1) {
      log("Tentativa 1 falhou:", err1?.name, err1?.message);

      const cams = await listVideoInputs();
      log("Dispositivos:", cams.map(c => ({ label: c.label, id: c.deviceId })));

      const preferred = cams.find(c => c.label && !isProbablyVirtualCamera(c.label)) || cams[0];
      if (!preferred) throw err1;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: { exact: preferred.deviceId },
          width: { ideal: 640 }, height: { ideal: 480 }
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

  // ── Capturar frame do vídeo para o canvas ─────────────────────────

  function captureToCanvas(videoEl, canvasEl) {
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvasEl.toDataURL("image/jpeg", 0.85);
  }

  // ── Helpers de visibilidade (vence Bootstrap d-flex) ──────────────

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

  // ── Validação global de foto obrigatória ──────────────────────────

  window.ensurePhoto = function ensurePhoto(e) {
    const submitter = e && e.submitter;
    if (submitter && submitter.name === "skip") return true;

    const input = document.getElementById("photo_data_url");
    if (!input || !input.value) {
      alert('Capture a foto antes de continuar.\nOu clique em "Pular sem foto".');
      return false;
    }
    return true;
  };

  // ── Inicialização principal (wizard etapa 2) ──────────────────────

  document.addEventListener("DOMContentLoaded", () => {

    const block = document.querySelector('[data-camera="1"]');
    if (!block) return;

    if (block.offsetParent === null) {
      log("Bloco de câmera oculto — aguardando sisport:open-camera.");
      return;
    }

    initCamera();
  });

  // ── Função central de inicialização ───────────────────────────────

  function initCamera() {
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

    if (!video || !container) return;

    let stream = null;

    // ── Face Cropper: montar elementos dinâmicos se disponível ──────
    // Cria um canvas extra POR CIMA do vídeo para o preview do crop.
    // Se FaceCropper não existir, nada é criado e tudo funciona normal.

    let fcActive = false;
    let fcCanvas = null;
    let fcIndicator = null;

    const hasFaceCropper = typeof window.FaceCropper !== "undefined";

    if (hasFaceCropper) {
      log("FaceCropper disponível — montando overlay.");

      // Canvas do crop: absoluto, cobre o vídeo inteiro
      fcCanvas = document.createElement("canvas");
      fcCanvas.style.cssText =
        "position:absolute; top:0; left:0; width:100%; height:100%; " +
        "object-fit:cover; display:none; z-index:1; pointer-events:none;";
      container.appendChild(fcCanvas);

      // Indicador de status do rosto
      fcIndicator = document.createElement("div");
      fcIndicator.style.cssText =
        "display:none; position:absolute; bottom:8px; left:50%; " +
        "transform:translateX(-50%); z-index:3; padding:4px 14px; " +
        "border-radius:20px; font-size:0.75rem; font-weight:600; " +
        "color:#fff; backdrop-filter:blur(6px); pointer-events:none; " +
        "white-space:nowrap; transition:background-color 0.3s;";
      container.appendChild(fcIndicator);
    }

    function onFaceStatus(status) {
      if (!fcIndicator) return;
      fcIndicator.style.display = "block";
      switch (status) {
        case "found":
          fcIndicator.textContent = "✅ Rosto detectado";
          fcIndicator.style.backgroundColor = "rgba(25,135,84,0.85)";
          break;
        case "lost":
          fcIndicator.textContent = "⚠️ Reposicione o rosto";
          fcIndicator.style.backgroundColor = "rgba(255,28,7,0.85)";
          break;
        case "searching":
          fcIndicator.textContent = "🔍 Procurando rosto…";
          fcIndicator.style.backgroundColor = "rgba(108,117,125,0.85)";
          break;
      }
    }

    // ── Estados visuais ─────────────────────────────────────────────

    function setStateLive() {
      video.style.display = "block";
      canvas.style.display = "none";

      if (fcActive && fcCanvas) {
        // Face cropper ativo: mostra canvas do crop POR CIMA do vídeo
        fcCanvas.style.display = "block";
      }

      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      container.style.borderWidth = "";

      if (btnCapture) { btnCapture.style.display = "block"; btnCapture.disabled = false; }
      if (btnRetake)    btnRetake.style.display = "none";
      if (btnNext)      btnNext.disabled = true;
      if (hiddenInput)  hiddenInput.value = "";
    }

    function setStateCaptured(dataUrl) {
      video.style.display = "none";
      canvas.style.display = "block";

      // Esconde o overlay do face cropper
      if (fcCanvas) fcCanvas.style.display = "none";
      if (fcIndicator) fcIndicator.style.display = "none";

      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      container.style.borderWidth = "3px";

      if (btnCapture) btnCapture.style.display = "none";
      if (btnRetake)  btnRetake.style.display = "block";
      if (btnNext)    btnNext.disabled = false;
      if (hiddenInput) hiddenInput.value = dataUrl;
    }

    function setStateError() {
      hide(loading);
      showFlex(errorOverlay);
      if (btnCapture) btnCapture.disabled = true;
    }

    function setStateReady() {
      hide(loading);
      hide(errorOverlay);
      setStateLive();
    }

    // ── Abrir câmera ────────────────────────────────────────────────

    async function startCamera() {
      showFlex(loading);
      hide(errorOverlay);

      try {
        stream = await openCamera(video);
        log("Câmera aberta com sucesso.");

        // Tenta ativar face cropper (opcional, não bloqueia)
        if (hasFaceCropper && fcCanvas) {
          try {
            fcActive = await window.FaceCropper.start(video, fcCanvas, onFaceStatus);
            log(fcActive ? "FaceCropper ativo ✔" : "FaceCropper não iniciou — modo normal.");
          } catch (fcErr) {
            log("FaceCropper erro:", fcErr.message, "— modo normal.");
            fcActive = false;
          }
        }

        setStateReady();
      } catch (err) {
        console.error("[camera] Falha ao abrir:", err?.name, err?.message, err);
        setStateError();
      }
    }

    // ── Auto-abrir ──────────────────────────────────────────────────
    startCamera();

    // ── Botão TIRAR FOTO ────────────────────────────────────────────

    btnCapture?.addEventListener("click", () => {
      if (!stream || !video) return;

      let dataUrl = null;

      // Se face cropper está ativo, usa o crop recortado
      if (fcActive && window.FaceCropper) {
        dataUrl = window.FaceCropper.capture();
        if (dataUrl) {
          log("Foto via FaceCropper (crop 3:4).");
          // Desenha no canvas de exibição para o preview
          const img = new Image();
          img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            canvas.getContext("2d").drawImage(img, 0, 0);
            setStateCaptured(dataUrl);
          };
          img.src = dataUrl;
          return; // sai aqui — o setStateCaptured roda no onload
        }
      }

      // Fallback: frame inteiro (comportamento original)
      dataUrl = captureToCanvas(video, canvas);
      setStateCaptured(dataUrl);
      log("Foto capturada (frame inteiro).");
    });

    // ── Botão TIRAR OUTRA ───────────────────────────────────────────

    btnRetake?.addEventListener("click", () => {
      setStateLive();
      if (!stream || !video.srcObject) {
        startCamera();
      }
      log("Modo retake — câmera ao vivo.");
    });

    // ── Botão PULAR ─────────────────────────────────────────────────

    btnSkip?.addEventListener("click", () => {
      if (hiddenInput) hiddenInput.value = "";
    });

    // ── Cleanup ─────────────────────────────────────────────────────

    window.addEventListener("beforeunload", () => {
      if (window.FaceCropper) window.FaceCropper.stop();
      stopCamera(stream);
    });
  }

  // ── Abertura sob demanda (tela de edição) ───────────────────────

  window.addEventListener("sisport:open-camera", () => {
    const video = document.getElementById("cam-video");
    if (!video) return;

    if (video.srcObject) {
      log("Câmera já ativa, ignorando.");
      const loading = document.getElementById("cam-loading");
      hide(loading);
      return;
    }

    initCamera();
  });

})();
