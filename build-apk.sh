#!/bin/bash
# Full Android SDK setup + APK build for Mandarin Tutor.
# Designed to run in the background (heavy downloads). Idempotent where possible.
set -o pipefail

export ANDROID_HOME="$HOME/Android/Sdk"
export ANDROID_SDK_ROOT="$HOME/Android/Sdk"
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# --- 1. cmdline-tools ---
SDKM="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [ ! -f "$SDKM" ]; then
  log "Downloading Android cmdline-tools…"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  cd /tmp
  curl -L --retry 3 --retry-delay 5 -o cmdtools.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" || { log "DOWNLOAD FAILED"; exit 1; }
  log "Download done ($(du -h cmdtools.zip | cut -f1)). Unzipping…"
  unzip -q -o cmdtools.zip -d "$ANDROID_HOME/cmdline-tools"
  rm -rf "$ANDROID_HOME/cmdline-tools/latest"
  mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi
[ -f "$SDKM" ] || { log "sdkmanager missing after setup"; exit 1; }
log "sdkmanager ready."

# --- 2. licenses + packages ---
log "Accepting licenses…"
yes | "$SDKM" --licenses >/dev/null 2>&1 || true
log "Installing platform-tools, android-34, build-tools 34.0.0…"
"$SDKM" "platform-tools" "platforms;android-34" "build-tools;34.0.0" 2>&1 | tail -5

# --- 3. build APK ---
cd "$HOME/projects/mandarin-tutor/android-app/android" || { log "android dir missing"; exit 1; }
echo "sdk.dir=$ANDROID_HOME" > local.properties
log "Running gradle assembleDebug (first build downloads gradle deps, be patient)…"
./gradlew assembleDebug --no-daemon 2>&1 | tail -25

APK="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK" ]; then
  log "BUILD DONE ✓"
  ls -lh "$APK"
  # copy to a stable, easy-to-find location
  cp "$APK" "$HOME/projects/mandarin-tutor/MandarinTutor.apk"
  log "APK copied to ~/projects/mandarin-tutor/MandarinTutor.apk"
else
  log "BUILD FAILED — apk not found"
  exit 1
fi
