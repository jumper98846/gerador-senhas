"""Núcleo do gerador: geração, estimativa de entropia e classificação de força.

Este módulo NÃO depende de interface gráfica. Por isso a mesma lógica serve à
GUI, à linha de comando e aos testes automatizados (separação de responsabilidades).
"""

from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass
from enum import Enum

TAMANHO_MIN = 8
TAMANHO_MAX = 64
TAMANHO_PADRAO = 20

SIMBOLOS = "!@#$%^&*()-_=+[]{};:,.<>?"
AMBIGUOS = frozenset("lI1O0")

# Teto da barra de força: acima de ~128 bits o ganho prático é nulo.
ENTROPIA_TETO_BARRA = 128.0


class Forca(Enum):
    """Níveis de força. O valor é o rótulo exibido ao usuário."""

    FRACA = "Fraca"
    MEDIA = "Média"
    FORTE = "Forte"
    MUITO_FORTE = "Muito forte"

    @property
    def slug(self) -> str:
        """Identificador usado em classes CSS (ex.: 'muito-forte')."""
        return self.name.lower().replace("_", "-")


# (limite superior exclusivo em bits, nível) — ordem crescente.
_FAIXAS_FORCA: tuple[tuple[float, Forca], ...] = (
    (50.0, Forca.FRACA),
    (75.0, Forca.MEDIA),
    (100.0, Forca.FORTE),
)


@dataclass(frozen=True, slots=True)
class ConfigSenha:
    """Parâmetros de geração. Imutável e validado na criação."""

    tamanho: int = TAMANHO_PADRAO
    maiusculas: bool = True
    numeros: bool = True
    simbolos: bool = True
    evitar_ambiguos: bool = True

    def __post_init__(self) -> None:
        if not TAMANHO_MIN <= self.tamanho <= TAMANHO_MAX:
            raise ValueError(
                f"tamanho deve estar entre {TAMANHO_MIN} e {TAMANHO_MAX} (recebido: {self.tamanho})"
            )

    def alfabetos(self) -> tuple[str, ...]:
        """Conjuntos de caracteres ativos, já sem os ambíguos se solicitado.

        Minúsculas sempre entram: garante que o pool nunca fique vazio.
        """
        conjuntos = [string.ascii_lowercase]
        if self.maiusculas:
            conjuntos.append(string.ascii_uppercase)
        if self.numeros:
            conjuntos.append(string.digits)
        if self.simbolos:
            conjuntos.append(SIMBOLOS)

        if self.evitar_ambiguos:
            conjuntos = [
                "".join(c for c in conjunto if c not in AMBIGUOS) for conjunto in conjuntos
            ]
        return tuple(conjuntos)


def gerar_senha(config: ConfigSenha) -> str:
    """Gera uma senha com CSPRNG (módulo `secrets`).

    Lógica:
      1. Sorteia 1 caractere de cada conjunto ativo → garante todas as classes.
      2. Completa o restante sorteando do pool total.
      3. Embaralha com SystemRandom → os obrigatórios não ficam no início.
    """
    alfabetos = config.alfabetos()
    pool = "".join(alfabetos)

    caracteres = [secrets.choice(alfabeto) for alfabeto in alfabetos]
    caracteres += [secrets.choice(pool) for _ in range(config.tamanho - len(caracteres))]
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


def entropia_bits(config: ConfigSenha) -> float:
    """Estimativa de entropia: tamanho × log2(tamanho do pool).

    É um limite superior: a exigência de ao menos um caractere por classe
    reduz levemente o espaço real de possibilidades.
    """
    pool = sum(len(alfabeto) for alfabeto in config.alfabetos())
    return config.tamanho * math.log2(pool)


def classificar_forca(bits: float) -> Forca:
    """Converte entropia (bits) em nível de força."""
    for limite, nivel in _FAIXAS_FORCA:
        if bits < limite:
            return nivel
    return Forca.MUITO_FORTE


def fracao_barra(bits: float) -> float:
    """Entropia normalizada para 0.0–1.0, para barras de progresso."""
    return max(0.0, min(1.0, bits / ENTROPIA_TETO_BARRA))


def tipo_caractere(caractere: str) -> str:
    """Classifica um caractere para colorir a senha: letra, numero ou simbolo."""
    if caractere.isalpha():
        return "letra"
    if caractere.isdigit():
        return "numero"
    return "simbolo"
