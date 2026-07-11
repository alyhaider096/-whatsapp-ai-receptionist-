export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface MeOut {
  email: string;
  business_name: string;
}

export interface DocumentOut {
  id: string;
  title: string;
  source_type: string;
  status: "processing" | "ready" | "failed";
}

export interface WhatsAppConfigOut {
  waba_id: string;
  phone_number_id: string;
  access_token_masked: string;
  status: string;
}

export interface LLMConfigOut {
  provider: string;
  model: string;
  api_key_masked: string;
}

export interface GreetingMenuOption {
  title: string;
  description: string;
}

export interface AgentBehaviorOut {
  reply_mode: "auto_answer" | "lead_capture";
  tone: string;
  memory_window_messages: number;
  handoff_message: string;
  lead_fields: string[];
  extra_instructions: string;
  greeting_message: string;
  greeting_menu_options: GreetingMenuOption[];
}

export interface ConnectionStatusOut {
  whatsapp_connected: boolean;
  whatsapp_status: string | null;
  llm_connected: boolean;
  llm_model: string | null;
  webhook_last_seen_at: string | null;
  webhook_expected_phone_number_id: string | null;
  webhook_last_phone_number_id: string | null;
  webhook_last_processed_at: string | null;
  webhook_last_failure_reason: string | null;
  webhook_last_error_message: string | null;
  webhook_last_send_error: string | null;
  webhook_signature_configured: boolean;
  webhook_verify_token_configured: boolean;
  webhook_verify_token_is_placeholder: boolean;
  redis_connected: boolean;
  worker_queue_depth: number | null;
  worker_health_seen: boolean;
  worker_health_detail: string | null;
}

export interface TestInboundMessageOut {
  status: string;
  webhook_event_id: string;
  wa_message_id: string;
  normalized_from_number: string;
}

export interface ContactOut {
  id: string;
  phone: string;
  name: string | null;
}

export interface ConversationOut {
  id: string;
  status: "open" | "needs_human" | "human" | "closed";
  last_inbound_at: string | null;
  contact: ContactOut;
  last_message_text: string | null;
  updated_at: string;
  assigned_user_id: string | null;
  assigned_user_email: string | null;
  tags: string[];
  lead_status: "new" | "qualified" | "needs_human" | "booked" | "lost" | null;
  lead_notes: string | null;
}

export interface ConversationCrmUpdateIn {
  assigned_user_id?: string | null;
  lead_status?: string;
  lead_notes?: string | null;
}

export interface TeamMemberOut {
  id: string;
  email: string;
  role: string;
}

export interface MessageOut {
  id: string;
  direction: "inbound" | "outbound";
  type: "text" | "audio" | "image" | "document";
  text: string | null;
  audio_url: string | null;
  created_at: string;
}

export interface SheetConfigOut {
  spreadsheet_id: string;
  sheet_name: string;
}

export interface SheetsServiceAccountOut {
  email: string | null;
}

export interface SheetsTestResult {
  ok: boolean;
  message: string;
  header_row: string[];
}

export interface LeadOut {
  id: string;
  intent: string | null;
  status: "new" | "qualified" | "needs_human" | "booked" | "lost";
  notes: string | null;
  value: number | null;
  contact: ContactOut;
  created_at: string;
}
