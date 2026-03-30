// =====================================================================
// wizard.js
// Módulo de Câmera do Wizard de Cadastro — Versão simplificada do
// controle de webcam, utilizada especificamente no fluxo de wizard
// (passo a passo) de cadastro de visitantes. Gerencia abertura da
// câmera, captura de snapshot redimensionado (640px de largura) e
// validação de foto obrigatória antes de avançar ao próximo passo.
// =====================================================================

// ─────────────────────────────────────────────────────────────────────
// Estado Global — Referência ao Stream de Vídeo
// ─────────────────────────────────────────────────────────────────────

/** @type {MediaStream|null} Stream ativo da câmera (null se desligada). */
let streamRef = null;


// ─────────────────────────────────────────────────────────────────────
// Função — Abertura da Câmera
// ─────────────────────────────────────────────────────────────────────

/**
 * Solicita acesso à câmera via getUserMedia e vincula o stream ao
 * elemento <video id="video"> da página do wizard.
 *
 * Em caso de falha (permissão negada, câmera indisponível), exibe
 * um alerta orientando o usuário a verificar permissões.
 *
 * @returns {Promise<void>}
 */
async function startCamera() {
  try {
    const video = document.getElementById("video");
    streamRef = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = streamRef;
  } catch (e) {
    alert("Não foi possível acessar a câmera. Verifique permissões do Windows/navegador embutido.");
  }
}


// ─────────────────────────────────────────────────────────────────────
// Função — Captura de Foto (Snapshot)
// ─────────────────────────────────────────────────────────────────────

/**
 * Captura o frame atual do <video> e o redimensiona para 640px de
 * largura (mantendo proporção), gerando uma Data URL JPEG a 75%
 * de qualidade.
 *
 * Elementos HTML esperados:
 * - <video id="video">           — Stream ativo da câmera.
 * - <canvas id="canvas">         — Canvas auxiliar (pode ser hidden).
 * - <img id="preview">           — Pré-visualização da foto capturada.
 * - <input id="photo_data_url">  — Campo hidden que armazena a Data URL.
 *
 * Fluxo:
 * 1. Valida se o vídeo está ativo (videoWidth > 0).
 * 2. Calcula escala proporcional para largura fixa de 640px.
 * 3. Desenha o frame no canvas redimensionado.
 * 4. Converte para Data URL JPEG (qualidade 75%).
 * 5. Armazena no input hidden e exibe a pré-visualização.
 */
function capturePhoto() {
  const video   = document.getElementById("video");
  const canvas  = document.getElementById("canvas");
  const preview = document.getElementById("preview");
  const output  = document.getElementById("photo_data_url");

  if (!video || !video.videoWidth) {
    alert("Ative a câmera antes de capturar.");
    return;
  }

  // ── Redimensionamento proporcional para 640px de largura ──────────
  const targetW = 640;
  const scale   = targetW / video.videoWidth;
  const targetH = Math.round(video.videoHeight * scale);

  canvas.width  = targetW;
  canvas.height = targetH;

  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, targetW, targetH);

  // ── Conversão para Data URL JPEG a 75% de qualidade ───────────────
  const dataUrl = canvas.toDataURL("image/jpeg", 0.75);
  output.value        = dataUrl;
  preview.src         = dataUrl;
  preview.style.display = "block";
}


// ─────────────────────────────────────────────────────────────────────
// Função — Validação de Foto Obrigatória
// ─────────────────────────────────────────────────────────────────────

/**
 * Verifica se uma foto já foi capturada antes de permitir que o
 * usuário avance para o próximo passo do wizard.
 *
 * Uso no HTML:
 *   <form onsubmit="return ensurePhoto()">
 *
 * @returns {boolean} True se a foto existe no campo hidden, false caso contrário.
 */
function ensurePhoto() {
  const output = document.getElementById("photo_data_url");
  if (!output || !output.value) {
    alert("Capture a foto antes de avançar.");
    return false;
  }
  return true;
}
