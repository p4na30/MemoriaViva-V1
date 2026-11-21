export type ThemeMode = "light" | "dark";

export interface AccountConfig {
  is_registered: boolean;
  kiosk_locked: boolean;
  active_profile_id: string;
  is_demo_mode: boolean;
  caregiver_name: string;
  caregiver_username: string;
  rotation_interval_sec: number;
  theme_mode: ThemeMode;
  voice_gender: "male" | "female";
  telegram_link_code: string;
  telegram_chat_id: string;
  consent_caregiver_accepted: boolean;
  consent_caregiver_at: string | null;
  has_pin: boolean;
}

export interface PatientProfile {
  paciente: {
    id: string;
    tipo_perfil: string;
    nombre_completo: string;
    nombre_preferido: string;
    edad: number;
    ciudad_residencia: string;
    ocupacion_historica: string;
  };
  red_familiar_y_afectiva: {
    esposa_finada: string;
    hija_mayor_cuidadora: {
      nombre: string;
      ciudad: string;
      detalle: string;
    };
    hija_menor: {
      nombre: string;
      ciudad: string;
      ocupacion?: string;
      detalle: string;
    };
    nietos: Array<{
      nombre: string;
      edad: number;
      gusto_compartido: string;
    }>;
  };
  anclas_de_reminiscencia: string[];
  recuerdos_aprendidos: string[];
  rutinas_salud_suaves: string[];
  contacto_emergencia_telegram: {
    nombre: string;
    parentesco: string;
    chat_id: string;
  };
}

export interface LongitudinalDay {
  day_number: number;
  date_label: string;
  mattr: number;
  mean_pause: number;
  anomic_pauses: number;
  repetitions: number;
  mood: string;
  circadian_period: string;
  updated_at?: string;
}

export interface LongitudinalEvaluation {
  baseline_mattr_mean: number;
  baseline_mattr_std: number;
  recent_mattr_mean: number;
  latest_mattr: number;
  delta_mattr_pct: number;
  delta_mattr_pct_display: number;
  z_mattr: number;
  baseline_pause_mean: number;
  baseline_pause_std: number;
  recent_pause_mean: number;
  latest_pause: number;
  delta_pause_pct: number;
  delta_pause_pct_display: number;
  z_pause: number;
  vitality_score: number;
  level2_alert_triggered: boolean;
  alert_reasons: string[];
  circadian_summary: {
    matutino: number;
    vespertino_sundowning: number;
    nocturno: number;
  };
}

export interface AlbumPhoto {
  filename: string;
  url: string;
  title: string;
  caption: string;
  theme: string;
  is_sample: boolean;
}

export interface TelegramStatus {
  bot_configured: boolean;
  bot_username: string;
  link_uuid: string;
  link_code: string;
  status: "pending" | "paired";
  linked_user_name: string;
  deep_link: string;
  qr_base64: string;
  chat_id: string;
  linked: boolean;
}

export interface InboundFamilyMessage {
  id: number;
  created_at: string;
  profile_id: string;
  link_uuid: string;
  sender_name: string;
  message_type: "text" | "photo";
  text_content: string;
  photo_filename?: string | null;
  audio_data_uri?: string | null;
  delivered_to_kiosk: boolean;
}

export interface TelegramLog {
  id: number;
  created_at: string;
  profile_id: string;
  level: 1 | 2 | 3;
  title: string;
  message: string;
  delivered: boolean;
  channel_status: string;
}

export interface ConversationTurn {
  id: number;
  created_at: string;
  circadian_period: string;
  profile_id: string;
  user_text: string;
  assistant_reply: string;
  mattr: number;
  mean_pause_sec: number;
  max_pause_sec: number;
  anomic_count: number;
  is_repetition: boolean;
  repetition_score: number;
  emotional_state: string;
  emergency_triggered: boolean;
  memory_album_theme: string;
  learned_facts: string[];
  alert_level: number;
  source: string;
}

export interface ClinicalReview {
  id: number;
  created_at: string;
  profile_id: string;
  reviewer_name: string;
  reviewer_role: string;
  decision: string;
  confounding_factors: string[];
  clinical_notes: string;
  mattr_snapshot: number;
  pause_snapshot: number;
}

export interface ConsentEvent {
  id: number;
  created_at: string;
  profile_id: string;
  consent_type: string;
  acknowledged_by: string;
  summary_text: string;
}

export interface AiToolDisclosure {
  tool: string;
  category: string;
  role: string;
  privacy_and_limits: string;
}

export interface DemoScenarioMeta {
  id: string;
  title: string;
  subtitle: string;
  transcript: string;
  expected_theme: string;
}

export interface ConfoundingFactorItem {
  id: string;
  label: string;
  description: string;
}

export interface AppState {
  account: AccountConfig;
  profile: PatientProfile;
  history_21_days: LongitudinalDay[];
  evaluation: LongitudinalEvaluation;
  photos: AlbumPhoto[];
  photo_count: number;
  min_screensaver_photos: number;
  silence_threshold_sec: number;
  memory_album_themes: string[];
  confounding_factors_catalog: ConfoundingFactorItem[];
  telegram_status: TelegramStatus;
  telegram_logs: TelegramLog[];
  recent_turns: ConversationTurn[];
  clinical_reviews: ClinicalReview[];
  consent_events: ConsentEvent[];
  ai_tools_disclosure: AiToolDisclosure[];
  demo_scenarios: DemoScenarioMeta[];
  runtime_status: {
    gemini_configured: boolean;
    telegram_bot_configured: boolean;
    cloud_run_shield: boolean;
  };
}

export interface TurnResponse {
  ok: boolean;
  mode: string;
  turn?: ConversationTurn;
  transcript?: string;
  assistant_reply: string;
  audio_data_uri?: string | null;
  emotional_state?: string;
  emergency_triggered?: boolean;
  emergency_reason?: string | null;
  biographical_rescue_triggered?: boolean;
  rescued_entity?: string | null;
  conversation_topic_summary?: string;
  dinner_conversation_tip?: string;
  learned_facts?: string[];
  memory_album_theme: string;
  matched_photo?: AlbumPhoto | null;
  biomarkers?: {
    mattr: { mattr: number; content_word_count: number; anomic_filler_count: number };
    pauses: { mean_pause_sec: number; max_pause_sec: number; anomic_count: number };
    rms: { duration_sec: number; max_rms_pause_sec: number; anomic_rms_count: number };
    repetition: { is_repetition: boolean; max_similarity: number };
    circadian_period: string;
  };
  telegram_event?: TelegramLog;
  engine_used?: string;
  state?: AppState;
}
