#!/usr/bin/env bash
set -euo pipefail

# Caça à Arte Scout Linux installer
# Installs into a separate directory and does not modify the original project.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/scout"
INSTALL_DIR="$HOME/CacaArteScoutLinux"
DATA_DIR="$INSTALL_DIR/data"
VENV_DIR="$INSTALL_DIR/.venv"
DESKTOP_DIR="$HOME/.local/share/applications"

if [[ ! -f "$SOURCE_DIR/Caca_Arte_Scout.py" ]]; then
  echo "Erro: nao encontrei a pasta scout ao lado de linux_install."
  echo "Execute este instalador a partir do pacote completo do projecto."
  exit 1
fi

echo "Instalacao separada em: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$DESKTOP_DIR"

# Copy source files without touching the original project. Preserve installed data.
rsync -a --exclude 'data/*' "$SOURCE_DIR/" "$INSTALL_DIR/"
mkdir -p "$DATA_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 nao encontrado. Instale Python 3 antes de continuar."
  exit 1
fi

if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
  echo "A preparar dependencias de sistema (pode pedir a palavra-passe)..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip rsync
  else
    echo "Instale python3-venv e rsync na sua distribuicao e repita."
    exit 1
  fi
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

cat > "$INSTALL_DIR/abrir_caca_arte_scout.sh" <<'LAUNCH'
#!/usr/bin/env bash
set -e
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"
"$BASE/.venv/bin/python" "$BASE/Caca_Arte_Scout.py" &
PID=$!
sleep 2
xdg-open "http://127.0.0.1:8766" >/dev/null 2>&1 || true
wait "$PID"
LAUNCH
chmod +x "$INSTALL_DIR/abrir_caca_arte_scout.sh"

cat > "$DESKTOP_DIR/caca-arte-scout.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Caca Arte Scout
Comment=Pesquisa de arte, livros e usados
Exec=$INSTALL_DIR/abrir_caca_arte_scout.sh
Terminal=false
Categories=Utility;
EOF
chmod +x "$DESKTOP_DIR/caca-arte-scout.desktop"

echo
echo "Instalacao concluida."
echo "Atalho criado no menu de aplicacoes."
echo "Pasta independente: $INSTALL_DIR"
echo "Para abrir: $INSTALL_DIR/abrir_caca_arte_scout.sh"
