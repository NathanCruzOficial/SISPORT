# =====================================================================
# app/loading.py
# Splash thread-safe — Tkinter roda em thread daemon e recebe comandos
# de qualquer thread através de queue.Queue.
#
# Layout: logo + título lado a lado, versão abaixo, status, barra de
# progresso e botão de cancelar (visível apenas durante o download).
# =====================================================================

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import threading
import queue

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


class LoadingWindow:
    """Splash centralizado, sem bordas, abaixo das janelas de diálogo."""

    def __init__(
        self,
        title: str = "SISPORT",
        image_path=None,
        version: str | None = None,
        width: int = 520,
        height: int = 340,
        gradient_top: str = "#2e5c1f",
        gradient_bottom: str = "#1d4310",
        accent: str = "#ffffff",
        text_color: str = "#ffffff",
        muted_color: str = "#e4ebc8",
        subtle_color: str = "#b3c27e",
        copyright_text: str = "© 2026 Nathan Cruz",
        license_text: str = "Licenciado sob a Licença MIT",
    ):
        self.title = title
        self.image_path = image_path
        self.version = version
        self.width = width
        self.height = height

        self.gradient_top = gradient_top
        self.gradient_bottom = gradient_bottom
        self.accent = accent
        self.text_color = text_color
        self.muted_color = muted_color
        self.subtle_color = subtle_color
        self.copyright_text = copyright_text
        self.license_text = license_text

        self._root = None
        self._thread = None
        self._ready = threading.Event()
        self._queue = queue.Queue()

        self._canvas = None
        self._status_item = None
        self._percent_item = None
        self._progress = None
        self._image_ref = None
        self._closable = False
        self._indeterminate_active = False

        # Cancelamento do download
        self._cancel_signal = threading.Event()
        self._cancel_visible = False
        self._cancel_btn = None
        self._cancel_btn_id = None

    # ── Thread Tkinter ──────────────────────────────────────────────
    def show(self):
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_tk, daemon=True, name="loading-window"
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run_tk(self):
        try:
            self._root = tk.Tk()
            self._root.title(self.title)

            # Sem bordas de janela
            self._root.overrideredirect(True)

            # NÃO força ficar acima das outras janelas.
            # Assim dialogs de erro/confirmação aparecem naturalmente na frente.
            self._root.attributes("-topmost", False)

            self._center_window()
            self._build_ui()

            # Garante que a janela seja desenhada e visível
            self._root.deiconify()
            self._root.update_idletasks()
            self._root.update()

            self._root.protocol("WM_DELETE_WINDOW", self._block_close)
            self._root.after(30, self._poll_queue)

            self._ready.set()
            self._root.mainloop()
        except Exception as e:
            # Se o splash travar silenciosamente, pelo menos logamos.
            print(f"[LoadingWindow] Erro ao criar splash: {e}", file=sys.stderr)
            self._ready.set()

    def _block_close(self):
        if not self._closable:
            return
        # Chamado de dentro da própria thread Tk (ex.: WM_CLOSE enviado pelo
        # instalador InnoSetup). Encerra direto, sem join(), para não travar
        # a thread nela mesma.
        self._root.quit()
        self._root.destroy()

    def _poll_queue(self):
        try:
            while True:
                try:
                    cmd = self._queue.get_nowait()
                except queue.Empty:
                    break
                self._handle_command(cmd)
        except tk.TclError:
            return
        try:
            self._root.after(30, self._poll_queue)
        except tk.TclError:
            pass

    def _handle_command(self, cmd):
        kind = cmd[0]

        if kind == "status":
            if self._status_item is not None:
                self._canvas.itemconfig(self._status_item, text=cmd[1])

        elif kind == "progress":
            percent, text = cmd[1], cmd[2]
            self._indeterminate_active = False
            self._progress.stop()
            self._progress.configure(mode="determinate", maximum=100, value=percent)
            if self._percent_item is not None:
                self._canvas.itemconfig(self._percent_item, text=f"{percent:.0f}%")
            if text and self._status_item is not None:
                self._canvas.itemconfig(self._status_item, text=text)

        elif kind == "indeterminate":
            text = cmd[1]
            if not self._indeterminate_active:
                self._progress.stop()
                self._progress.configure(mode="indeterminate")
                self._progress.start(20)
                self._indeterminate_active = True
            if self._percent_item is not None:
                self._canvas.itemconfig(self._percent_item, text="")
            if text and self._status_item is not None:
                self._canvas.itemconfig(self._status_item, text=text)

        elif kind == "closable":
            self._closable = bool(cmd[1])

        elif kind == "cancel_visible":
            self._set_cancel_visibility(bool(cmd[1]))

        elif kind == "close":
            self._root.quit()
            self._root.destroy()

    # ── Posicionamento / degradê ────────────────────────────────────
    def _center_window(self):
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - self.width) // 2
        y = (sh - self.height) // 2
        self._root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    @staticmethod
    def _hex_to_rgb(value: str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def _draw_gradient(self, canvas):
        top = self._hex_to_rgb(self.gradient_top)
        bottom = self._hex_to_rgb(self.gradient_bottom)
        steps = max(self.height - 1, 1)
        for y in range(self.height):
            t = y / steps
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            canvas.create_line(0, y, self.width, y, fill=f"#{r:02x}{g:02x}{b:02x}")

    # ── Interface ───────────────────────────────────────────────────
    def _build_ui(self):
        canvas = tk.Canvas(
            self._root,
            width=self.width,
            height=self.height,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
        self._canvas = canvas
        self._draw_gradient(canvas)

        cx = self.width // 2
        logo_x = cx - 58
        title_x = cx - 32

        # Logo + título lado a lado
        if self.image_path and Path(self.image_path).exists():
            self._add_image(canvas, self.image_path, logo_x)
        else:
            self._add_placeholder_logo(canvas, logo_x)

        canvas.create_text(
            title_x, 88, text="SISPORT", anchor="w",
            fill=self.text_color, font=("Segoe UI", 22, "bold"),
        )

        # Versão abaixo do bloco
        if self.version:
            canvas.create_text(
                cx, 130, text=f"v{self.version}",
                fill=self.muted_color, font=("Segoe UI", 10),
            )

        # Status
        self._status_item = canvas.create_text(
            cx, 172, text="Inicializando...",
            fill=self.muted_color, font=("Segoe UI", 10),
        )

        # Barra de progresso
        style = ttk.Style(self._root)
        style.theme_use("clam")
        style.configure(
            "Loading.Horizontal.TProgressbar",
            troughcolor="#1f2a0d",
            background=self.accent,
            bordercolor="#1f2a0d",
            lightcolor=self.accent,
            darkcolor=self.accent,
            thickness=8,
        )

        self._progress = ttk.Progressbar(
            canvas,
            mode="indeterminate",
            length=400,
            style="Loading.Horizontal.TProgressbar",
        )
        canvas.create_window(cx, 224, window=self._progress, width=400)
        self._progress.start(20)

        # Percentual
        self._percent_item = canvas.create_text(
            self.width - 36, 250, text="",
            fill=self.subtle_color, font=("Segoe UI", 9), anchor="e",
        )

        # Copyright / licença
        canvas.create_text(
            cx, self.height - 34, text=self.copyright_text,
            fill=self.subtle_color, font=("Segoe UI", 8),
        )
        canvas.create_text(
            cx, self.height - 16, text=self.license_text,
            fill=self.subtle_color, font=("Segoe UI", 8),
        )

    # ── Logo / placeholder ──────────────────────────────────────────
    def _add_image(self, canvas, image_path, cx):
        if _HAS_PIL:
            try:
                img = Image.open(image_path)
                img.thumbnail((44, 44), Image.LANCZOS)
                self._image_ref = ImageTk.PhotoImage(img)
                canvas.create_image(cx, 88, image=self._image_ref, anchor="center")
                return
            except Exception:
                pass

        try:
            self._image_ref = tk.PhotoImage(file=str(image_path))
            canvas.create_image(cx, 88, image=self._image_ref, anchor="center")
        except Exception:
            self._add_placeholder_logo(canvas, cx)

    def _add_placeholder_logo(self, canvas, cx):
        canvas.create_text(cx, 88, text="🛡️", font=("Segoe UI Emoji", 28))

    # ── Botão de cancelar (só durante download) ─────────────────────
    def _create_cancel_button(self):
        if self._cancel_btn_id is not None:
            return
        self._cancel_btn = tk.Button(
            self._root,
            text="Cancelar",
            command=self._on_cancel_click,
            bd=0,
            relief="flat",
            highlightthickness=0,
            bg=self.gradient_bottom,
            fg=self.subtle_color,
            activebackground=self.gradient_bottom,
            activeforeground=self.text_color,
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
        )
        self._cancel_btn_id = self._canvas.create_window(
            12, self.height - 24, anchor="w", window=self._cancel_btn
        )

    def _on_cancel_click(self):
        self._cancel_signal.set()
        if self._cancel_btn is not None:
            self._cancel_btn.configure(
                text="Cancelando...", state="disabled", cursor="arrow"
            )

    def _remove_cancel_button(self):
        if self._cancel_btn_id is not None:
            self._canvas.delete(self._cancel_btn_id)
            self._cancel_btn_id = None
        if self._cancel_btn is not None:
            self._cancel_btn.destroy()
            self._cancel_btn = None

    def _set_cancel_visibility(self, visible: bool):
        if visible and self._cancel_btn_id is None:
            self._create_cancel_button()
        elif not visible:
            self._remove_cancel_button()

    # ── API pública (thread-safe) ───────────────────────────────────
    def set_status(self, text: str):
        self._queue.put(("status", text))

    def update_status(self, text: str):
        self.set_status(text)

    def update_progress(self, percent: float, text: str | None = None):
        self._queue.put(("progress", float(percent), text))

    def set_indeterminate(self, text: str | None = None):
        self._queue.put(("indeterminate", text))

    def set_closable(self, closable: bool):
        self._queue.put(("closable", bool(closable)))

    def set_cancel_visible(self, visible: bool):
        self._queue.put(("cancel_visible", bool(visible)))

    def is_cancelled(self) -> bool:
        return self._cancel_signal.is_set()

    def reset_cancel(self):
        self._cancel_signal.clear()

    def update(self):
        """No-op — o mainloop da thread própria mantém a animação."""
        pass

    def close(self):
        if not self._thread or not self._thread.is_alive():
            self._root = None
            self._thread = None
            return

        if threading.current_thread() is self._thread:
            # Chamado de dentro da thread Tk — encerra direto, sem join().
            self._root.quit()
            self._root.destroy()
            return

        self._queue.put(("close",))
        self._thread.join(timeout=2)
        self._root = None
        self._thread = None

    def is_alive(self) -> bool:
        """True enquanto a janela do splash estiver aberta."""
        return self._thread is not None and self._thread.is_alive()
