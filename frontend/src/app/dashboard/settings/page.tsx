"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { AgentBehaviorOut, GreetingMenuOption, LLMConfigOut, WhatsAppConfigOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const MAX_GREETING_MENU_OPTIONS = 5;

const CUSTOM_MODEL_VALUE = "__custom_model__";
const DEFAULT_LEAD_FIELDS = ["name", "service needed", "preferred day/time"];
const DEFAULT_HANDOFF_MESSAGE = "I'm connecting you with a team member. Please wait a moment.";

const MODEL_OPTIONS = [
  { label: "GPT-5 Nano", value: "openai/gpt-5-nano", provider: "openai" },
  { label: "GPT-5 Mini", value: "openai/gpt-5-mini", provider: "openai" },
  { label: "GPT-5", value: "openai/gpt-5", provider: "openai" },
  { label: "GPT-4o Mini", value: "openai/gpt-4o-mini", provider: "openai" },
  { label: "GPT-4o", value: "openai/gpt-4o", provider: "openai" },
];

const REPLY_MODES = [
  {
    value: "auto_answer",
    icon: "smart_toy",
    label: "AI receptionist",
    detail: "Answers from knowledge and asks short follow-ups.",
  },
  {
    value: "lead_capture",
    icon: "assignment_ind",
    label: "Lead collector",
    detail: "Collects details first, then moves the chat toward handoff.",
  },
] as const;

const emptyAgent: AgentBehaviorOut = {
  reply_mode: "auto_answer",
  tone: "friendly and professional",
  memory_window_messages: 8,
  handoff_message: DEFAULT_HANDOFF_MESSAGE,
  lead_fields: DEFAULT_LEAD_FIELDS,
  extra_instructions: "",
  greeting_message: "",
  greeting_menu_options: [],
};

function applyModelConfig(cfg: LLMConfigOut, setProvider: (value: string) => void, setModel: (value: string) => void, setCustomModel: (value: string) => void) {
  setProvider(cfg.provider);
  if (MODEL_OPTIONS.some((option) => option.value === cfg.model)) {
    setModel(cfg.model);
    setCustomModel("");
  } else {
    setModel(CUSTOM_MODEL_VALUE);
    setCustomModel(cfg.model);
  }
}

function fieldsToText(fields: string[]) {
  return fields.join("\n");
}

function textToFields(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function AgentSettingsPage() {
  const [whatsapp, setWhatsapp] = useState<WhatsAppConfigOut | null>(null);
  const [llm, setLlm] = useState<LLMConfigOut | null>(null);
  const [agent, setAgent] = useState<AgentBehaviorOut | null>(null);

  const [wabaId, setWabaId] = useState("");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [savingWhatsapp, setSavingWhatsapp] = useState(false);

  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState(MODEL_OPTIONS[3].value);
  const [customModel, setCustomModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [savingLlm, setSavingLlm] = useState(false);

  const [replyMode, setReplyMode] = useState<AgentBehaviorOut["reply_mode"]>(emptyAgent.reply_mode);
  const [tone, setTone] = useState(emptyAgent.tone);
  const [memoryWindow, setMemoryWindow] = useState(emptyAgent.memory_window_messages);
  const [handoffMessage, setHandoffMessage] = useState(emptyAgent.handoff_message);
  const [leadFieldsText, setLeadFieldsText] = useState(fieldsToText(emptyAgent.lead_fields));
  const [extraInstructions, setExtraInstructions] = useState(emptyAgent.extra_instructions);
  const [greetingMessage, setGreetingMessage] = useState(emptyAgent.greeting_message);
  const [greetingOptions, setGreetingOptions] = useState<GreetingMenuOption[]>(
    emptyAgent.greeting_menu_options,
  );
  const [savingAgent, setSavingAgent] = useState(false);

  useEffect(() => {
    api
      .get<WhatsAppConfigOut | null>("/settings/whatsapp")
      .then((cfg) => {
        if (!cfg) return;
        setWhatsapp(cfg);
        setWabaId(cfg.waba_id);
        setPhoneNumberId(cfg.phone_number_id);
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load WhatsApp config"));

    api
      .get<LLMConfigOut | null>("/settings/llm")
      .then((cfg) => {
        if (!cfg) return;
        setLlm(cfg);
        applyModelConfig(cfg, setProvider, setModel, setCustomModel);
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load LLM config"));

    api
      .get<AgentBehaviorOut>("/settings/agent")
      .then((cfg) => {
        setAgent(cfg);
        setReplyMode(cfg.reply_mode);
        setTone(cfg.tone);
        setMemoryWindow(cfg.memory_window_messages);
        setHandoffMessage(cfg.handoff_message);
        setLeadFieldsText(fieldsToText(cfg.lead_fields));
        setExtraInstructions(cfg.extra_instructions);
        setGreetingMessage(cfg.greeting_message);
        setGreetingOptions(cfg.greeting_menu_options);
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load agent behavior"));
  }, []);

  function addGreetingOption() {
    setGreetingOptions((current) =>
      current.length >= MAX_GREETING_MENU_OPTIONS
        ? current
        : [...current, { title: "", description: "" }],
    );
  }

  function updateGreetingOption(index: number, patch: Partial<GreetingMenuOption>) {
    setGreetingOptions((current) =>
      current.map((option, i) => (i === index ? { ...option, ...patch } : option)),
    );
  }

  function removeGreetingOption(index: number) {
    setGreetingOptions((current) => current.filter((_, i) => i !== index));
  }

  async function handleWhatsappSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextAccessToken = accessToken.trim();
    if (!whatsapp && !nextAccessToken) {
      toast.error("Add a WhatsApp access token before saving this connection.");
      return;
    }
    setSavingWhatsapp(true);
    try {
      const cfg = await api.put<WhatsAppConfigOut>("/settings/whatsapp", {
        waba_id: wabaId.trim(),
        phone_number_id: phoneNumberId.trim(),
        access_token: nextAccessToken || undefined,
      });
      setWhatsapp(cfg);
      setAccessToken("");
      toast.success("WhatsApp connection saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save WhatsApp connection");
    } finally {
      setSavingWhatsapp(false);
    }
  }

  async function handleLlmSubmit(e: React.FormEvent) {
    e.preventDefault();
    const selectedModel = model === CUSTOM_MODEL_VALUE ? customModel.trim() : model;
    const nextApiKey = apiKey.trim();
    if (!selectedModel) {
      toast.error("Choose a model or enter a custom LiteLLM model string.");
      return;
    }
    if (!llm && !nextApiKey) {
      toast.error("Add an API key before saving the LLM configuration.");
      return;
    }
    setSavingLlm(true);
    try {
      const cfg = await api.put<LLMConfigOut>("/settings/llm", {
        provider: provider.trim() || "openai",
        model: selectedModel,
        api_key: nextApiKey || undefined,
      });
      setLlm(cfg);
      setApiKey("");
      applyModelConfig(cfg, setProvider, setModel, setCustomModel);
      toast.success("LLM configuration saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save LLM configuration");
    } finally {
      setSavingLlm(false);
    }
  }

  async function handleAgentSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tone.trim()) {
      toast.error("Add a tone for the assistant.");
      return;
    }
    if (!handoffMessage.trim()) {
      toast.error("Add a handoff message.");
      return;
    }

    setSavingAgent(true);
    try {
      const cfg = await api.put<AgentBehaviorOut>("/settings/agent", {
        reply_mode: replyMode,
        tone: tone.trim(),
        memory_window_messages: memoryWindow,
        handoff_message: handoffMessage.trim(),
        lead_fields: textToFields(leadFieldsText),
        extra_instructions: extraInstructions.trim(),
        greeting_message: greetingMessage.trim(),
        greeting_menu_options: greetingOptions
          .map((option) => ({ title: option.title.trim(), description: option.description.trim() }))
          .filter((option) => option.title.length > 0),
      });
      setAgent(cfg);
      setReplyMode(cfg.reply_mode);
      setTone(cfg.tone);
      setMemoryWindow(cfg.memory_window_messages);
      setHandoffMessage(cfg.handoff_message);
      setLeadFieldsText(fieldsToText(cfg.lead_fields));
      setExtraInstructions(cfg.extra_instructions);
      setGreetingMessage(cfg.greeting_message);
      setGreetingOptions(cfg.greeting_menu_options);
      toast.success("Agent behavior saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save agent behavior");
    } finally {
      setSavingAgent(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">Agent Settings</h1>
          <p className="text-sm text-on-surface-variant">
            Configure the number, model, reply behavior, and short-term chat memory.
          </p>
        </div>
        <Badge variant={whatsapp && llm ? "default" : "outline"} className="h-6">
          {whatsapp && llm ? "Ready to test" : "Setup needed"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <SummaryCard
          icon="chat"
          label="WhatsApp"
          value={whatsapp ? whatsapp.status : "Not connected"}
          active={!!whatsapp}
        />
        <SummaryCard
          icon="psychology"
          label="Model"
          value={llm ? llm.model : "Not configured"}
          active={!!llm}
        />
        <SummaryCard
          icon="memory"
          label="Memory"
          value={`${memoryWindow} messages`}
          active={!!agent}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(340px,0.95fr)]">
        <Card className="border-outline-variant/60">
          <CardContent className="p-5">
            <SectionHeader
              icon="tune"
              title="Behavior and memory"
              description="Controls used by the live WhatsApp reply worker."
            />

            <form onSubmit={handleAgentSubmit} className="mt-5 flex flex-col gap-5">
              <div className="flex flex-col gap-2">
                <Label>Reply mode</Label>
                <div className="grid gap-2 sm:grid-cols-2">
                  {REPLY_MODES.map((modeOption) => {
                    const active = replyMode === modeOption.value;
                    return (
                      <button
                        key={modeOption.value}
                        type="button"
                        onClick={() => setReplyMode(modeOption.value)}
                        className={cn(
                          "flex min-h-24 items-start gap-3 rounded-lg border p-3 text-left transition-colors",
                          active
                            ? "border-primary bg-primary-container/20 text-on-surface"
                            : "border-outline-variant/70 hover:bg-surface-container-low",
                        )}
                      >
                        <span
                          className={cn(
                            "flex h-9 w-9 shrink-0 items-center justify-center rounded border",
                            active ? "border-primary/30 text-primary" : "border-outline-variant text-on-surface-variant",
                          )}
                        >
                          <Icon name={modeOption.icon} size={19} />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">{modeOption.label}</span>
                          <span className="mt-1 block text-xs leading-5 text-on-surface-variant">
                            {modeOption.detail}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="agent-tone">Tone</Label>
                  <Input
                    id="agent-tone"
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    placeholder="friendly and professional"
                    required
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="memory-window">Context window</Label>
                  <div className="rounded-lg border border-outline-variant/70 px-3 py-2">
                    <div className="mb-2 flex items-center justify-between text-xs text-on-surface-variant">
                      <span>Last messages</span>
                      <span className="font-medium text-on-surface">{memoryWindow}</span>
                    </div>
                    <input
                      id="memory-window"
                      type="range"
                      min={0}
                      max={12}
                      value={memoryWindow}
                      onChange={(e) => setMemoryWindow(Number(e.target.value))}
                      className="h-2 w-full accent-primary"
                    />
                  </div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="lead-fields">Lead fields</Label>
                  <Textarea
                    id="lead-fields"
                    value={leadFieldsText}
                    onChange={(e) => setLeadFieldsText(e.target.value)}
                    rows={5}
                    placeholder={"name\nservice needed\npreferred day/time"}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="handoff-message">Handoff message</Label>
                  <Textarea
                    id="handoff-message"
                    value={handoffMessage}
                    onChange={(e) => setHandoffMessage(e.target.value)}
                    rows={5}
                    required
                  />
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="extra-instructions">Business instructions</Label>
                <Textarea
                  id="extra-instructions"
                  value={extraInstructions}
                  onChange={(e) => setExtraInstructions(e.target.value)}
                  rows={4}
                  placeholder="Use Roman Urdu when the customer does. Do not confirm bookings without a person."
                />
              </div>

              <div className="flex flex-col gap-3 rounded-lg border border-outline-variant/60 p-4">
                <div>
                  <Label htmlFor="greeting-message">First-message greeting</Label>
                  <p className="mt-0.5 text-xs text-on-surface-variant">
                    Sent once, the first time a new contact messages you. Leave blank to skip
                    straight to the AI reply as before.
                  </p>
                </div>
                <Textarea
                  id="greeting-message"
                  value={greetingMessage}
                  onChange={(e) => setGreetingMessage(e.target.value)}
                  rows={2}
                  placeholder="Hi! Welcome to Test Clinic. How can we help today?"
                />

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Label>Tappable menu options (optional)</Label>
                    <span className="text-xs text-on-surface-variant">
                      {greetingOptions.length}/{MAX_GREETING_MENU_OPTIONS}
                    </span>
                  </div>
                  {greetingOptions.length === 0 && (
                    <p className="text-xs text-on-surface-variant/70">
                      No menu -- the greeting will send as plain text.
                    </p>
                  )}
                  {greetingOptions.map((option, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <div className="grid flex-1 gap-1.5 sm:grid-cols-2">
                        <Input
                          value={option.title}
                          onChange={(e) => updateGreetingOption(index, { title: e.target.value })}
                          placeholder="Book an appointment"
                          maxLength={24}
                          className="h-9 text-sm"
                        />
                        <Input
                          value={option.description}
                          onChange={(e) => updateGreetingOption(index, { description: e.target.value })}
                          placeholder="Optional short description"
                          maxLength={72}
                          className="h-9 text-sm"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 shrink-0"
                        onClick={() => removeGreetingOption(index)}
                        aria-label="Remove option"
                      >
                        <Icon name="close" size={16} />
                      </Button>
                    </div>
                  ))}
                  {greetingOptions.length < MAX_GREETING_MENU_OPTIONS && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-fit"
                      onClick={addGreetingOption}
                    >
                      <Icon name="add" size={15} />
                      Add option
                    </Button>
                  )}
                </div>
              </div>

              <Button type="submit" disabled={savingAgent} className="w-fit">
                <Icon name="save" size={17} className="text-primary-foreground" />
                {savingAgent ? "Saving..." : "Save behavior"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card className="border-outline-variant/60">
            <CardContent className="p-5">
              <SectionHeader
                icon="api"
                title="WhatsApp connection"
                description={whatsapp ? `Current token: ${whatsapp.access_token_masked}` : "Meta Cloud API number"}
              />
              <form onSubmit={handleWhatsappSubmit} className="mt-5 flex flex-col gap-4">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="waba-id">WABA ID</Label>
                    <Input id="waba-id" required value={wabaId} onChange={(e) => setWabaId(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="phone-number-id">Phone number ID</Label>
                    <Input
                      id="phone-number-id"
                      required
                      value={phoneNumberId}
                      onChange={(e) => setPhoneNumberId(e.target.value)}
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="access-token">Access token</Label>
                  <Input
                    id="access-token"
                    type="password"
                    required={!whatsapp}
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    placeholder={whatsapp ? "Leave blank to keep the current token" : "Paste Meta access token"}
                  />
                </div>
                <Button type="submit" disabled={savingWhatsapp} className="w-fit">
                  <Icon name="save" size={17} className="text-primary-foreground" />
                  {savingWhatsapp ? "Saving..." : "Save WhatsApp"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="border-outline-variant/60">
            <CardContent className="p-5">
              <SectionHeader
                icon="psychology"
                title="AI model"
                description={llm ? `Current key: ${llm.api_key_masked}` : "LiteLLM compatible model"}
              />
              <form onSubmit={handleLlmSubmit} className="mt-5 flex flex-col gap-4">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="provider">Provider</Label>
                    <Input id="provider" required value={provider} onChange={(e) => setProvider(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="model">Model</Label>
                    <Select
                      value={model}
                      onValueChange={(value) => {
                        const nextModel = String(value);
                        setModel(nextModel);
                        const option = MODEL_OPTIONS.find((item) => item.value === nextModel);
                        if (option) setProvider(option.provider);
                      }}
                    >
                      <SelectTrigger id="model" className="h-9 w-full">
                        <SelectValue placeholder="Choose a model" />
                      </SelectTrigger>
                      <SelectContent align="start" className="min-w-[var(--anchor-width)]">
                        <SelectGroup>
                          <SelectLabel>OpenAI models</SelectLabel>
                          {MODEL_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              <span>{option.label}</span>
                              <span className="text-xs text-muted-foreground">{option.value}</span>
                            </SelectItem>
                          ))}
                        </SelectGroup>
                        <SelectItem value={CUSTOM_MODEL_VALUE}>
                          <span>Custom model</span>
                          <span className="text-xs text-muted-foreground">Any LiteLLM string</span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {model === CUSTOM_MODEL_VALUE ? (
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="custom-model">Custom model</Label>
                    <Input
                      id="custom-model"
                      required
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="openai/gpt-5-nano"
                    />
                  </div>
                ) : null}
                <div className="flex flex-col gap-2">
                  <Label htmlFor="api-key">API key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    required={!llm}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={llm ? "Leave blank to keep the current key" : "Paste provider API key"}
                  />
                </div>
                <Button type="submit" disabled={savingLlm} className="w-fit">
                  <Icon name="save" size={17} className="text-primary-foreground" />
                  {savingLlm ? "Saving..." : "Save model"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-surface-container text-on-surface-variant">
        <Icon name={icon} size={18} />
      </div>
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-on-surface">{title}</h2>
        <p className="truncate text-xs text-on-surface-variant">{description}</p>
      </div>
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  active,
}: {
  icon: string;
  label: string;
  value: string;
  active: boolean;
}) {
  return (
    <Card className="border-outline-variant/60">
      <CardContent className="flex items-center gap-3 p-4">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full border",
            active ? "border-primary/30 text-primary" : "border-outline-variant text-on-surface-variant",
          )}
        >
          <Icon name={icon} size={20} />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-on-surface-variant">{label}</div>
          <div className="truncate text-sm font-medium text-on-surface">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}
