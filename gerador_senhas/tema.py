"""Integração com o tema ativo do Omarchy.

Fonte primária: `colors.toml` do tema ativo (formato oficial do Omarchy).
Fallback legado: `alacritty.toml` (versões antigas).
Fallback final: paleta Tokyo Night embutida.

Local do tema ativo (XDG):
    ~/.local/state/omarchy/current/theme/       <- versões atuais
    ~/.config/omarchy/current/theme/            <- versões antigas
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Acima deste brilho percebido (0–1), o fundo é considerado claro.
LIMIAR_TEMA_CLARO = 0.55
_HEX = re.compile(r"^(?:#|0x)([0-9a-fA-F]{6})$")


# --------------------------------------------------------------------------- #
# Utilitários de cor
# --------------------------------------------------------------------------- #
def normalizar_hex(valor: Any) -> str | None:
    """Aceita '#rrggbb' ou '0xrrggbb' e devolve '#rrggbb' (minúsculo), ou None."""
    if not isinstance(valor, str):
        return None
    achado = _HEX.match(valor.strip())
    return f"#{achado.group(1).lower()}" if achado else None


def _rgb(cor: str) -> tuple[int, int, int]:
    return int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)


def luminancia(cor: str) -> float:
    """Brilho percebido de 0.0 (preto) a 1.0 (branco)."""
    r, g, b = _rgb(cor)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def variar_tom(cor: str, fator: float) -> str:
    """Clareia cores escuras e escurece cores claras (usado no 'cartão')."""
    delta = int(255 * fator)
    if luminancia(cor) > LIMIAR_TEMA_CLARO:
        delta = -delta
    canais = (max(0, min(255, c + delta)) for c in _rgb(cor))
    return "#{:02x}{:02x}{:02x}".format(*canais)


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Paleta:
    """Cores semânticas extraídas do tema."""

    nome: str
    fundo: str
    texto: str
    destaque: str
    verde: str
    amarelo: str
    vermelho: str
    origem: str = "padrão interno"

    @property
    def escuro(self) -> bool:
        return luminancia(self.fundo) <= LIMIAR_TEMA_CLARO

    @property
    def cartao(self) -> str:
        return variar_tom(self.fundo, 0.06)

    @property
    def texto_sobre_destaque(self) -> str:
        """Cor de texto legível sobre o destaque (usa o fundo do tema se houver contraste)."""
        if abs(luminancia(self.fundo) - luminancia(self.destaque)) >= 0.35:
            return self.fundo
        return "#101010" if luminancia(self.destaque) > 0.5 else "#ffffff"


PALETA_PADRAO = Paleta(
    nome="tokyo-night",
    fundo="#1a1b26",
    texto="#c0caf5",
    destaque="#7aa2f7",
    verde="#9ece6a",
    amarelo="#e0af68",
    vermelho="#f7768e",
)


# --------------------------------------------------------------------------- #
# Leitura dos arquivos de tema
# --------------------------------------------------------------------------- #
def diretorios_correntes() -> list[Path]:
    """Pastas 'current' do Omarchy, da mais recente para a mais antiga."""
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return [estado / "omarchy" / "current", config / "omarchy" / "current"]


def _ler_toml(caminho: Path) -> dict[str, Any] | None:
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError) as erro:
        log.warning("Não foi possível ler %s: %s", caminho, erro)
        return None


def _paleta_de_colors_toml(dados: dict[str, Any], nome: str, origem: str) -> Paleta | None:
    """Converte o formato `colors.toml` do Omarchy (chaves planas) em Paleta."""
    fundo = normalizar_hex(dados.get("background"))
    texto = normalizar_hex(dados.get("foreground"))
    if not (fundo and texto):
        return None  # sem fundo/texto a paleta não faz sentido

    def cor(chave: str, padrao: str, *alternativas: str) -> str:
        for k in (chave, *alternativas):
            valor = normalizar_hex(dados.get(k))
            if valor:
                return valor
        return padrao

    return Paleta(
        nome=nome,
        fundo=fundo,
        texto=texto,
        destaque=cor("accent", PALETA_PADRAO.destaque, "color4"),
        verde=cor("color2", PALETA_PADRAO.verde),
        amarelo=cor("color3", PALETA_PADRAO.amarelo),
        vermelho=cor("color1", PALETA_PADRAO.vermelho),
        origem=origem,
    )


def _paleta_de_alacritty(dados: dict[str, Any], nome: str, origem: str) -> Paleta | None:
    """Fallback para versões antigas: reaproveita o conversor acima."""
    cores = dados.get("colors", {})
    primaria = cores.get("primary", {})
    normal = cores.get("normal", {})
    return _paleta_de_colors_toml(
        {
            "background": primaria.get("background"),
            "foreground": primaria.get("foreground"),
            "accent": normal.get("blue"),
            "color1": normal.get("red"),
            "color2": normal.get("green"),
            "color3": normal.get("yellow"),
        },
        nome,
        origem,
    )


_Conversor = Callable[[dict[str, Any], str, str], Paleta | None]
_FONTES: tuple[tuple[str, _Conversor], ...] = (
    ("colors.toml", _paleta_de_colors_toml),
    ("alacritty.toml", _paleta_de_alacritty),
)


def _nome_do_tema(base: Path, pasta_tema: Path) -> str:
    try:
        nome = (base / "theme.name").read_text(encoding="utf-8").strip()
        if nome:
            return nome
    except OSError:
        pass
    return pasta_tema.resolve().name


def detectar_paleta(bases: Sequence[Path] | None = None) -> Paleta:
    """Detecta o tema ativo. `bases` permite injetar pastas (útil em testes)."""
    for base in bases if bases is not None else diretorios_correntes():
        pasta = base / "theme"
        if not pasta.is_dir():
            continue
        nome = _nome_do_tema(base, pasta)
        for arquivo, converter in _FONTES:
            dados = _ler_toml(pasta / arquivo)
            if dados is None:
                continue
            paleta = converter(dados, nome, str(pasta / arquivo))
            if paleta is not None:
                return paleta
    log.info("Tema do Omarchy não encontrado; usando paleta padrão.")
    return PALETA_PADRAO


# --------------------------------------------------------------------------- #
# Geração de CSS (GTK4 / libadwaita)
# --------------------------------------------------------------------------- #
def gerar_css(p: Paleta) -> str:
    """CSS que sobrescreve as cores nomeadas do libadwaita e define estilos do app."""
    niveis = {
        "fraca": p.vermelho,
        "media": p.amarelo,
        "forte": p.verde,
        "muito-forte": p.destaque,
    }
    css_forca = "\n".join(
        f"label.forca-{nome} {{ color: {cor}; }}\n"
        f"progressbar.forca-{nome} > trough > progress {{ background-color: {cor}; }}"
        for nome, cor in niveis.items()
    )
    return f"""
@define-color window_bg_color {p.fundo};
@define-color window_fg_color {p.texto};
@define-color view_bg_color {p.cartao};
@define-color view_fg_color {p.texto};
@define-color headerbar_bg_color {p.fundo};
@define-color headerbar_fg_color {p.texto};
@define-color card_bg_color {p.cartao};
@define-color card_fg_color {p.texto};
@define-color popover_bg_color {p.cartao};
@define-color popover_fg_color {p.texto};
@define-color accent_bg_color {p.destaque};
@define-color accent_fg_color {p.texto_sobre_destaque};
@define-color accent_color {p.destaque};
@define-color success_color {p.verde};
@define-color warning_color {p.amarelo};
@define-color error_color {p.vermelho};

.cartao-senha {{ padding: 24px 20px 18px 20px; }}
.senha {{ font-family: monospace; font-size: 21px; font-weight: 600; }}

progressbar.forca > trough {{ min-height: 6px; }}
progressbar.forca > trough > progress {{ min-height: 6px; border-radius: 3px; }}
{css_forca}
"""
