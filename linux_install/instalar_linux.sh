#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/scout"
INSTALL_DIR="$HOME/CacaArteScoutLinux"
DATA_DIR="$INSTALL_DIR/data"
VENV_DIR="$INSTALL_DIR/.venv"
DESKTOP_DIR="$HOME/.local/share/applications"

if [[ ! -f "$SOURCE_DIR/Caca_Arte_Scout.py" ]]; then
  echo "Erro: nao encontrei a pasta scout junto deste pacote."
  exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "A instalar componentes Python necessarios..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
  else
    echo "Instale python3-venv na sua distribuicao e repita."
    exit 1
  fi
fi

mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$DESKTOP_DIR"
cp -a "$SOURCE_DIR/." "$INSTALL_DIR/"
mkdir -p "$DATA_DIR"

python3 -m venv "$VENV_DIR"
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
echo "Instalacao concluida."
echo "Instalacao independente: $INSTALL_DIR"
echo "Atalho criado no menu de aplicacoes."
