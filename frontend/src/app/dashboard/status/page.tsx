"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { ConnectionStatusOut, TestInboundMessageOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const ROWS = [
  {
    key: "whatsapp" as const,
    icon: "chat",
    title: "WhatsApp",
    description: "Cloud API connection",
  },
  {
    key: "llm" as const,
    icon: "psychology",
    title: "LLM",
    description: "Model used to generate replies",
  },
  {
    key: "webhook" as const,
    icon: "webhook",
    title: "Webhook",
    description: "Last message received from Meta",
  },
  {
    key: "worker" as const,
    icon: "manufacturing",
    title: "Worker",
    description: "Redis queue and ARQ health",
  },
];

function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : null;
}

function normalizePakistanNumber(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.startsWith("00")) return digits.slice(2);
  if (digits.startsWith("92")) return digits;
  if (digits.startsWith("0")) return `92${digits.slice(1)}`;
  if (digits.startsWith("3") && digits.length === 10) return `92${digits}`;
  return digits;
}

export default function ConnectionStatusPage() {
  const [status, setStatus] = useState<ConnectionStatusOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [fromNumber, setFromNumber] = useState("+923030222057");
  const [testMessage, setTestMessage] = useState("hey");
  const [resetConversation, setResetConversation] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);

  useEffect(() => {
    api
      .get<ConnectionStatusOut>("/settings/status")
      .then(setStatus)
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load status"))
      .finally(() => setLoading(false));
  }, []);

  const rowData: Record<string, { ok: boolean; detail: string }> = {
    whatsapp: {
      ok: status?.whatsapp_connected ?? false,
      detail: status?.whatsapp_status ?? "No WhatsApp number configured yet",
    },
    llm: {
      ok: status?.llm_connected ?? false,
      detail: status?.llm_model ?? "No LLM API key configured yet",
    },
    webhook: {
      ok: !!status?.webhook_last_seen_at,
      detail: formatDate(status?.webhook_last_seen_at) ?? "No messages received yet",
    },
    worker: {
      ok: !!status?.redis_connected && !!status?.worker_health_seen,
      detail: status?.redis_connected
        ? `Queue depth: ${status.worker_queue_depth ?? 0}`
        : "Redis is not reachable",
    },
  };

  const metaSetupRows = [
    {
      label: "Expected phone number ID",
      value: status?.webhook_expected_phone_number_id ?? "Not configured",
    },
    {
      label: "Last webhook phone number ID",
      value: status?.webhook_last_phone_number_id ?? "None yet",
    },
    {
      label: "Last webhook processed",
      value: formatDate(status?.webhook_last_processed_at) ?? "None yet",
    },
    {
      label: "Webhook signature",
      value: status?.webhook_signature_configured ? "App secret configured" : "App secret missing",
      warning: !status?.webhook_signature_configured,
    },
    {
      label: "Verify token",
      value: !status?.webhook_verify_token_configured
        ? "Missing"
        : status?.webhook_verify_token_is_placeholder
          ? "Placeholder token"
          : "Configured",
      warning: !status?.webhook_verify_token_configured || !!status?.webhook_verify_token_is_placeholder,
    },
    {
      label: "Worker health",
      value: status?.worker_health_seen ? status.worker_health_detail ?? "Seen" : "No health key seen",
      warning: !status?.worker_health_seen,
    },
  ];

  const lastError =
    status?.webhook_last_send_error ||
    status?.webhook_last_error_message ||
    status?.webhook_last_failure_reason;

  async function handleTestSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSendingTest(true);
    try {
      const result = await api.post<TestInboundMessageOut>("/settings/test-inbound", {
        from_number: fromNumber,
        text: testMessage,
        reset_conversation: resetConversation,
      });
      setFromNumber(`+${result.normalized_from_number}`);
      toast.success(`Test message queued for +${result.normalized_from_number}.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to queue test message");
    } finally {
      setSendingTest(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-on-surface">Connection Status</h1>
        <p className="text-sm text-on-surface-variant">
          Health of the WhatsApp connection, LLM key, and webhook delivery.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {ROWS.map((row) => {
              const { ok, detail } = rowData[row.key];
              return (
                <Card key={row.key} className="border-outline-variant/60">
                  <CardContent className="flex flex-col gap-3 p-4">
                    <div className="flex items-center justify-between">
                      <div
                        className={cn(
                          "flex h-10 w-10 items-center justify-center rounded-full border",
                          ok ? "border-primary/30 text-primary" : "border-outline-variant text-on-surface-variant",
                        )}
                      >
                        <Icon name={row.icon} size={20} />
                      </div>
                      <span
                        className={cn(
                          "flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
                          ok
                            ? "bg-primary-container/15 text-primary"
                            : "bg-surface-container text-on-surface-variant",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            ok ? "animate-pulse bg-primary" : "bg-outline-variant",
                          )}
                        />
                        {ok ? "Connected" : "Needs attention"}
                      </span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-on-surface">{row.title}</div>
                      <div className="text-xs text-on-surface-variant">{row.description}</div>
                    </div>
                    <p className="text-xs text-on-surface-variant">{detail}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Card className="border-outline-variant/60">
            <CardContent className="p-4">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded bg-surface-container text-on-surface-variant">
                  <Icon name="troubleshoot" size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-on-surface">Delivery diagnostics</h2>
                  <p className="text-xs text-on-surface-variant">
                    Runtime signals for the configured WhatsApp number.
                  </p>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {metaSetupRows.map((item) => (
                  <div
                    key={item.label}
                    className="flex min-h-14 items-center justify-between gap-4 border-b border-outline-variant/50 py-2 last:border-b-0 md:last:border-b md:[&:nth-last-child(-n+2)]:border-b-0"
                  >
                    <span className="text-xs font-medium text-on-surface-variant">{item.label}</span>
                    <span
                      className={cn(
                        "max-w-[60%] break-words text-right text-xs text-on-surface",
                        item.warning && "text-error",
                      )}
                    >
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>

              {lastError ? (
                <div className="mt-4 rounded border border-error/30 bg-error-container/20 p-3 text-xs text-error">
                  {lastError}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-outline-variant/60">
            <CardContent className="p-4">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded bg-surface-container text-on-surface-variant">
                  <Icon name="forum" size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-on-surface">Test conversation</h2>
                  <p className="text-xs text-on-surface-variant">
                    Send a customer-style message through the live reply pipeline.
                  </p>
                </div>
              </div>

              <form onSubmit={handleTestSubmit} className="flex flex-col gap-4">
                <div className="grid gap-4 md:grid-cols-[240px_1fr]">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="test-from-number">Customer number</Label>
                    <Input
                      id="test-from-number"
                      value={fromNumber}
                      onChange={(e) => setFromNumber(e.target.value)}
                      onBlur={() => {
                        const normalized = normalizePakistanNumber(fromNumber);
                        if (normalized.startsWith("92")) setFromNumber(`+${normalized}`);
                      }}
                      placeholder="+923030222057"
                      required
                    />
                    <p className="text-xs text-on-surface-variant">
                      Local Pakistan numbers like 03030222057 are sent as +923030222057.
                    </p>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="test-message">Message</Label>
                    <Textarea
                      id="test-message"
                      value={testMessage}
                      onChange={(e) => setTestMessage(e.target.value)}
                      rows={3}
                      required
                    />
                  </div>
                </div>

                <label className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <input
                    type="checkbox"
                    checked={resetConversation}
                    onChange={(e) => setResetConversation(e.target.checked)}
                    className="h-4 w-4 accent-primary"
                  />
                  Reset this number before sending
                </label>

                <Button type="submit" disabled={sendingTest || !fromNumber.trim() || !testMessage.trim()} className="w-fit">
                  <Icon name="send" size={17} className="text-primary-foreground" />
                  {sendingTest ? "Sending..." : "Send test message"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
