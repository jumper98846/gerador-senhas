import math
import string

import pytest

from gerador_senhas import core
from gerador_senhas.core import ConfigSenha, Forca


def gerar_muitas(config: ConfigSenha, n: int = 300) -> list[str]:
    return [core.gerar_senha(config) for _ in range(n)]


def test_tamanho_respeitado():
    for tamanho in (core.TAMANHO_MIN, 20, core.TAMANHO_MAX):
        assert all(len(s) == tamanho for s in gerar_muitas(ConfigSenha(tamanho=tamanho), 50))


@pytest.mark.parametrize("tamanho", [core.TAMANHO_MIN - 1, core.TAMANHO_MAX + 1, 0, -5])
def test_tamanho_invalido(tamanho):
    with pytest.raises(ValueError):
        ConfigSenha(tamanho=tamanho)


def test_garante_todas_as_classes_no_menor_tamanho():
    # Pior caso: tamanho mínimo com 4 classes ativas.
    for senha in gerar_muitas(ConfigSenha(tamanho=core.TAMANHO_MIN)):
        assert any(c in string.ascii_lowercase for c in senha)
        assert any(c in string.ascii_uppercase for c in senha)
        assert any(c in string.digits for c in senha)
        assert any(c in core.SIMBOLOS for c in senha)


def test_evita_ambiguos():
    for senha in gerar_muitas(ConfigSenha(evitar_ambiguos=True)):
        assert not set(senha) & core.AMBIGUOS


def test_permite_ambiguos_quando_desativado():
    cfg = ConfigSenha(tamanho=64, evitar_ambiguos=False)
    assert set("".join(gerar_muitas(cfg, 100))) & core.AMBIGUOS


def test_respeita_classes_desativadas():
    cfg = ConfigSenha(maiusculas=False, numeros=False, simbolos=False)
    for senha in gerar_muitas(cfg, 100):
        assert set(senha) <= set(string.ascii_lowercase)


def test_apenas_simbolos_desativados():
    for senha in gerar_muitas(ConfigSenha(simbolos=False), 100):
        assert not set(senha) & set(core.SIMBOLOS)


def test_senhas_distintas():
    assert len(set(gerar_muitas(ConfigSenha(), 200))) == 200


def test_entropia_formula():
    cfg = ConfigSenha(
        tamanho=10, maiusculas=False, numeros=False, simbolos=False, evitar_ambiguos=False
    )
    assert core.entropia_bits(cfg) == pytest.approx(10 * math.log2(26))


def test_entropia_cresce_com_tamanho_e_classes():
    base = ConfigSenha(tamanho=12, simbolos=False)
    assert core.entropia_bits(ConfigSenha(tamanho=16, simbolos=False)) > core.entropia_bits(base)
    assert core.entropia_bits(ConfigSenha(tamanho=12)) > core.entropia_bits(base)


@pytest.mark.parametrize(
    ("bits", "esperado"),
    [
        (0, Forca.FRACA),
        (49.9, Forca.FRACA),
        (50, Forca.MEDIA),
        (74.9, Forca.MEDIA),
        (75, Forca.FORTE),
        (99.9, Forca.FORTE),
        (100, Forca.MUITO_FORTE),
        (300, Forca.MUITO_FORTE),
    ],
)
def test_classificar_forca(bits, esperado):
    assert core.classificar_forca(bits) is esperado


def test_fracao_barra_limitada():
    assert core.fracao_barra(-10) == 0.0
    assert core.fracao_barra(64) == pytest.approx(0.5)
    assert core.fracao_barra(999) == 1.0


def test_slug_forca():
    assert Forca.MUITO_FORTE.slug == "muito-forte"
    assert Forca.FRACA.slug == "fraca"


def test_tipo_caractere():
    assert core.tipo_caractere("a") == "letra"
    assert core.tipo_caractere("Z") == "letra"
    assert core.tipo_caractere("7") == "numero"
    for simbolo in core.SIMBOLOS:
        assert core.tipo_caractere(simbolo) == "simbolo"
