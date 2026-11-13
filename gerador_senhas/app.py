"""Interface GTK4 + libadwaita, integrada ao tema do Omarchy.

Pontos de projeto:
  * Área de transferência nativa (Gdk.Clipboard): dispensa `wl-clipboard`.
  * Tema via @define-color do libadwaita: um único CSS recolore todos os widgets.
  * Troca de tema detectada por Gio.FileMonitor (evento), sem polling.
  * Senha copiada é marcada como sensível e limpa automaticamente.
"""

from __future__ import annotations

import logging
import sys
from itertools import groupby

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from . import core, tema  # noqa: E402

log = logging.getLogger(__name__)

APP_ID = "local.GeradorSenhas"
TEMPO_LIMPEZA_S = 30


# --------------------------------------------------------------------------- #
# Observador do tema
# --------------------------------------------------------------------------- #
class ObservadorTema:
    """Vigia as pastas 'current' do Omarchy e avisa quando o tema é trocado.

    O `omarchy-theme-set` substitui a pasta `theme/` de uma vez (mv). Vários
    eventos chegam em sequência, então usamos *debounce*: só reagimos depois de
    um curto período sem novos eventos.
    """

    def __init__(self, ao_mudar, atraso_ms: int = 300) -> None:
        self._ao_mudar = ao_mudar
        self._atraso_ms = atraso_ms
        self._id_espera = 0
        self._monitores: list[Gio.FileMonitor] = []

        for pasta in tema.diretorios_correntes():
            if not pasta.is_dir():
                continue
            try:
                monitor = Gio.File.new_for_path(str(pasta)).monitor_directory(
                    Gio.FileMonitorFlags.NONE, None
                )
            except GLib.Error as erro:
                log.warning("Não foi possível monitorar %s: %s", pasta, erro)
                continue
            monitor.connect("changed", self._ao_evento)
            self._monitores.append(monitor)

    def _ao_evento(self, *_args) -> None:
        if self._id_espera:
            GLib.source_remove(self._id_espera)
        self._id_espera = GLib.timeout_add(self._atraso_ms, self._disparar)

    def _disparar(self) -> bool:
        self._id_espera = 0
        self._ao_mudar()
        return GLib.SOURCE_REMOVE


# --------------------------------------------------------------------------- #
# Clipboard
# --------------------------------------------------------------------------- #
def _conteudo_sensivel(senha: str) -> Gdk.ContentProvider:
    """Texto + dica 'x-kde-passwordManagerHint'.

    Gerenciadores de histórico que respeitam a convenção ignoram o item.
    """
    texto = Gdk.ContentProvider.new_for_value(GObject.Value(str, senha))
    dica = Gdk.ContentProvider.new_for_bytes("x-kde-passwordManagerHint", GLib.Bytes.new(b"secret"))
    return Gdk.ContentProvider.new_union([texto, dica])


# --------------------------------------------------------------------------- #
# Janela
# --------------------------------------------------------------------------- #
class JanelaPrincipal(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, paleta: tema.Paleta) -> None:
        super().__init__(application=app, title="Gerador de Senhas", default_width=480)
        self._paleta = paleta
        self._senha = ""
        self._bits = 0.0
        self._copiou = False
        self._id_limpeza = 0

        self._construir_interface()
        self._registrar_acoes()
        self.gerar()
        self.connect("close-request", self._ao_fechar)

    # -- construção ---------------------------------------------------------
    def _construir_interface(self) -> None:
        self._toasts = Adw.ToastOverlay()
        vista = Adw.ToolbarView()
        vista.add_top_bar(Adw.HeaderBar())
        self._toasts.set_child(vista)
        self.set_content(self._toasts)

        # Conteúdo rolável: se o gerenciador de janelas (tiling) der menos altura
        # que o necessário, o usuário rola em vez de ter a interface cortada.
        conteudo = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=6,
            margin_bottom=12,
            margin_start=18,
            margin_end=18,
        )
        conteudo.append(self._construir_cartao_senha())
        conteudo.append(self._construir_opcoes())

        self._rotulo_tema = Gtk.Label()
        self._rotulo_tema.add_css_class("dim-label")
        self._rotulo_tema.add_css_class("caption")
        conteudo.append(self._rotulo_tema)

        rolagem = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True,  # janela flutuante abre no tamanho ideal
            vexpand=True,
        )
        # Clamp: em janelas largas o conteúdo não se estica além de 520 px.
        rolagem.set_child(Adw.Clamp(maximum_size=520, tightening_threshold=480, child=conteudo))
        vista.set_content(rolagem)

        # Botões fixos na barra inferior: sempre visíveis, mesmo com a janela pequena.
        vista.add_bottom_bar(
            Adw.Clamp(
                maximum_size=520,
                tightening_threshold=480,
                child=self._construir_botoes(),
            )
        )

    def _construir_cartao_senha(self) -> Gtk.Widget:
        cartao = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        cartao.add_css_class("card")
        cartao.add_css_class("cartao-senha")

        self._rotulo_senha = Gtk.Label(
            wrap=True,
            wrap_mode=Pango.WrapMode.CHAR,
            justify=Gtk.Justification.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
        )
        self._rotulo_senha.add_css_class("senha")
        self._rotulo_senha.set_size_request(-1, 64)  # evita "pulos" de layout
        cartao.append(self._rotulo_senha)

        self._barra = Gtk.ProgressBar()
        self._barra.add_css_class("forca")
        cartao.append(self._barra)

        self._rotulo_forca = Gtk.Label()
        self._rotulo_forca.add_css_class("heading")
        cartao.append(self._rotulo_forca)
        return cartao

    def _construir_opcoes(self) -> Gtk.Widget:
        grupo = Adw.PreferencesGroup()

        self._escala = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, core.TAMANHO_MIN, core.TAMANHO_MAX, 1
        )
        self._escala.set_value(core.TAMANHO_PADRAO)
        self._escala.set_draw_value(True)
        self._escala.set_value_pos(Gtk.PositionType.LEFT)
        self._escala.set_size_request(230, -1)
        self._escala.set_valign(Gtk.Align.CENTER)
        linha = Adw.ActionRow(title="Tamanho")
        linha.add_suffix(self._escala)
        linha.set_activatable_widget(self._escala)
        grupo.add(linha)

        self._sw_maiusculas = self._nova_opcao(grupo, "Letras maiúsculas", "A–Z")
        self._sw_numeros = self._nova_opcao(grupo, "Números", "0–9")
        self._sw_simbolos = self._nova_opcao(grupo, "Símbolos", "!@#$%…")
        self._sw_ambiguos = self._nova_opcao(grupo, "Evitar caracteres ambíguos", "l, I, 1, O, 0")

        # Só conecta os sinais após o estado inicial, para não gerar senha à toa.
        self._escala.connect("value-changed", lambda *_: self.gerar())
        return grupo

    def _nova_opcao(self, grupo: Adw.PreferencesGroup, titulo: str, subtitulo: str):
        linha = Adw.SwitchRow(title=titulo, subtitle=subtitulo, active=True)
        linha.connect("notify::active", lambda *_: self.gerar())
        grupo.add(linha)
        return linha

    def _construir_botoes(self) -> Gtk.Widget:
        caixa = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            homogeneous=True,
            margin_top=6,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )

        self._btn_gerar = Gtk.Button(
            label="Gerar nova", action_name="win.gerar", tooltip_text="Ctrl+G ou F5"
        )
        self._btn_copiar = Gtk.Button(
            label="Copiar", action_name="win.copiar", tooltip_text="Ctrl+C"
        )
        self._btn_copiar.add_css_class("suggested-action")
        for botao in (self._btn_gerar, self._btn_copiar):
            botao.add_css_class("pill")
            caixa.append(botao)

        self.set_default_widget(self._btn_gerar)  # Enter gera uma nova senha
        return caixa

    def _registrar_acoes(self) -> None:
        for nome, funcao in (("gerar", self.gerar), ("copiar", self.copiar)):
            acao = Gio.SimpleAction.new(nome, None)
            acao.connect("activate", lambda _a, _p, f=funcao: f())
            self.add_action(acao)

    # -- estado -------------------------------------------------------------
    def _config_atual(self) -> core.ConfigSenha:
        return core.ConfigSenha(
            tamanho=int(self._escala.get_value()),
            maiusculas=self._sw_maiusculas.get_active(),
            numeros=self._sw_numeros.get_active(),
            simbolos=self._sw_simbolos.get_active(),
            evitar_ambiguos=self._sw_ambiguos.get_active(),
        )

    def gerar(self) -> None:
        config = self._config_atual()
        self._senha = core.gerar_senha(config)
        self._bits = core.entropia_bits(config)
        self._atualizar_exibicao()

    def definir_paleta(self, paleta: tema.Paleta) -> None:
        self._paleta = paleta
        self._atualizar_exibicao()

    # -- exibição -----------------------------------------------------------
    def _markup_senha(self) -> str:
        """Colore por classe: letras (texto), números (destaque), símbolos (amarelo)."""
        cores = {
            "letra": self._paleta.texto,
            "numero": self._paleta.destaque,
            "simbolo": self._paleta.amarelo,
        }
        trechos = []
        for tipo, grupo in groupby(self._senha, key=core.tipo_caractere):
            texto = GLib.markup_escape_text("".join(grupo))  # '<', '>' e '&' são símbolos!
            trechos.append(f'<span foreground="{cores[tipo]}">{texto}</span>')
        return "".join(trechos)

    def _atualizar_exibicao(self) -> None:
        forca = core.classificar_forca(self._bits)

        self._rotulo_senha.set_markup(self._markup_senha())
        self._barra.set_fraction(core.fracao_barra(self._bits))
        self._rotulo_forca.set_text(f"{forca.value} · {self._bits:.0f} bits")
        self._rotulo_tema.set_text(f"Tema Omarchy: {self._paleta.nome}")

        for nivel in core.Forca:
            for widget in (self._barra, self._rotulo_forca):
                widget.remove_css_class(f"forca-{nivel.slug}")
        for widget in (self._barra, self._rotulo_forca):
            widget.add_css_class(f"forca-{forca.slug}")

    # -- clipboard ----------------------------------------------------------
    def copiar(self) -> None:
        self.get_clipboard().set_content(_conteudo_sensivel(self._senha))
        self._copiou = True
        self._agendar_limpeza()
        self._toasts.add_toast(
            Adw.Toast(title=f"Senha copiada. Limpeza automática em {TEMPO_LIMPEZA_S} s.", timeout=3)
        )

    def _agendar_limpeza(self) -> None:
        self._cancelar_limpeza()
        self._id_limpeza = GLib.timeout_add_seconds(TEMPO_LIMPEZA_S, self._limpar_clipboard)

    def _cancelar_limpeza(self) -> None:
        if self._id_limpeza:
            GLib.source_remove(self._id_limpeza)
            self._id_limpeza = 0

    def _limpar_clipboard(self) -> bool:
        """Só limpa se o conteúdo ainda for nosso (não apaga algo copiado depois)."""
        self._id_limpeza = 0
        clipboard = self.get_clipboard()
        if self._copiou and clipboard.is_local():
            clipboard.set_content(None)
        self._copiou = False
        return GLib.SOURCE_REMOVE

    def _ao_fechar(self, *_args) -> bool:
        self._cancelar_limpeza()
        self._limpar_clipboard()
        return False  # permite fechar


# --------------------------------------------------------------------------- #
# Aplicação
# --------------------------------------------------------------------------- #
class Aplicacao(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self._janela: JanelaPrincipal | None = None
        self._css = Gtk.CssProvider()
        self._paleta = tema.detectar_paleta()
        self._observador: ObservadorTema | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)  # inicializa libadwaita
        Gtk.Window.set_default_icon_name(APP_ID)  # ícone instalado pelo install.sh

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self._aplicar_paleta(self._paleta)

        sair = Gio.SimpleAction.new("sair", None)
        sair.connect("activate", lambda *_: self.quit())
        self.add_action(sair)
        self.set_accels_for_action("app.sair", ["<Control>q", "Escape"])
        self.set_accels_for_action("win.gerar", ["<Control>g", "F5"])
        self.set_accels_for_action("win.copiar", ["<Control>c"])

        self._observador = ObservadorTema(self._recarregar_tema)

    def do_activate(self) -> None:
        if self._janela is None:
            self._janela = JanelaPrincipal(self, self._paleta)
        self._janela.present()

    def _aplicar_paleta(self, paleta: tema.Paleta) -> None:
        self._paleta = paleta
        esquema = Adw.ColorScheme.FORCE_DARK if paleta.escuro else Adw.ColorScheme.FORCE_LIGHT
        Adw.StyleManager.get_default().set_color_scheme(esquema)

        css = tema.gerar_css(paleta)
        if hasattr(self._css, "load_from_string"):  # GTK >= 4.12
            self._css.load_from_string(css)
        else:
            self._css.load_from_data(css.encode())

        if self._janela is not None:
            self._janela.definir_paleta(paleta)

    def _recarregar_tema(self) -> None:
        nova = tema.detectar_paleta()
        if nova != self._paleta:
            log.info("Tema alterado para '%s'", nova.nome)
            self._aplicar_paleta(nova)


def executar() -> int:
    # Não repassamos nossos argumentos ao GApplication (ele não os conhece).
    return Aplicacao().run([sys.argv[0]])
