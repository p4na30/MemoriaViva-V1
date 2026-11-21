#!/usr/bin/env node
/**
 * Idempotent Capacitor 6 Android Kiosk Configurator for MemoriaViva RISE v3.0
 *
 * Injects:
 * 1. AndroidManifest.xml permissions: INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, WAKE_LOCK
 * 2. MainActivity.java: FLAG_KEEP_SCREEN_ON, immersive kiosk bars, runtime RECORD_AUDIO permission,
 *    and WebChromeClient.onPermissionRequest granting PermissionRequest.RESOURCE_AUDIO_CAPTURE
 * 3. android/app/build.gradle: optional Release signing config from environment variables
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(__dirname, "..");
const androidDir = path.join(frontendDir, "android");
const dryRun = process.argv.includes("--dry-run");

const REQUIRED_PERMISSIONS = [
  "android.permission.INTERNET",
  "android.permission.RECORD_AUDIO",
  "android.permission.MODIFY_AUDIO_SETTINGS",
  "android.permission.WAKE_LOCK",
];

function configureManifest(manifestPath) {
  let xml = fs.readFileSync(manifestPath, "utf-8");
  for (const perm of REQUIRED_PERMISSIONS) {
    const tag = `<uses-permission android:name="${perm}" />`;
    if (!xml.includes(perm)) {
      xml = xml.replace("<application", `    ${tag}\n\n    <application`);
    }
  }
  if (!xml.includes("android.hardware.microphone")) {
    xml = xml.replace(
      "<application",
      '    <uses-feature android:name="android.hardware.microphone" android:required="false" />\n\n    <application'
    );
  }
  if (!dryRun) fs.writeFileSync(manifestPath, xml, "utf-8");
  console.log("[configure-android] AndroidManifest.xml updated with audio & wake-lock permissions.");
}

function configureMainActivity(javaDir) {
  const target = path.join(javaDir, "org", "memoriaviva", "rise", "MainActivity.java");
  const content = `package org.memoriaviva.rise;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.PermissionRequest;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

public class MainActivity extends BridgeActivity {
    private static final int AUDIO_PERMISSION_CODE = 1001;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Keep tablet screen awake in Elder Kiosk Mode
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        // Request microphone permission at runtime
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(
                this,
                new String[]{Manifest.permission.RECORD_AUDIO},
                AUDIO_PERMISSION_CODE
            );
        }

        // Extend Capacitor's BridgeWebChromeClient so microphone + file uploads + JS dialogs all work
        if (this.bridge != null && this.bridge.getWebView() != null) {
            this.bridge.getWebView().setWebChromeClient(new BridgeWebChromeClient(this.bridge) {
                @Override
                public void onPermissionRequest(final PermissionRequest request) {
                    runOnUiThread(() -> request.grant(request.getResources()));
                }
            });
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            );
        }
    }
}
`;
  if (!dryRun) {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content, "utf-8");
  }
  console.log("[configure-android] MainActivity.java configured for Kiosk WakeLock + WebView audio.");
}

function configureGradleSigning(gradlePath) {
  let gradle = fs.readFileSync(gradlePath, "utf-8");
  if (gradle.includes("KEYSTORE_FILE")) {
    console.log("[configure-android] Gradle release signing block already present.");
    return;
  }

  const signingSnippet = `
    signingConfigs {
        release {
            if (System.getenv("KEYSTORE_FILE")) {
                storeFile file(System.getenv("KEYSTORE_FILE"))
                storePassword System.getenv("KEYSTORE_PASSWORD")
                keyAlias System.getenv("KEY_ALIAS")
                keyPassword System.getenv("KEY_PASSWORD")
            }
        }
    }
`;

  if (gradle.includes("buildTypes {")) {
    gradle = gradle.replace("buildTypes {", `${signingSnippet}\n    buildTypes {`);
    gradle = gradle.replace(
      /release\s*\{/,
      `release {\n            if (System.getenv("KEYSTORE_FILE")) { signingConfig signingConfigs.release }`
    );
    if (!dryRun) fs.writeFileSync(gradlePath, gradle, "utf-8");
    console.log("[configure-android] build.gradle updated with optional CI release signing.");
  }
}

function main() {
  if (dryRun && !fs.existsSync(androidDir)) {
    console.log("[configure-android] Dry-run syntax check OK (android/ not generated yet).");
    process.exit(0);
  }
  if (!fs.existsSync(androidDir)) {
    console.error("[configure-android] Error: frontend/android does not exist. Run 'npx cap add android' first.");
    process.exit(1);
  }

  configureManifest(path.join(androidDir, "app", "src", "main", "AndroidManifest.xml"));
  configureMainActivity(path.join(androidDir, "app", "src", "main", "java"));
  configureGradleSigning(path.join(androidDir, "app", "build.gradle"));
}

main();
