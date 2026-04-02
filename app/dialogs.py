# =====================================================================
# app/dialogs.py
# Módulo de Diálogos Visuais — Centraliza todas as janelas de
# mensagem, confirmação e progresso da aplicação. Utiliza Tkinter
# para criar interfaces nativas do Windows sem dependências externas.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import logging

from app.paths import icon_path

log = logging.getLogger("sisport.dialogs")


# =====================================================================
# Função Auxiliar — Ícone Personalizado
# =====================================================================

def _apply_icon(window: tk.Tk) -> None:
    """
    Aplica o ícone personalizado do SISPORT na janela Tkinter,
    substituindo a pena padrão do Tk. Silencia erros caso o
    arquivo não exista (fallback para o ícone padrão).

    :param window: (tk.Tk) Janela alvo.
    """
    try:
        window.iconbitmap(icon_path())
    except Exception:
        pass


# =====================================================================
# Classe Base — Janela Tkinter Oculta
# =====================================================================

def _hidden_root() -> tk.Tk:
    """
    Cria uma janela Tk invisível para hospedar diálogos nativos.
    Garante que nenhuma janela fantasma apareça na taskbar.

    :return: (tk.Tk) Instância da janela oculta.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    _apply_icon(root)
    root.update()
    return root


# =====================================================================
# Diálogos Simples — Info, Aviso, Erro, Confirmação
# =====================================================================

def show_info(title: str, message: str) -> None:
    """
    Exibe uma mensagem informativa (ícone ℹ️).

    :param title:   (str) Título da janela.
    :param message: (str) Corpo da mensagem.
    """
    root = _hidden_root()
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def show_warning(title: str, message: str) -> None:
    """
    Exibe uma mensagem de aviso (ícone ⚠️).

    :param title:   (str) Título da janela.
    :param message: (str) Corpo da mensagem.
    """
    root = _hidden_root()
    messagebox.showwarning(title, message, parent=root)
    root.destroy()


def show_error(title: str, message: str) -> None:
    """
    Exibe uma mensagem de erro (ícone ❌).

    :param title:   (str) Título da janela.
    :param message: (str) Corpo da mensagem.
    """
    root = _hidden_root()
    messagebox.showerror(title, message, parent=root)
    root.destroy()


def ask_yes_no(title: str, message: str) -> bool:
    """
    Exibe um diálogo de confirmação Sim/Não.

    :param title:   (str) Título da janela.
    :param message: (str) Pergunta exibida ao usuário.
    :return: (bool) True se "Sim", False se "Não".
    """
    root = _hidden_root()
    result = messagebox.askyesno(title, message, parent=root)
    root.destroy()
    return result


# =====================================================================
# Janela de Progresso — Download / Instalação
# =====================================================================

class ProgressWindow:
    """
    Janela de progresso visual para operações longas (download, instalação).
    Exibe título, mensagem de status, barra de progresso e percentual.

    Uso:
        pw = ProgressWindow("Atualizando", "Baixando atualização...")
        pw.show()
        pw.update_progress(50, "Baixando... 50%")
        pw.update_status("Instalando atualização...")
        pw.set_indeterminate()
        pw.close()
    """

    def __init__(self, title: str, status: str = "Aguarde..."):
        """
        Inicializa a janela de progresso (ainda não exibe).

        :param title:  (str) Título da janela.
        :param status: (str) Mensagem de status inicial.
        """
        self._title = title
        self._status_text = status
        self._root = None
        self._progress_bar = None
        self._status_label = None
        self._percent_label = None
        self._ready = threading.Event()
        self._thread = None

    def show(self) -> None:
        """
        Abre a janela de progresso em uma thread separada (não bloqueia).
        Aguarda até que a janela esteja pronta para receber atualizações.
        """
        self._thread = threading.Thread(
            target=self._create_window,
            daemon=True,
            name="progress-window",
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    def _create_window(self):
        """Cria a janela Tkinter na thread dedicada."""
        self._root = tk.Tk()
        self._root.title(self._title)
        self._root.resizable(False, False)
        self._root.attributes("-topmost", True)
        _apply_icon(self._root)
        self._root.protocol("WM_DELETE_WINDOW", lambda: None)

        # ── Dimensões e centralização ──
        w, h = 420, 150
        sx = self._root.winfo_screenwidth() // 2 - w // 2
        sy = self._root.winfo_screenheight() // 2 - h // 2
        self._root.geometry(f"{w}x{h}+{sx}+{sy}")

        # ── Frame principal ──
        frame = tk.Frame(self._root, padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        # ── Label de status ──
        self._status_label = tk.Label(
            frame,
            text=self._status_text,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._status_label.pack(fill="x", pady=(0, 8))

        # ── Barra de progresso ──
        self._progress_bar = ttk.Progressbar(
            frame,
            orient="horizontal",
            length=380,
            mode="determinate",
            maximum=100,
        )
        self._progress_bar.pack(fill="x", pady=(0, 5))

        # ── Label de percentual ──
        self._percent_label = tk.Label(
            frame,
            text="0%",
            font=("Segoe UI", 9),
            fg="#555555",
            anchor="e",
        )
        self._percent_label.pack(fill="x")

        self._ready.set()
        self._root.mainloop()

    def update_progress(self, percent: float, status: str = None) -> None:
        """
        Atualiza a barra de progresso e, opcionalmente, o texto de status.

        :param percent: (float) Valor de 0 a 100.
        :param status:  (str|None) Nova mensagem de status (opcional).
        """
        if not self._root:
            return

        def _update():
            try:
                self._progress_bar.configure(mode="determinate", value=percent)
                self._percent_label.configure(text=f"{percent:.0f}%")
                if status:
                    self._status_label.configure(text=status)
            except tk.TclError:
                pass

        self._root.after(0, _update)

    def update_status(self, status: str) -> None:
        """
        Atualiza apenas o texto de status sem alterar a barra.

        :param status: (str) Nova mensagem de status.
        """
        if not self._root:
            return

        def _update():
            try:
                self._status_label.configure(text=status)
            except tk.TclError:
                pass

        self._root.after(0, _update)

    def set_indeterminate(self, status: str = None) -> None:
        """
        Coloca a barra em modo indeterminado (animação contínua).
        Útil para etapas sem progresso mensurável (ex: instalando...).

        :param status: (str|None) Nova mensagem de status (opcional).
        """
        if not self._root:
            return

        def _update():
            try:
                self._progress_bar.configure(mode="indeterminate")
                self._progress_bar.start(15)
                self._percent_label.configure(text="")
                if status:
                    self._status_label.configure(text=status)
            except tk.TclError:
                pass

        self._root.after(0, _update)

    def close(self) -> None:
        """Fecha a janela de progresso com segurança."""
        if not self._root:
            return

        def _close():
            try:
                self._root.quit()
                self._root.destroy()
            except tk.TclError:
                pass

        try:
            self._root.after(0, _close)
        except Exception:
            pass

        self._root = None