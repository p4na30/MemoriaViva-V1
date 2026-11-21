import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Hand,
  Image as ImageIcon,
  Loader2,
  Lock,
  MessageCircleHeart,
  Mic,
  MicOff,
  Radio,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { api, apiUrl } from "../api/client";
import type { AlbumPhoto, AppState, TurnResponse } from "../types";
import { useToast } from "./ToastProvider";

interface Props {
  state: AppState;
  onStateChange: (state: AppState) => void;
  onUnlocked: (state: AppState) => void;
}

type VoiceMode = "auto_vad" | "hold_ptt";

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
}
interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

const THEME_LABELS: Record<string, string> = {
  ferrocarril: "Recuerdo · Ferrocarril",
  musica_boleros: "Recuerdo · Boleros y Música",
  playa_manzanillo: "Recuerdo · Playa Manzanillo",
  familia_hogar: "Recuerdo · Familia y Hogar",
  mascotas: "Recuerdo · Mascotas",
};

export const ElderKioskView: React.FC<Props> = ({ state, onStateChange, onUnlocked }) => {
  const { notify } = useToast();
  const photos = state.photos;
  const elderName = state.profile.paciente.nombre_preferido || "Don Manuel";
  const rotationSec = state.account.rotation_interval_sec || 8;
  const vadSilenceMs = Math.round((state.silence_threshold_sec || 3.8) * 1000);

  const [photoIdx, setPhotoIdx] = useState(0);
  const [previousPhoto, setPreviousPhoto] = useState<AlbumPhoto | null>(null);
  const [activePhotoVisible, setActivePhotoVisible] = useState(true);
  const [anchoredBadge, setAnchoredBadge] = useState<string | null>(null);
  const [clockNow, setClockNow] = useState(new Date());

  // Conversation & Audio state
  const [voiceMode, setVoiceMode] = useState<VoiceMode>("auto_vad");
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [replyText, setReplyText] = useState(
    `Hola ${elderName}, qué gusto acompañarlo hoy. Cuando guste platicar sobre sus fotos o recuerdos, toque el botón para hablar.`
  );
  const [lastAudioUri, setLastAudioUri] = useState<string | null>(null);
  const [learnedChip, setLearnedChip] = useState<string | null>(null);
  const [familyBanner, setFamilyBanner] = useState<string | null>(null);
  const [emergencyActive, setEmergencyActive] = useState(false);

  // PIN unlock modal
  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [pinInput, setPinInput] = useState("");
  const [pinBusy, setPinBusy] = useState(false);

  // Discreet Demo Fail-Safe Drawer (only in demo profile)
  const [demoBarOpen, setDemoBarOpen] = useState(false);

  // Refs for MediaRecorder, VAD, and SpeechRecognition
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const speechRecRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef("");
  const vadTimerRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const listeningRef = useRef(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const currentPhoto: AlbumPhoto | undefined = photos[photoIdx % Math.max(1, photos.length)];
  const lastPhotoRef = useRef<AlbumPhoto | undefined>(currentPhoto);

  // True dual-layer crossfade without dark flashes when switching postcards
  useEffect(() => {
    if (!currentPhoto) return;
    if (lastPhotoRef.current && lastPhotoRef.current.filename !== currentPhoto.filename) {
      setPreviousPhoto(lastPhotoRef.current);
      setActivePhotoVisible(false);
      const rafId = window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => setActivePhotoVisible(true));
      });
      const clearId = window.setTimeout(() => setPreviousPhoto(null), 750);
      lastPhotoRef.current = currentPhoto;
      return () => {
        window.cancelAnimationFrame(rafId);
        window.clearTimeout(clearId);
      };
    }
    lastPhotoRef.current = currentPhoto;
  }, [currentPhoto]);

  // Clock ticker
  useEffect(() => {
    const id = window.setInterval(() => setClockNow(new Date()), 15000);
    return () => window.clearInterval(id);
  }, []);

  // Automatic gentle screensaver rotation (paused while speaking/processing)
  useEffect(() => {
    if (photos.length <= 1 || isListening || isProcessing || pinModalOpen) return;
    const id = window.setInterval(() => {
      setPhotoIdx((prev) => (prev + 1) % photos.length);
      setAnchoredBadge(null);
    }, rotationSec * 1000);
    return () => window.clearInterval(id);
  }, [photos.length, rotationSec, isListening, isProcessing, pinModalOpen]);

  // Live listening elapsed timer
  useEffect(() => {
    if (!isListening) {
      setElapsedSec(0);
      return;
    }
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsedSec(Number(((Date.now() - start) / 1000).toFixed(1)));
    }, 100);
    return () => window.clearInterval(id);
  }, [isListening]);

  const playAudioUri = useCallback((uri?: string | null) => {
    if (!uri) return;
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      const audio = new Audio(uri);
      audioPlayerRef.current = audio;
      audio.play().catch(() => {
        // Browser autoplay policy fallback; replay button remains available
      });
    } catch {
      // ignore playback issues
    }
  }, []);

  const applyTurnResult = useCallback(
    (res: TurnResponse) => {
      setFamilyBanner(null);
      setReplyText(res.assistant_reply);
      setLastAudioUri(res.audio_data_uri || null);
      setEmergencyActive(Boolean(res.emergency_triggered));

      if (res.learned_facts && res.learned_facts.length > 0) {
        setLearnedChip(res.learned_facts[0]);
      } else {
        setLearnedChip(null);
      }

      // Bidirectional Visual Anchoring: Voice -> Photo smooth crossfade
      if (res.matched_photo && photos.length > 0) {
        const targetIdx = photos.findIndex((p) => p.filename === res.matched_photo?.filename);
        if (targetIdx >= 0) {
          setPhotoIdx(targetIdx);
          setAnchoredBadge(THEME_LABELS[res.memory_album_theme] || "Recuerdo evocado");
        }
      }

      if (res.state) {
        onStateChange(res.state);
      }

      if (res.emergency_triggered) {
        notify("Contención de Naomi Feil activada + Alerta Roja S.O.S. enviada a Telegram.", "error");
      } else if (res.learned_facts && res.learned_facts.length > 0) {
        notify(`Memoria viva actualizada: "${res.learned_facts[0]}"`, "success");
      }

      playAudioUri(res.audio_data_uri);
    },
    [photos, onStateChange, notify, playAudioUri]
  );

  const blobToBase64 = (blob: Blob): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result || ""));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

  const cleanupCaptureResources = useCallback(() => {
    if (vadTimerRef.current) {
      window.clearInterval(vadTimerRef.current);
      vadTimerRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (speechRecRef.current) {
      try {
        speechRecRef.current.stop();
      } catch {
        // ignore
      }
      speechRecRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const stopListeningAndSubmit = useCallback(async () => {
    if (!listeningRef.current) return;
    listeningRef.current = false;
    setIsListening(false);
    setIsProcessing(true);

    const recorder = mediaRecorderRef.current;
    const stopPromise = new Promise<Blob | null>((resolve) => {
      if (!recorder || recorder.state === "inactive") {
        const fallbackBlob =
          chunksRef.current.length > 0 ? new Blob(chunksRef.current, { type: "audio/webm" }) : null;
        resolve(fallbackBlob);
        return;
      }
      recorder.onstop = () => {
        const mime = recorder.mimeType || "audio/webm";
        const blob = chunksRef.current.length > 0 ? new Blob(chunksRef.current, { type: mime }) : null;
        resolve(blob);
      };
      try {
        if (recorder.state === "recording") {
          recorder.requestData();
        }
        recorder.stop();
      } catch {
        const fallbackBlob =
          chunksRef.current.length > 0 ? new Blob(chunksRef.current, { type: "audio/webm" }) : null;
        resolve(fallbackBlob);
      }
    });

    const audioBlob = await stopPromise;
    const finalTranscript = transcriptRef.current.trim();
    cleanupCaptureResources();

    try {
      const audioBase64 = audioBlob && audioBlob.size > 150 ? await blobToBase64(audioBlob) : undefined;
      if (!audioBase64 && !finalTranscript) {
        notify("No se escuchó voz. Intenta hablar más cerca del micrófono o mantén presionado el botón.", "info");
        return;
      }
      const res = await api.submitTurn({
        audio_base64: audioBase64,
        audio_mime: audioBlob?.type,
        browser_transcript: finalTranscript || undefined,
        current_photo_filename: currentPhoto?.filename,
      });
      applyTurnResult(res);
    } catch (err) {
      notify(err instanceof Error ? err.message : "No se pudo procesar el turno de voz.", "error");
    } finally {
      setIsProcessing(false);
      setLiveTranscript("");
      transcriptRef.current = "";
    }
  }, [cleanupCaptureResources, currentPhoto?.filename, applyTurnResult, notify]);

  const startListening = useCallback(async () => {
    if (listeningRef.current || isProcessing || pinModalOpen) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      transcriptRef.current = "";
      setLiveTranscript("");
      setFamilyBanner(null);
      setEmergencyActive(false);

      const mimeCandidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ];
      const preferredMime =
        typeof MediaRecorder.isTypeSupported === "function"
          ? mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m)) || ""
          : "";

      const recorder = preferredMime
        ? new MediaRecorder(stream, { mimeType: preferredMime })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start(200);

      // Optional live transcript preview via Web SpeechRecognition (es-MX)
      const SpeechRecCtor =
        (window as unknown as Record<string, new () => SpeechRecognitionLike>).SpeechRecognition ||
        (window as unknown as Record<string, new () => SpeechRecognitionLike>).webkitSpeechRecognition;
      if (SpeechRecCtor) {
        try {
          const rec = new SpeechRecCtor();
          rec.lang = "es-MX";
          rec.continuous = true;
          rec.interimResults = true;
          rec.onresult = (ev) => {
            let combined = "";
            for (let i = 0; i < ev.results.length; i++) {
              combined += ev.results[i][0].transcript + " ";
            }
            const clean = combined.trim();
            if (clean) {
              transcriptRef.current = clean;
              setLiveTranscript(clean);
            }
          };
          rec.onerror = () => {};
          rec.start();
          speechRecRef.current = rec;
        } catch {
          // Graceful fallback to backend RAM STT (Gemini / SpeechRecognition es-MX)
        }
      }

      listeningRef.current = true;
      setIsListening(true);

      // Auto-VAD 3.8s inclusive silence detector for single-tap mode
      if (voiceMode === "auto_vad") {
        try {
          const AudioCtx =
            window.AudioContext ||
            (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          const ctx = new AudioCtx();
          audioCtxRef.current = ctx;
          if (ctx.state === "suspended") {
            await ctx.resume();
          }
          const src = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 1024;
          src.connect(analyser);
          const data = new Uint8Array(analyser.fftSize);
          let hasSpoken = false;
          let lastVoiceAt = Date.now();
          const startedAt = Date.now();
          let noiseFloor = 0.012;
          let noiseSamples = 0;

          vadTimerRef.current = window.setInterval(() => {
            if (!listeningRef.current) return;
            analyser.getByteTimeDomainData(data);
            // Compute DC-offset-free RMS energy
            let mean = 0;
            for (let i = 0; i < data.length; i++) {
              mean += (data[i] - 128) / 128;
            }
            mean /= data.length;
            let sum = 0;
            for (let i = 0; i < data.length; i++) {
              const v = (data[i] - 128) / 128 - mean;
              sum += v * v;
            }
            const rms = Math.sqrt(sum / data.length);
            const totalElapsed = Date.now() - startedAt;

            if (!hasSpoken && noiseSamples < 3 && rms < 0.03) {
              noiseFloor = (noiseFloor * noiseSamples + rms) / (noiseSamples + 1);
              noiseSamples += 1;
            }
            const adaptiveThreshold = Math.max(0.014, Math.min(0.045, noiseFloor * 1.9));

            if (rms > adaptiveThreshold || transcriptRef.current.length > 0) {
              if (!hasSpoken) {
                hasSpoken = true;
              }
              if (rms > adaptiveThreshold) {
                lastVoiceAt = Date.now();
              }
            }
            const silenceElapsed = Date.now() - lastVoiceAt;
            if ((hasSpoken && silenceElapsed >= vadSilenceMs) || totalElapsed >= 18000) {
              stopListeningAndSubmit();
            }
          }, 120);
        } catch {
          // If AudioContext unavailable, user can tap Stop manually
        }
      }
    } catch {
      notify(
        "No se pudo acceder al micrófono. Puedes usar los actos Fail-Safe Demo (teclas 1, 2, 3) o habilitar permisos.",
        "error"
      );
    }
  }, [isProcessing, pinModalOpen, voiceMode, vadSilenceMs, stopListeningAndSubmit, notify]);

  const handleRunDemoAct = useCallback(
    async (scenarioId: string) => {
      if (isProcessing || isListening) return;
      setIsProcessing(true);
      try {
        const res = await api.submitTurn({
          demo_scenario_id: scenarioId,
          current_photo_filename: currentPhoto?.filename,
        });
        applyTurnResult(res);
      } catch (err) {
        notify(err instanceof Error ? err.message : "Error al ejecutar escenario demo.", "error");
      } finally {
        setIsProcessing(false);
      }
    },
    [isProcessing, isListening, currentPhoto?.filename, applyTurnResult, notify]
  );

  const handleTalkAboutPhoto = async () => {
    if (!currentPhoto || isProcessing || isListening) return;
    setFamilyBanner(null);
    setIsProcessing(true);
    try {
      const res = await api.submitTurn({
        photo_filename: currentPhoto.filename,
      });
      setReplyText(res.assistant_reply);
      setLastAudioUri(res.audio_data_uri || null);
      setAnchoredBadge(THEME_LABELS[currentPhoto.theme] || currentPhoto.title);
      playAudioUri(res.audio_data_uri);
      notify(`Iniciando reminiscencia sobre "${currentPhoto.title}".`, "info");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al iniciar charla sobre la foto.", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleConsentGreeting = async () => {
    if (isProcessing) return;
    setIsProcessing(true);
    try {
      const res = await api.consentGreeting();
      setReplyText(res.greeting_text);
      setLastAudioUri(res.audio_data_uri || null);
      playAudioUri(res.audio_data_uri);
      notify("Bienvenida de Consentimiento Dual registrada en SQLite.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "No se pudo reproducir la bienvenida.", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  // Keyboard shortcuts: SPACE (Hold-to-Talk) + 1/2/3 (Discreet Demo Fail-Safe)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (pinModalOpen) return;
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        if (voiceMode === "hold_ptt") {
          startListening();
        } else if (listeningRef.current) {
          stopListeningAndSubmit();
        } else {
          startListening();
        }
      } else if (state.account.is_demo_mode && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === "1") handleRunDemoAct("demo_1_rescate");
        if (e.key === "2") handleRunDemoAct("demo_2_anomia");
        if (e.key === "3") handleRunDemoAct("demo_3_crisis");
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (pinModalOpen) return;
      if (e.code === "Space" && voiceMode === "hold_ptt" && listeningRef.current) {
        e.preventDefault();
        stopListeningAndSubmit();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [pinModalOpen, voiceMode, state.account.is_demo_mode, startListening, stopListeningAndSubmit, handleRunDemoAct]);

  useEffect(() => () => cleanupCaptureResources(), [cleanupCaptureResources]);

  // Bidirectional Family Bridge (Telegram -> Elder Kiosk): poll every 4s for inbound text/photos
  useEffect(() => {
    if (isListening || isProcessing || pinModalOpen) return;
    const id = window.setInterval(async () => {
      try {
        const res = await api.getKioskInbound();
        if (!res.messages || res.messages.length === 0) return;
        const msg = res.messages[0];
        await api.ackKioskInbound(msg.id);

        setReplyText(msg.text_content);
        setLastAudioUri(msg.audio_data_uri || null);
        setFamilyBanner(`Mensaje familiar de ${msg.sender_name} (Telegram)`);
        setEmergencyActive(false);

        if (msg.message_type === "photo" && msg.photo_filename) {
          const fresh = await api.getState();
          onStateChange(fresh);
          const idx = fresh.photos.findIndex((p) => p.filename === msg.photo_filename);
          if (idx >= 0) {
            setPhotoIdx(idx);
            setAnchoredBadge(`Foto nueva de ${msg.sender_name}`);
          }
        }
        playAudioUri(msg.audio_data_uri);
      } catch {
        // silent poll retry
      }
    }, 4000);
    return () => window.clearInterval(id);
  }, [isListening, isProcessing, pinModalOpen, onStateChange, playAudioUri]);

  const handleUnlockPin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pinInput.trim()) return;
    setPinBusy(true);
    try {
      const res = await api.verifyPin(pinInput.trim());
      setPinModalOpen(false);
      setPinInput("");
      onUnlocked(res.state);
    } catch (err) {
      notify(err instanceof Error ? err.message : "PIN incorrecto.", "error");
    } finally {
      setPinBusy(false);
    }
  };

  const timeFormatted = clockNow.toLocaleTimeString("es-MX", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const dayFormatted = clockNow.toLocaleDateString("es-MX", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-slate-950 text-white select-none">
      {/* Fullscreen Family Photo Frame (True Dual-Layer Crossfade) */}
      {currentPhoto ? (
        <>
          {previousPhoto && (
            <img
              src={apiUrl(previousPhoto.url)}
              alt={previousPhoto.title}
              className="absolute inset-0 w-full h-full object-cover opacity-100"
            />
          )}
          <img
            key={currentPhoto.filename}
            src={apiUrl(currentPhoto.url)}
            alt={currentPhoto.title}
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-700 ease-out ${
              activePhotoVisible ? "opacity-100" : "opacity-0"
            }`}
          />
        </>
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-cyan-950" />
      )}

      {/* Cinematic Top & Bottom Legibility Vignette */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/65 via-transparent to-slate-950/85 pointer-events-none" />

      {/* Discreet Top Bar */}
      <header className="relative z-20 flex items-start justify-between px-6 pt-5 pb-3">
        <div>
          <div className="text-4xl sm:text-5xl font-semibold tracking-tight tabular-nums leading-none drop-shadow">
            {timeFormatted}
          </div>
          <p className="text-sm sm:text-base text-slate-200 capitalize mt-1 drop-shadow">
            {dayFormatted} · Compañero de {elderName}
          </p>
          {currentPhoto && (
            <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-950/55 backdrop-blur-md border border-white/15 text-xs text-slate-100">
              <ImageIcon className="w-3.5 h-3.5 text-cyan-300" />
              <span>{currentPhoto.title}</span>
              {anchoredBadge && (
                <span className="px-2 py-0.5 rounded-full bg-cyan-500/25 text-cyan-200 font-medium">
                  {anchoredBadge}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          {photos.length > 0 && (
            <span className="px-3 py-1.5 rounded-full bg-slate-950/55 backdrop-blur-md border border-white/15 text-xs font-medium tabular-nums">
              {(photoIdx % photos.length) + 1} / {photos.length}
            </span>
          )}

          {/* Assisted Dual Consent Warm Greeting Button */}
          <button
            type="button"
            onClick={handleConsentGreeting}
            title="Bienvenida y transparencia de privacidad"
            className="w-10 h-10 rounded-full bg-slate-950/55 hover:bg-slate-900/80 backdrop-blur-md border border-white/20 flex items-center justify-center transition"
            aria-label="Escuchar bienvenida de privacidad"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-300" />
          </button>

          {/* Discreet Caregiver Lock Button */}
          <button
            type="button"
            onClick={() => setPinModalOpen(true)}
            title="Acceso al Panel Familiar (PIN)"
            className="w-10 h-10 rounded-full bg-slate-950/55 hover:bg-slate-900/80 backdrop-blur-md border border-white/20 flex items-center justify-center transition"
            aria-label="Desbloquear Panel Familiar"
          >
            <Lock className="w-4 h-4 text-slate-100" />
          </button>
        </div>
      </header>

      {/* Emotional Breathing Aura Overlay while listening or processing */}
      {(isListening || isProcessing) && (
        <div className="absolute inset-0 z-30 bg-slate-950/75 backdrop-blur-md flex flex-col items-center justify-center px-6 text-center gap-6">
          <div className="w-40 h-40 sm:w-48 sm:h-48 rounded-full aura-orb flex items-center justify-center">
            {isProcessing ? (
              <Loader2 className="w-12 h-12 text-white animate-spin" />
            ) : (
              <Mic className="w-12 h-12 text-white" />
            )}
          </div>

          <div className="space-y-2 max-w-xl">
            <p className="text-xl sm:text-2xl font-semibold">
              {isProcessing
                ? "Pensando una respuesta cálida..."
                : `Te escucho con calma, ${elderName}`}
            </p>
            {isListening && (
              <p className="text-sm text-cyan-200 tabular-nums">
                {voiceMode === "auto_vad"
                  ? `Escucha continua (${elapsedSec.toFixed(1)}s) · Cierra automáticamente tras ${state.silence_threshold_sec}s de silencio`
                  : `Mantén presionado para hablar (${elapsedSec.toFixed(1)}s) · Suelta al terminar`}
              </p>
            )}
            {liveTranscript && (
              <p className="mt-3 px-4 py-2.5 rounded-xl bg-white/10 text-base text-slate-100 leading-relaxed">
                “{liveTranscript}”
              </p>
            )}
          </div>

          {isListening && (
            <button
              type="button"
              onClick={stopListeningAndSubmit}
              className="px-6 py-3 rounded-full bg-white text-slate-900 font-semibold text-sm flex items-center gap-2 hover:bg-slate-100 transition"
            >
              <Square className="w-4 h-4 fill-current" />
              Terminar y responder ahora
            </button>
          )}
        </div>
      )}

      {/* Minimal Translucent Bottom Dock */}
      <footer className="absolute bottom-0 inset-x-0 z-20 p-5 sm:p-7 flex flex-col items-center gap-3">
        <div className="w-full max-w-3xl rounded-2xl bg-slate-950/70 backdrop-blur-md border border-white/15 p-5 shadow-2xl space-y-4">
          {/* Emergency Contention Banner */}
          {emergencyActive && (
            <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-red-500/20 border border-red-400/40 text-red-100 text-xs sm:text-sm font-medium">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-300" />
              Protocolo de Validación de Naomi Feil activo · Aviso S.O.S. enviado a {state.account.caregiver_name}.
            </div>
          )}

          {/* Bidirectional Family Inbound Message Banner */}
          {familyBanner && !emergencyActive && (
            <div className="flex items-center justify-between gap-2 px-3.5 py-2 rounded-xl bg-cyan-500/20 border border-cyan-300/35 text-cyan-100 text-xs sm:text-sm font-medium">
              <span className="flex items-center gap-2">
                <MessageCircleHeart className="w-4 h-4 shrink-0 text-cyan-300" />
                {familyBanner}
              </span>
              <button
                type="button"
                onClick={() => setFamilyBanner(null)}
                className="opacity-70 hover:opacity-100"
                aria-label="Cerrar aviso familiar"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Companion Reply */}
          <div className="flex items-start justify-between gap-4">
            <p className="text-lg sm:text-2xl font-medium leading-snug text-white">
              {replyText}
            </p>
            {lastAudioUri && (
              <button
                type="button"
                onClick={() => playAudioUri(lastAudioUri)}
                className="shrink-0 w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition"
                title="Volver a escuchar respuesta"
                aria-label="Repetir audio"
              >
                <Volume2 className="w-5 h-5 text-cyan-200" />
              </button>
            )}
          </div>

          {/* Learned Fact Chip (Biographical RAG-Lite) */}
          {learnedChip && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-400/35 text-emerald-200 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Nuevo recuerdo guardado: {learnedChip}
            </div>
          )}

          {/* Voice Dual Mode Controls + Foto -> Voz Action */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2 flex-wrap">
              {/* Primary Inclusive Talk Button */}
              {voiceMode === "auto_vad" ? (
                <button
                  type="button"
                  disabled={isProcessing}
                  onClick={isListening ? stopListeningAndSubmit : startListening}
                  className="px-6 py-3.5 rounded-xl font-semibold text-base flex items-center gap-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition shadow-lg"
                >
                  {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  {isListening ? "Detener escucha" : "Tocar para platicar"}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={isProcessing}
                  onPointerDown={startListening}
                  onPointerUp={stopListeningAndSubmit}
                  onPointerCancel={stopListeningAndSubmit}
                  className="px-6 py-3.5 rounded-xl font-semibold text-base flex items-center gap-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition shadow-lg touch-none"
                >
                  <Hand className="w-5 h-5" />
                  Mantén presionado (o ESPACIO)
                </button>
              )}

              {/* Foto -> Voz Button */}
              {currentPhoto && (
                <button
                  type="button"
                  disabled={isProcessing || isListening}
                  onClick={handleTalkAboutPhoto}
                  className="px-4 py-3.5 rounded-xl font-medium text-sm flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/15 text-white transition"
                >
                  <MessageCircleHeart className="w-4 h-4 text-cyan-300" />
                  Platicar sobre esta foto
                </button>
              )}
            </div>

            {/* Dual Voice Mode Switcher */}
            <div className="inline-flex rounded-xl bg-white/10 p-1 text-xs">
              <button
                type="button"
                onClick={() => setVoiceMode("auto_vad")}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  voiceMode === "auto_vad" ? "bg-white text-slate-950" : "text-slate-200 hover:text-white"
                }`}
              >
                Toque simple (3.8s)
              </button>
              <button
                type="button"
                onClick={() => setVoiceMode("hold_ptt")}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  voiceMode === "hold_ptt" ? "bg-white text-slate-950" : "text-slate-200 hover:text-white"
                }`}
              >
                Mantener presionado
              </button>
            </div>
          </div>
        </div>
      </footer>

      {/* Discreet Fail-Safe Pitch Controls (only visible in Demo Mode) */}
      {state.account.is_demo_mode && (
        <div className="fixed bottom-4 left-4 z-30 flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setDemoBarOpen((v) => !v)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-950/60 hover:bg-slate-900/90 border border-white/15 text-[11px] font-medium text-slate-300 flex items-center gap-1.5 backdrop-blur-md"
            title="Disparadores Fail-Safe del Pitch (Atajos 1, 2, 3)"
          >
            <Radio className="w-3 h-3 text-cyan-400" />
            Demo
          </button>
          {demoBarOpen && (
            <div className="flex items-center gap-1.5 bg-slate-950/85 border border-white/15 rounded-lg p-1 backdrop-blur-md">
              <button
                type="button"
                disabled={isProcessing}
                onClick={() => handleRunDemoAct("demo_1_rescate")}
                className="px-2.5 py-1 rounded text-[11px] font-medium bg-emerald-500/20 hover:bg-emerald-500/35 text-emerald-200"
              >
                1 · Rescate
              </button>
              <button
                type="button"
                disabled={isProcessing}
                onClick={() => handleRunDemoAct("demo_2_anomia")}
                className="px-2.5 py-1 rounded text-[11px] font-medium bg-amber-500/20 hover:bg-amber-500/35 text-amber-200"
              >
                2 · Anomia 3.18s
              </button>
              <button
                type="button"
                disabled={isProcessing}
                onClick={() => handleRunDemoAct("demo_3_crisis")}
                className="px-2.5 py-1 rounded text-[11px] font-medium bg-red-500/25 hover:bg-red-500/40 text-red-200"
              >
                3 · Crisis S.O.S.
              </button>
            </div>
          )}
        </div>
      )}

      {/* Clean Caregiver PIN Unlock Modal */}
      {pinModalOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            className="clinical-card w-full max-w-sm p-6 space-y-4"
            style={{ color: "var(--text)" }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4" style={{ color: "var(--primary)" }} />
                <h2 className="text-base font-semibold">Acceso al Panel Familiar</h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPinModalOpen(false);
                  setPinInput("");
                }}
                className="p-1 opacity-70 hover:opacity-100"
                aria-label="Cerrar modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Ingresa el PIN del cuidador para consultar biomarcadores, gobernanza RISE y el reporte clínico PDF.
            </p>

            {state.account.is_demo_mode && (
              <div
                className="px-3 py-2 rounded-lg text-xs flex items-center gap-2"
                style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
              >
                <Sparkles className="w-3.5 h-3.5 shrink-0" />
                <span>
                  Modo Simulación activo · <strong>PIN demo: 1234</strong>
                </span>
              </div>
            )}

            <form onSubmit={handleUnlockPin} className="space-y-3">
              <input
                type="password"
                inputMode="numeric"
                autoFocus
                placeholder="PIN de 4+ dígitos"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                className="clinical-input text-center text-lg tracking-widest tabular-nums"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPinModalOpen(false);
                    setPinInput("");
                  }}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={pinBusy} className="btn-primary">
                  {pinBusy && <Loader2 className="w-4 h-4 animate-spin" />}
                  Desbloquear
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
