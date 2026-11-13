from pathlib import Path

from gerador_senhas import tema
from gerador_senhas.tema import PALETA_PADRAO, Paleta

COLORS_TOML = """
accent = "#89b4fa"
foreground = "#cdd6f4"
background = "#1e1e2e"
color1 = "#f38ba8"
color2 = "#a6e3a1"
color3 = "#f9e2af"
color4 = "#89b4fa"
"""


def criar_tema(base: Path, nome: str, arquivo: str, conteudo: str) -> Path:
    pasta = base / "theme"
    pasta.mkdir(parents=True)
    (pasta / arquivo).write_text(conteudo, encoding="utf-8")
    (base / "theme.name").write_text(nome + "\n", encoding="utf-8")
    return base


def test_normalizar_hex():
    assert tema.normalizar_hex("#ABCDEF") == "#abcdef"
    assert tema.normalizar_hex("0x1A2B3C") == "#1a2b3c"
    assert tema.normalizar_hex(" #123456 ") == "#123456"
    for invalido in ("#12345", "azul", "#gggggg", "", None, 42):
        assert tema.normalizar_hex(invalido) is None


def test_colors_toml(tmp_path):
    base = criar_tema(tmp_path / "current", "catppuccin", "colors.toml", COLORS_TOML)
    p = tema.detectar_paleta([base])
    assert (p.nome, p.fundo, p.texto, p.destaque) == ("catppuccin", "#1e1e2e", "#cdd6f4", "#89b4fa")
    assert (p.vermelho, p.verde, p.amarelo) == ("#f38ba8", "#a6e3a1", "#f9e2af")
    assert p.origem.endswith("colors.toml")
    assert p.escuro


def test_tema_claro_detectado(tmp_path):
    claro = COLORS_TOML.replace("#1e1e2e", "#eff1f5")
    base = criar_tema(tmp_path / "c", "latte", "colors.toml", claro)
    assert not tema.detectar_paleta([base]).escuro


def test_alacritty_legado(tmp_path):
    conteudo = """
[colors.primary]
background = "0x2e3440"
foreground = "#eceff4"
[colors.normal]
red = "#bf616a"
green = "#a3be8c"
yellow = "#ebcb8b"
blue = "#81a1c1"
"""
    base = criar_tema(tmp_path / "c", "nord", "alacritty.toml", conteudo)
    p = tema.detectar_paleta([base])
    assert (p.nome, p.fundo, p.destaque) == ("nord", "#2e3440", "#81a1c1")


def test_colors_toml_tem_prioridade_sobre_alacritty(tmp_path):
    base = criar_tema(tmp_path / "c", "x", "colors.toml", COLORS_TOML)
    (base / "theme" / "alacritty.toml").write_text(
        '[colors.primary]\nbackground="#000000"\nforeground="#ffffff"\n', encoding="utf-8"
    )
    assert tema.detectar_paleta([base]).fundo == "#1e1e2e"


def test_chaves_ausentes_usam_padrao(tmp_path):
    base = criar_tema(
        tmp_path / "c", "x", "colors.toml", 'background = "#101010"\nforeground = "#f0f0f0"\n'
    )
    p = tema.detectar_paleta([base])
    assert p.fundo == "#101010"
    assert p.destaque == PALETA_PADRAO.destaque


def test_sem_fundo_ou_texto_cai_no_padrao(tmp_path):
    base = criar_tema(tmp_path / "c", "x", "colors.toml", 'accent = "#89b4fa"\n')
    assert tema.detectar_paleta([base]) is PALETA_PADRAO


def test_toml_corrompido_nao_quebra(tmp_path):
    base = criar_tema(tmp_path / "c", "x", "colors.toml", "isto = = não é toml [[[")
    assert tema.detectar_paleta([base]) is PALETA_PADRAO


def test_sem_pasta_de_tema(tmp_path):
    assert tema.detectar_paleta([tmp_path / "inexistente"]) is PALETA_PADRAO


def test_usa_primeira_base_valida(tmp_path):
    nova = criar_tema(tmp_path / "nova", "novo", "colors.toml", COLORS_TOML)
    antiga = criar_tema(
        tmp_path / "antiga", "velho", "colors.toml", COLORS_TOML.replace("#1e1e2e", "#111111")
    )
    assert tema.detectar_paleta([tmp_path / "vazia", nova, antiga]).nome == "novo"


def test_nome_cai_para_pasta_sem_theme_name(tmp_path):
    base = criar_tema(tmp_path / "c", "x", "colors.toml", COLORS_TOML)
    (base / "theme.name").unlink()
    assert tema.detectar_paleta([base]).nome == "theme"


def test_variar_tom_direcao():
    assert tema.luminancia(tema.variar_tom("#1a1b26", 0.06)) > tema.luminancia("#1a1b26")
    assert tema.luminancia(tema.variar_tom("#eff1f5", 0.06)) < tema.luminancia("#eff1f5")


def test_variar_tom_limites():
    assert tema.variar_tom("#000000", 0.5) == "#7f7f7f"
    assert tema.variar_tom("#ffffff", 5.0) == "#000000"


def test_texto_sobre_destaque_garante_contraste():
    bom = Paleta("a", "#1a1b26", "#c0caf5", "#7aa2f7", "#0f0", "#ff0", "#f00")
    assert bom.texto_sobre_destaque == "#1a1b26"
    ruim = Paleta("b", "#808080", "#ffffff", "#858585", "#0f0", "#ff0", "#f00")
    assert ruim.texto_sobre_destaque in {"#101010", "#ffffff"}


def test_css_contem_cores_e_niveis():
    css = tema.gerar_css(PALETA_PADRAO)
    assert f"@define-color window_bg_color {PALETA_PADRAO.fundo};" in css
    for nivel in ("fraca", "media", "forte", "muito-forte"):
        assert f"progressbar.forca-{nivel}" in css
    assert css.count("{") == css.count("}")
