#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
ADDONS="$ROOT/addons"
JAVA_HOME="${JAVA_HOME:-}"

if [[ -z "$JAVA_HOME" ]] && command -v brew >/dev/null 2>&1; then
  BREW_JDK="$(brew --prefix openjdk@21 2>/dev/null || true)"
  if [[ -n "$BREW_JDK" && -d "$BREW_JDK/libexec/openjdk.jdk/Contents/Home" ]]; then
    JAVA_HOME="$BREW_JDK/libexec/openjdk.jdk/Contents/Home"
  fi
fi

if [[ -n "$JAVA_HOME" ]]; then
  export JAVA_HOME
  export PATH="$JAVA_HOME/bin:$PATH"
fi

mkdir -p "$DIST"

if command -v java >/dev/null 2>&1; then
  echo "[build] screenshotbridge..."
  (cd "$ADDONS/labymod-screenshot-addon" && ./gradlew createReleaseJar --no-daemon -q)
  echo "[build] autologin..."
  (cd "$ADDONS/labymod-autologin-addon" && ./gradlew createReleaseJar --no-daemon -q)
  echo "[build] chatcopy..."
  (cd "$ADDONS/labymod-chatcopy-addon" && ./gradlew createReleaseJar --no-daemon -q)
else
  echo "[build] java не найдена — jar не пересобраны"
fi

echo "[build] moderator..."
rm -rf "$DIST/moderator"
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$ROOT/moderator/" "$DIST/moderator/"

echo "[build] моды..."
cp "$ADDONS/labymod-screenshot-addon/build/libs/screenshotbridge-release.jar" "$DIST/screenshotbridge.jar"
cp "$ADDONS/labymod-autologin-addon/build/libs/autologin-release.jar" "$DIST/autologin.jar"
cp "$ADDONS/labymod-chatcopy-addon/build/libs/chatcopy-release.jar" "$DIST/chatcopy.jar"

echo "[build] python..."
cp "$ROOT/main.py" "$DIST/main.py"
cp "$ROOT/requirements.txt" "$DIST/requirements.txt"
cp "$ROOT/scripts/startser.bat" "$DIST/startser.bat"

if [[ -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env" "$DIST/.env"
elif [[ -f "$ROOT/../.env" ]]; then
  cp "$ROOT/../.env" "$DIST/.env"
else
  echo "[build] предупреждение: .env не найден"
fi

if [[ -d "$ROOT/dashboard" ]] && command -v npm >/dev/null 2>&1; then
  echo "[build] dashboard..."
  if [[ ! -d "$ROOT/dashboard/node_modules" ]]; then
    (cd "$ROOT/dashboard" && npm install --silent)
  fi
  (cd "$ROOT/dashboard" && npm run build --silent)
  rm -rf "$DIST/dashboard_dist"
  rsync -a \
    --exclude '.DS_Store' \
    "$ROOT/dashboard_dist/" "$DIST/dashboard_dist/"
fi

rm -rf "$DIST/__pycache__"
find "$DIST" -name '.DS_Store' -delete

ZIP="$ROOT/dist.zip"
echo "[build] архив $ZIP..."
rm -f "$ZIP"
(
  cd "$DIST"
  zip -r -q "$ZIP" . \
    -x "**/__pycache__/*" \
    -x "**/*.pyc" \
    -x "**/.DS_Store" \
    -x ".DS_Store"
)

echo "[build] готово: $DIST"
ls -la "$DIST"/*.jar 2>/dev/null || true
ls -lh "$ZIP" | awk '{print "  zip:", $9, $5}'
