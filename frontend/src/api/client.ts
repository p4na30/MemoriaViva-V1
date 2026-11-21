import type { AppState, InboundFamilyMessage, TelegramStatus, TurnResponse } from "../types";

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timerId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiUrl(path), {
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers || {}),
      },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `Error HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err?.detail) message = String(err.detail);
      } catch {
        // ignore parse failure
      }
      throw new Error(message);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al conectar con el servidor.");
    }
    throw err;
  } finally {
    window.clearTimeout(timerId);
  }
}

export const api = {
  getState: () => requestJson<AppState>("/api/state"),

  completeOnboarding: (payload: Record<string, unknown>) =>
    requestJson<{ ok: boolean; state: AppState }>("/api/onboarding/complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  verifyPin: (pin: string) =>
    requestJson<{ ok: boolean; unlocked: boolean; state: AppState }>("/api/auth/verify-pin", {
      method: "POST",
      body: JSON.stringify({ pin }),
    }),

  lockKiosk: () =>
    requestJson<{ ok: boolean; kiosk_locked: boolean }>("/api/kiosk/lock", {
      method: "POST",
    }),

  consentGreeting: () =>
    requestJson<{
      ok: boolean;
      greeting_text: string;
      audio_data_uri: string | null;
    }>("/api/kiosk/consent-greeting", { method: "POST" }),

  submitTurn: (payload: {
    audio_base64?: string;
    audio_mime?: string;
    browser_transcript?: string;
    browser_word_timestamps?: Array<{ word: string; start: number; end: number }>;
    demo_scenario_id?: string;
    custom_text?: string;
    photo_filename?: string;
    current_photo_filename?: string;
    skip_tts?: boolean;
  }) =>
    requestJson<TurnResponse>(
      "/api/turn",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      15000
    ),

  createReview: (payload: {
    reviewer_name: string;
    reviewer_role: string;
    decision: string;
    confounding_factors: string[];
    clinical_notes: string;
  }) =>
    requestJson<{ ok: boolean; state: AppState }>("/api/reviews", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadPhoto: (file: File, title: string, caption: string, theme: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title);
    fd.append("caption", caption);
    fd.append("theme", theme);
    return requestJson<{ ok: boolean; photos: AppState["photos"] }>("/api/photos", {
      method: "POST",
      body: fd,
    });
  },

  generateSamplePhotos: () =>
    requestJson<{ ok: boolean; photos: AppState["photos"]; count: number }>("/api/photos/sample", {
      method: "POST",
    }),

  deletePhoto: (filename: string) =>
    requestJson<{ ok: boolean; photos: AppState["photos"] }>(
      `/api/photos/${encodeURIComponent(filename)}`,
      { method: "DELETE" }
    ),

  updateProfile: (payload: Record<string, unknown>) =>
    requestJson<{ ok: boolean; state: AppState }>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  updateSettings: (payload: Record<string, unknown>) =>
    requestJson<{ ok: boolean; state: AppState }>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  getTelegramStatus: () =>
    requestJson<{ ok: boolean; telegram_status: TelegramStatus }>("/api/telegram/status"),

  regenerateTelegramUuid: () =>
    requestJson<{ ok: boolean; telegram_status: TelegramStatus; state: AppState }>(
      "/api/telegram/regenerate-uuid",
      { method: "POST" }
    ),

  verifyTelegram: () =>
    requestJson<{ ok: boolean; verification: Record<string, unknown> }>("/api/telegram/verify", {
      method: "POST",
    }),

  discoverTelegramChat: () =>
    requestJson<{ ok: boolean; result: { found: boolean; detail: string }; state: AppState }>(
      "/api/telegram/discover-chat",
      { method: "POST" }
    ),

  getKioskInbound: () =>
    requestJson<{ ok: boolean; messages: InboundFamilyMessage[] }>("/api/kiosk/inbound"),

  ackKioskInbound: (msgId: number) =>
    requestJson<{ ok: boolean; acked_id: number }>(`/api/kiosk/inbound/${msgId}/ack`, {
      method: "POST",
    }),

  sendLevel2Warning: () =>
    requestJson<{ ok: boolean; state: AppState }>("/api/telegram/level2-warning", {
      method: "POST",
    }),

  resetDemo: () =>
    requestJson<{ ok: boolean; message: string; state: AppState }>("/api/demo/reset", {
      method: "POST",
    }),

  resetSystem: () =>
    requestJson<{ ok: boolean; state: AppState }>("/api/system/reset", {
      method: "POST",
    }),

  reportPdfUrl: () => apiUrl(`/api/report/pdf?t=${Date.now()}`),
};
