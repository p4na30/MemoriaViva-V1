/** @type {import('@capacitor/cli').CapacitorConfig} */
const config = {
  appId: "org.memoriaviva.rise",
  appName: "MemoriaViva RISE",
  webDir: "dist",
  server: {
    androidScheme: "https",
    cleartext: false,
  },
  android: {
    allowMixedContent: false,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
};

export default config;
