#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$ROOT/dist"
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

if ! command -v java >/dev/null 2>&1; then
  echo "[build] java не найдена — установи JDK 21"
  exit 1
fi

mkdir -p "$OUT"

echo "[build] chatcopy..."
(cd "$ROOT" && ./gradlew createReleaseJar --no-daemon)

JAR="$ROOT/build/libs/chatcopy-release.jar"
if [[ ! -f "$JAR" ]]; then
  echo "[build] jar не найден: $JAR"
  exit 1
fi

cp "$JAR" "$OUT/chatcopy.jar"
echo "[build] готово: $OUT/chatcopy.jar"
ls -lh "$OUT/chatcopy.jar"
