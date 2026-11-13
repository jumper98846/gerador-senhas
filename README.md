# Gerador de Senhas (Omarchy)

Gerador de senhas em GTK4 + libadwaita que adota automaticamente o tema ativo do Omarchy
e acompanha a troca de tema em tempo real.

## Instalação

```bash
sudo pacman -S --needed python-gobject gtk4 libadwaita
./install.sh
```

## Uso

| Modo     | Comando                                         |
| -------- | ----------------------------------------------- |
| Gráfico  | `gerador-senhas`                                |
| Terminal | `gerador-senhas --cli -t 24 -n 5 --sem-simbolos` |
| Diagnóstico do tema | `gerador-senhas --tema-info`         |

Atalhos: `Enter`/`Ctrl+G`/`F5` gera · `Ctrl+C` copia · `Esc`/`Ctrl+Q` sai.

## Segurança

- Geração com `secrets` (CSPRNG), nunca `random`.
- Senha copiada é marcada como sensível (`x-kde-passwordManagerHint`) e a área de
  transferência é limpa após 30 s ou ao fechar o app.

## Desenvolvimento

A GUI precisa do Python **do sistema** (onde o PyGObject está instalado). Se você usa
mise/pyenv, chame `/usr/bin/python` explicitamente:

```bash
sudo pacman -S --needed python-pytest
/usr/bin/python -m pytest
/usr/bin/python -m gerador_senhas -v
```

## Estrutura

| Arquivo                   | Responsabilidade                          |
| ------------------------- | ----------------------------------------- |
| `gerador_senhas/core.py`  | Geração, entropia e força (sem GUI)       |
| `gerador_senhas/tema.py`  | Leitura do tema Omarchy e geração de CSS  |
| `gerador_senhas/app.py`   | Interface GTK4/libadwaita                 |
| `gerador_senhas/__main__.py` | CLI e ponto de entrada                 |
| `data/local.GeradorSenhas.svg` | Ícone do aplicativo (SVG escalável)  |
| `tests/`                  | Testes automatizados                      |
