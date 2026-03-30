// =====================================================================
// camera.js
// Módulo de Captura de Foto via Webcam — Gerencia o acesso à câmera
// do dispositivo, exibição do stream de vídeo, captura de snapshot
// em Data URL (base64) e validação de foto obrigatória nos formulários
// de cadastro/checkin de visitantes.
//
// Estrutura esperada no HTML (bloco de câmera):
//   <div data-camera="1">
//     <video></video>
//     <img data-preview />
//     <input type="hidden" name="photo_data_url" />
//     <button data-open>Abrir</button>
//     <button data-capture>Capturar</button>
//     <button data-close>Fechar</button>
//     <button data-enable-on-capture>Confirmar</button>
//   </div>
// =====================================================================

(function () {

  // ───────────────────────────────────────────────────────────────────
  // Utilitário — Log com prefixo "[camera]"
  // ───────────────────────────────────────────────────────────────────

  /**
   * Loga mensagens no console com o prefixo "[camera]" para facilitar
   * a depuração de problemas relacionados à webcam.
   *
   * @param {...any} args - Argumentos a serem logados.
   */
  function log(...args) {
    console.log("[camera]", ...args);
  }


  // ───────────────────────────────────────────────────────────────────
  // Utilitário — Listagem de Dispositivos de Vídeo
  // ───────────────────────────────────────────────────────────────────

  /**
   * Enumera todos os dispositivos de mídia disponíveis e retorna
   * apenas os que são entradas de vídeo (webcams).
   *
   * @returns {Promise<MediaDeviceInfo[]>} Lista de dispositivos de vídeo.
   */
  async function listVideoInputs() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(d => d.kind === "videoinput");
  }


  // ───────────────────────────────────────────────────────────────────
  // Utilitário — Detecção de Câmera Virtual
  // ───────────────────────────────────────────────────────────────────

  /**
   * Heurística simples para identificar câmeras virtuais (OBS, ManyCam,
   * DroidCam, NVIDIA Broadcast, etc.) pelo label do dispositivo.
   * Usada no fallback para priorizar câmeras físicas reais.
   *
   * @param {string} label - Label do dispositivo de vídeo.
   * @returns {boolean} True se o label indica câmera virtual.
   */
  function isProbablyVirtualCamera(label = "") {
    const s = label.toLowerCase();
    return (
      s.includes("obs") ||
      s.includes("virtual") ||
      s.includes("nvidia") ||
      s.includes("broadcast") ||
      s.includes("manycam") ||
      s.includes("droidcam")
    );
  }


  // ───────────────────────────────────────────────────────────────────
  // Função Principal — Abertura da Câmera
  // ───────────────────────────────────────────────────────────────────

  /**
   * Abre o stream de vídeo da webcam e o associa ao elemento <video>.
   *
   * Estratégia em duas tentativas:
   * 1. getUserMedia genérico com resolução ideal 640×480.
   * 2. Fallback: enumera dispositivos, prioriza câmera física (não-virtual)
   *    e solicita acesso com deviceId explícito.
   *
   * @param {HTMLVideoElement} videoEl - Elemento <video> destino do stream.
   * @returns {Promise<MediaStream>} Stream de vídeo ativo.
   * @throws {Error} Se nenhuma câmera estiver disponível ou o acesso for negado.
   */
  async function openCamera(videoEl) {
    if (!videoEl) {
      throw new Error("Elemento <video> não encontrado no bloco data-camera.");
    }

    // ── Tentativa 1: Configuração genérica (mais compatível) ────────
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

      // ── Tentativa 2: Fallback com seleção explícita de device ─────
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


  // ───────────────────────────────────────────────────────────────────
  // Função — Encerramento da Câmera
  // ───────────────────────────────────────────────────────────────────

  /**
   * Para todas as tracks de um MediaStream, liberando a câmera.
   *
   * @param {MediaStream|null} stream - Stream a ser encerrado.
   */
  function stopCamera(stream) {
    if (stream) stream.getTracks().forEach(t => t.stop());
  }


  // ───────────────────────────────────────────────────────────────────
  // Função — Captura de Snapshot para Data URL
  // ───────────────────────────────────────────────────────────────────

  /**
   * Captura o frame atual do elemento <video> e o converte em uma
   * string Data URL (base64) usando um <canvas> temporário.
   *
   * @param {HTMLVideoElement} videoEl - Elemento <video> com stream ativo.
   * @param {string}           mime    - Tipo MIME da imagem (padrão: 'image/jpeg').
   * @param {number}           quality - Qualidade da compressão JPEG (0–1, padrão: 0.85).
   * @returns {string} Data URL da imagem capturada.
   */
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


  // ───────────────────────────────────────────────────────────────────
  // Função Global — Validação de Foto Obrigatória no Formulário
  // ───────────────────────────────────────────────────────────────────

  /**
   * Valida se a foto foi capturada antes do envio do formulário.
   * Permite bypass quando o botão de submit é o "Pular" (name='skip').
   * Deve ser chamada no onsubmit do <form>.
   *
   * Uso no HTML:
   *   <form onsubmit="return ensurePhoto(event)">
   *
   * @param {Event} e - Evento de submit do formulário.
   * @returns {boolean} True para permitir o envio, false para bloquear.
   */
  window.ensurePhoto = function ensurePhoto(e) {
    const submitter = e && e.submitter;
    if (submitter && submitter.name === 'skip') {
      return true;
    }
    const input = document.querySelector('[data-camera="1"] input[name="photo_data_url"]');
    if (!input || !input.value) {
      alert('Capture a foto antes de continuar. Ou clique em "Pular sem foto".');
      return false;
    }
    return true;
  };


  // ───────────────────────────────────────────────────────────────────
  // Listener — Limpa foto residual ao clicar em "Pular"
  // ───────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", () => {
    window.initCameraBlocks?.();

    // Garante que nenhuma foto residual seja enviada ao pular
    document.getElementById('skip-btn')?.addEventListener('click', () => {
      const h = document.getElementById('photo_data_url');
      if (h) h.value = '';
    });
  });


  // ───────────────────────────────────────────────────────────────────
  // Função Global — Inicialização dos Blocos de Câmera no DOM
  // ───────────────────────────────────────────────────────────────────

  /**
   * Percorre todos os blocos [data-camera="1"] na página e inicializa
   * os event listeners dos botões de abrir, capturar e fechar câmera.
   *
   * Estado inicial dos botões:
   * - "Capturar" e "Fechar": desabilitados (até a câmera abrir).
   * - "Confirmar" (data-enable-on-capture): desabilitado (até capturar).
   *
   * Também registra um listener em 'beforeunload' para liberar o
   * stream da câmera automaticamente ao sair/recarregar a página.
   */
  window.initCameraBlocks = function initCameraBlocks() {
    document.querySelectorAll('[data-camera="1"]').forEach(block => {

      // ── Referências aos elementos do bloco ────────────────────────
      const video            = block.querySelector("video");
      const imgPreview       = block.querySelector("[data-preview]");
      const input            = block.querySelector('input[type="hidden"][name="photo_data_url"]');

      const btnOpen            = block.querySelector("[data-open]");
      const btnCapture         = block.querySelector("[data-capture]");
      const btnClose           = block.querySelector("[data-close]");
      const btnEnableOnCapture = block.querySelector("[data-enable-on-capture]");

      let stream = null;

      // ── Estado inicial: botões desabilitados ──────────────────────
      if (btnCapture)         btnCapture.disabled = true;
      if (btnClose)           btnClose.disabled = true;
      if (btnEnableOnCapture) btnEnableOnCapture.disabled = true;

      // ── Botão "Abrir Câmera" ─────────────────────────────────────
      btnOpen?.addEventListener("click", async () => {
        try {
          stopCamera(stream);
          stream = await openCamera(video);

          if (btnCapture) btnCapture.disabled = false;
          if (btnClose)   btnClose.disabled = false;
        } catch (err) {
          console.error("[camera] open failed:", err?.name, err?.message, err);
          alert(`Câmera falhou: ${err?.name || "Erro"} - ${err?.message || String(err)}`);
        }
      });

      // ── Botão "Capturar Foto" ─────────────────────────────────────
      btnCapture?.addEventListener("click", () => {
        if (!stream || !video) return;
        const dataUrl = captureToDataURL(video);

        if (input)      input.value = dataUrl;
        if (imgPreview) {
          imgPreview.src = dataUrl;
          imgPreview.style.display = "block";
        }
        if (btnEnableOnCapture) btnEnableOnCapture.disabled = false;
      });

      // ── Botão "Fechar Câmera" ─────────────────────────────────────
      btnClose?.addEventListener("click", () => {
        stopCamera(stream);
        stream = null;

        if (video) {
          video.pause?.();
          video.srcObject = null;
        }

        if (btnCapture) btnCapture.disabled = true;
        if (btnClose)   btnClose.disabled = true;
      });

      // ── Libera câmera ao sair da página ───────────────────────────
      window.addEventListener("beforeunload", () => stopCamera(stream));
    });
  };


  // ───────────────────────────────────────────────────────────────────
  // Inicialização — DOMContentLoaded
  // ───────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", () => {
    window.initCameraBlocks?.();
  });

})();
