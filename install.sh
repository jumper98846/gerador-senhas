#!/usr/bin/env bash
# Instala o Gerador de Senhas para o usuário atual (sem sudo).
#   ./install.sh            instala / atualiza
#   ./install.sh --remover  remove
set -euo pipefail

DADOS="${XDG_DATA_HOME:-$HOME/.local/share}"
DESTINO="$DADOS/gerador-senhas"
BIN="$HOME/.local/bin"
DESKTOP="$DADOS/applications/local.GeradorSenhas.desktop"
TEMAS_ICONES="$DADOS/icons/hicolor"
ICONE="$TEMAS_ICONES/scalable/apps/local.GeradorSenhas.svg"
ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--remover" ]]; then
  rm -rf "$DESTINO" "$BIN/gerador-senhas" "$DESKTOP" "$ICONE"
  echo "Removido."
  exit 0
fi

# 1) Dependências (PyGObject + GTK4 + libadwaita)
#    Usa SEMPRE o Python do sistema: o PyGObject do pacman não é visível a
#    pythons de gerenciadores de versão (mise, pyenv, asdf...).
if ! /usr/bin/python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null; then
  echo "Dependências ausentes. Instale com:" >&2
  echo "  sudo pacman -S --needed python-gobject gtk4 libadwaita" >&2
  exit 1
fi

# 2) Código
mkdir -p "$DESTINO" "$BIN" "$(dirname "$DESKTOP")" "$(dirname "$ICONE")"
rm -rf "$DESTINO/gerador_senhas"
cp -r "$ORIGEM/gerador_senhas" "$DESTINO/"
find "$DESTINO" -name '__pycache__' -prune -exec rm -rf {} +

# 3) Comando no PATH
cat > "$BIN/gerador-senhas" <<LAUNCHER
#!/usr/bin/env bash
exec env PYTHONPATH="$DESTINO" /usr/bin/python3 -m gerador_senhas "\$@"
LAUNCHER
chmod +x "$BIN/gerador-senhas"

# 4) Ícone (tema hicolor do usuário). O nome do arquivo = application_id.
install -m 644 "$ORIGEM/data/local.GeradorSenhas.svg" "$ICONE"
# Só atualiza o cache se ele já existir; um cache antigo esconderia o ícone novo.
if [[ -f "$TEMAS_ICONES/icon-theme.cache" ]]; then
  gtk-update-icon-cache -q -t -f "$TEMAS_ICONES" 2>/dev/null || true
fi

# 5) Entrada no menu (Walker/launcher). O nome do arquivo = application_id.
cat > "$DESKTOP" <<ENTRY
[Desktop Entry]
Type=Application
Name=Gerador de Senhas
Comment=Gera senhas seguras com o tema do Omarchy
Exec=$BIN/gerador-senhas
Icon=local.GeradorSenhas
Terminal=false
Categories=Utility;GTK;
StartupWMClass=local.GeradorSenhas
ENTRY
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

echo "Instalado. Execute: gerador-senhas   (ou procure 'Gerador de Senhas' no launcher)"
