# Building & distributing the Android app

We build a signed **APK locally** (no Expo cloud) and **self-host it** on the
Caddy server for sideloading. Distributed builds talk to the **production API**
(`https://puriy.sofietorch.dev/api`), which is baked in via the `eas.json`
`preview` profile's `API_BASE_URL`.

## Prerequisites (one-time)

- **JDK 17** — the Android Gradle Plugin does not support newer JDKs. Check
  with `java -version`; if it's not 17, install Temurin 17 and point `JAVA_HOME`
  at it for builds.
- **Android SDK** — install via Android Studio or the command-line tools, then
  export `ANDROID_HOME` (and add `platform-tools` to `PATH`).
- **eas-cli** (for the recommended local path): `npm i -g eas-cli`.

## Signing keystore (one-time)

Generate a release keystore and keep it **out of git** (already gitignored):

```bash
cd app
mkdir -p credentials
keytool -genkeypair -v \
  -keystore credentials/release.keystore \
  -alias puriy -keyalg RSA -keysize 2048 -validity 10000
```

Then copy the template and fill in the passwords you chose:

```bash
cp credentials.json.example credentials.json
# edit credentials.json → keystorePassword / keyPassword
```

> Back up `credentials/release.keystore` somewhere safe. If you lose it you
> can't ship an update that installs over an already-distributed APK — users
> would have to uninstall first.

## Build the APK

### Recommended: `eas build --local`

Runs the whole build on your machine (no upload), reads `eas.json` +
`credentials.json`:

```bash
cd app
eas build -p android --profile preview --local
```

Output: an `*.apk` in `app/` (path printed at the end).

### Fallback: prebuild + Gradle (no eas-cli)

```bash
cd app
export API_BASE_URL=https://puriy.sofietorch.dev/api   # baked into the JS bundle
npx expo prebuild -p android --clean
cd android && ./gradlew assembleRelease
# → android/app/build/outputs/apk/release/app-release.apk
```

(For Gradle signing, wire `credentials/release.keystore` into
`android/app/build.gradle` signingConfigs, or use the eas path above which
handles it for you.)

## Host it

Copy the APK to the Caddy host's download dir and share the link:

```bash
scp ./*.apk user@server:/srv/downloads/puriy.apk
# → https://puriy.sofietorch.dev/download/puriy.apk
```

Users open the link, allow "install unknown apps" once, and install. HTTPS is
required (Android blocks cleartext); the server already serves HTTPS via Caddy.

## Versioning

Bump `version` in `app.config.ts` for each public build. Android also needs a
monotonically increasing `versionCode`; with `appVersionSource: "local"` set it
under `android.versionCode` in `app.config.ts` and increment it every release,
otherwise a newer APK won't install over an older one.

## Updates without a rebuild (optional)

JS/asset-only changes can later ship over-the-air with **EAS Update**
(`expo-updates`), so testers don't re-download the APK. Native changes (new
permissions, SDK bumps) still require a fresh APK.
