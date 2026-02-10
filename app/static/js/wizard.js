let streamRef = null;

// Inicia a câmera via getUserMedia para exibir no <video>.
async function startCamera() {
  try {
    const video = document.getElementById("video");
    streamRef = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = streamRef;
  } catch (e) {
    alert("Não foi possível acessar a câmera. Verifique permissões do Windows/navegador embutido.");
  }
}

// Captura um frame do <video> e armazena como dataURL em um campo hidden.
function capturePhoto() {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const preview = document.getElementById("preview");
  const output = document.getElementById("photo_data_url");

  if (!video || !video.videoWidth) {
    alert("Ative a câmera antes de capturar.");
    return;
  }

  const targetW = 640;
  const scale = targetW / video.videoWidth;
  const targetH = Math.round(video.videoHeight * scale);

  canvas.width = targetW;
  canvas.height = targetH;

  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, targetW, targetH);

  const dataUrl = canvas.toDataURL("image/jpeg", 0.75); // qualidade 75%
  output.value = dataUrl;
  preview.src = dataUrl;
  preview.style.display = "block";
}


// Garante que uma foto foi capturada antes de avançar.
function ensurePhoto() {
  const output = document.getElementById("photo_data_url");
  if (!output || !output.value) {
    alert("Capture a foto antes de avançar.");
    return false;
  }
  return true;
}
