"""Ponto de entrada: `python -m gerador_senhas` (GUI) ou `--cli` (terminal)."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, core, tema


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gerador-senhas",
        description="Gerador de senhas com interface integrada ao tema do Omarchy.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verboso", action="store_true", help="mostra logs e detalhes")
    parser.add_argument("--tema-info", action="store_true", help="mostra o tema detectado e sai")

    cli = parser.add_argument_group("modo terminal (use com --cli)")
    cli.add_argument("--cli", action="store_true", help="gera no terminal, sem interface gráfica")
    cli.add_argument("-t", "--tamanho", type=int, default=core.TAMANHO_PADRAO)
    cli.add_argument("-n", "--quantidade", type=int, default=1)
    cli.add_argument("--sem-maiusculas", action="store_true")
    cli.add_argument("--sem-numeros", action="store_true")
    cli.add_argument("--sem-simbolos", action="store_true")
    cli.add_argument("--permitir-ambiguos", action="store_true")
    return parser


def _mostrar_tema() -> int:
    p = tema.detectar_paleta()
    print(f"nome:     {p.nome}")
    print(f"origem:   {p.origem}")
    print(f"modo:     {'escuro' if p.escuro else 'claro'}")
    for campo in ("fundo", "texto", "destaque", "verde", "amarelo", "vermelho"):
        print(f"{campo + ':':<9} {getattr(p, campo)}")
    return 0


def _modo_cli(args: argparse.Namespace) -> int:
    if args.quantidade < 1:
        print("erro: --quantidade deve ser >= 1", file=sys.stderr)
        return 2
    try:
        config = core.ConfigSenha(
            tamanho=args.tamanho,
            maiusculas=not args.sem_maiusculas,
            numeros=not args.sem_numeros,
            simbolos=not args.sem_simbolos,
            evitar_ambiguos=not args.permitir_ambiguos,
        )
    except ValueError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2

    for _ in range(args.quantidade):
        print(core.gerar_senha(config))  # stdout limpo: seguro para pipes

    if args.verboso:
        bits = core.entropia_bits(config)
        print(f"# {core.classificar_forca(bits).value} (~{bits:.0f} bits)", file=sys.stderr)
    return 0


def _modo_grafico() -> int:
    try:
        from .app import executar  # import tardio: a CLI funciona sem GTK
    except (ImportError, ValueError) as erro:
        print(
            "erro: GTK4/libadwaita (PyGObject) não encontrados.\n"
            "  sudo pacman -S --needed python-gobject gtk4 libadwaita\n"
            f"detalhe: {erro}",
            file=sys.stderr,
        )
        return 1
    return executar()


def main(argv: list[str] | None = None) -> int:
    args = _criar_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.tema_info:
        return _mostrar_tema()
    if args.cli:
        return _modo_cli(args)
    return _modo_grafico()


if __name__ == "__main__":
    raise SystemExit(main())
