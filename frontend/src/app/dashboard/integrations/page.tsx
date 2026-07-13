"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { api, ApiError } from "@/lib/api";
import type {
  CalcomConfigOut,
  CalcomEventTypeOut,
  SheetConfigOut,
  SheetsServiceAccountOut,
  SheetsTestResult,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const INTEGRATIONS = [
  {
    name: "Google Calendar",
    icon: "calendar_month",
    status: "Planned",
    description: "Check availability and prepare appointment slots once booking is added.",
    setup: ["Connect Google", "Choose calendar", "Set working hours and buffer"],
    fields: ["Calendar", "Timezone", "Working hours", "Buffer", "Conflict rule"],
    accent: "text-tertiary",
  },
];

const FLOW_STEPS = [
  "Customer asks for appointment",
  "AI collects lead fields",
  "Human confirms or booking module runs",
  "Sheet row / calendar event / Cal.com booking is updated",
];

const META_STEPS = [
  {
    title: "Facebook login",
    detail: "Client signs in with their own Facebook account. We never ask for their password.",
  },
  {
    title: "Business portfolio",
    detail: "Meta shows the portfolios they administer, then the WhatsApp Business Account.",
  },
  {
    title: "Phone number",
    detail: "Client chooses or registers the real WhatsApp number they want this assistant to use.",
  },
  {
    title: "Permission grant",
    detail: "They approve WhatsApp messaging/management permissions for our Meta app.",
  },
  {
    title: "Connection saved",
    detail: "Backend stores WABA ID, phone number ID, display number, and encrypted token.",
  },
];

export default function IntegrationsPage() {
  return (
      <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">Integrations</h1>
          <p className="text-sm text-on-surface-variant">
            Preview the modules that will connect leads, sheets, calendars, and booking tools.
          </p>
        </div>
        <Badge variant="outline" className="h-6">
          Frontend preview
        </Badge>
      </div>

      <Card className="border-primary/20 bg-primary-container/5">
        <CardContent className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-surface-container-lowest text-primary">
              <Icon name="verified" size={22} />
            </div>
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-on-surface">Meta Official WhatsApp</h2>
                <Badge variant="outline">Embedded Signup later</Badge>
              </div>
              <p className="text-sm leading-6 text-on-surface-variant">
                This is the production connection path: the business owner logs in with Facebook,
                chooses their business portfolio, selects the WhatsApp Business Account and phone
                number, then grants access to this app.
              </p>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {["Business portfolio", "WABA", "Phone number ID"].map((item) => (
                  <div key={item} className="rounded-lg border border-outline-variant/60 bg-surface/70 p-3">
                    <div className="text-xs font-medium text-on-surface">{item}</div>
                    <div className="mt-1 text-[11px] text-on-surface-variant">Selected inside Meta</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-start justify-start xl:justify-end">
            <MetaPreviewDialog />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <GoogleSheetsCard />
        <CalcomCard />
        {INTEGRATIONS.map((integration) => (
          <IntegrationCard key={integration.name} integration={integration} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="border-outline-variant/60">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded bg-surface-container text-on-surface-variant">
                <Icon name="account_tree" size={18} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-on-surface">Future automation flow</h2>
                <p className="text-xs text-on-surface-variant">
                  The page is ready for the UI shape; backend OAuth and booking logic come later.
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-4">
              {FLOW_STEPS.map((step, index) => (
                <div key={step} className="rounded-lg border border-outline-variant/60 p-3">
                  <div className="mb-3 flex h-7 w-7 items-center justify-center rounded-full bg-primary-container/25 text-xs font-semibold text-primary">
                    {index + 1}
                  </div>
                  <p className="text-sm font-medium leading-5 text-on-surface">{step}</p>
                </div>
              ))}
            </div>

            <Separator className="my-5 bg-outline-variant/50" />

            <div className="grid gap-4 md:grid-cols-3">
              <PreviewBlock
                icon="login"
                title="OAuth"
                text="Connect with Google or Cal.com, store encrypted tokens, and show sync health."
              />
              <PreviewBlock
                icon="sync_alt"
                title="Read / write"
                text="Choose whether the integration only exports leads or also reads rows/events."
              />
              <PreviewBlock
                icon="rule"
                title="Rules"
                text="No automatic bookings until the booking module has confirmation and conflict checks."
              />
            </div>
          </CardContent>
        </Card>

        <Card className="border-outline-variant/60">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded bg-surface-container text-on-surface-variant">
                <Icon name="view_timeline" size={18} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-on-surface">Build order</h2>
                <p className="text-xs text-on-surface-variant">What to implement after v1 is stable.</p>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3">
              {[
                "Google OAuth connection",
                "Sheets lead export mapping",
                "Calendar availability settings",
                "Cal.com event type mapping",
                "Booking confirmation in WhatsApp",
              ].map((item, index) => (
                <div key={item} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-outline-variant text-[11px] text-on-surface-variant">
                    {index + 1}
                  </span>
                  <span className="text-sm leading-5 text-on-surface">{item}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function GoogleSheetsCard() {
  const [serviceAccount, setServiceAccount] = useState<SheetsServiceAccountOut | null>(null);
  const [config, setConfig] = useState<SheetConfigOut | null>(null);
  const [spreadsheetId, setSpreadsheetId] = useState("");
  const [sheetName, setSheetName] = useState("Appointments");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SheetsTestResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<SheetsServiceAccountOut>("/settings/sheets/service-account"),
      api.get<SheetConfigOut | null>("/settings/sheets"),
    ])
      .then(([account, cfg]) => {
        setServiceAccount(account);
        if (cfg) {
          setConfig(cfg);
          setSpreadsheetId(cfg.spreadsheet_id);
          setSheetName(cfg.sheet_name);
        }
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load Sheets settings"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!spreadsheetId.trim()) {
      toast.error("Add a Spreadsheet ID first.");
      return;
    }
    setSaving(true);
    try {
      const cfg = await api.put<SheetConfigOut>("/settings/sheets", {
        spreadsheet_id: spreadsheetId.trim(),
        sheet_name: sheetName.trim() || "Appointments",
      });
      setConfig(cfg);
      setTestResult(null);
      toast.success("Sheet connection saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post<SheetsTestResult>("/settings/sheets/test");
      setTestResult(result);
      if (result.ok) toast.success(result.message);
      else toast.error(result.message);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Test failed");
    } finally {
      setTesting(false);
    }
  }

  function copyEmail() {
    if (!serviceAccount?.email) return;
    navigator.clipboard.writeText(serviceAccount.email);
    toast.success("Copied");
  }

  const notConfigured = !loading && !serviceAccount?.email;

  return (
    <Card className="border-outline-variant/60">
      <CardContent className="flex h-full flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-outline-variant/60 text-primary">
              <Icon name="table_chart" size={21} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-on-surface">Google Sheets</h2>
              <p className="text-xs text-on-surface-variant">
                {config ? "Connected" : "Read/write appointment booking"}
              </p>
            </div>
          </div>
          <Badge variant={config ? "default" : "outline"}>{config ? "Live" : "Not connected"}</Badge>
        </div>

        <p className="text-sm leading-6 text-on-surface-variant">
          The assistant can check availability, look up an existing booking by phone, propose a new
          booking, and reschedule -- all reading and writing directly to your own Sheet. Every write
          is confirmed with the customer first.
        </p>

        {notConfigured ? (
          <div className="rounded-lg border border-outline-variant/60 bg-surface-container-low p-3 text-xs text-on-surface-variant">
            Google Sheets isn&apos;t configured on this deployment yet -- ask your developer to add a
            service account key.
          </div>
        ) : (
          <>
            <div className="rounded-lg border border-outline-variant/60 bg-surface-container-low p-3">
              <div className="mb-1 text-xs font-medium text-on-surface">Share your Sheet with</div>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate text-[11px] text-on-surface-variant">
                  {loading ? "Loading..." : serviceAccount?.email}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={copyEmail}
                  disabled={loading}
                >
                  <Icon name="content_copy" size={14} />
                </Button>
              </div>
              <p className="mt-1 text-[11px] text-on-surface-variant">
                Give it Editor access, like sharing with a colleague.
              </p>
            </div>

            <form onSubmit={handleSave} className="grid gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="sheet-id" className="text-xs">
                  Spreadsheet ID
                </Label>
                <Input
                  id="sheet-id"
                  value={spreadsheetId}
                  onChange={(e) => setSpreadsheetId(e.target.value)}
                  placeholder="From the sheet's URL"
                  className="h-9 text-sm"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sheet-tab" className="text-xs">
                  Sheet/tab name
                </Label>
                <Input
                  id="sheet-tab"
                  value={sheetName}
                  onChange={(e) => setSheetName(e.target.value)}
                  placeholder="Appointments"
                  className="h-9 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={saving}>
                  <Icon name="save" size={15} />
                  {saving ? "Saving..." : "Save"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={testing || !config}
                  onClick={handleTest}
                >
                  <Icon name="bolt" size={15} />
                  {testing ? "Testing..." : "Test connection"}
                </Button>
              </div>
            </form>

            {testResult && (
              <div
                className={cn(
                  "rounded-lg border p-3 text-xs",
                  testResult.ok
                    ? "border-primary/30 bg-primary-container/10 text-on-surface"
                    : "border-error-container text-destructive",
                )}
              >
                {testResult.message}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CalcomCard() {
  const [config, setConfig] = useState<CalcomConfigOut | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [eventTypes, setEventTypes] = useState<CalcomEventTypeOut[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadingEventTypes, setLoadingEventTypes] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<CalcomConfigOut | null>("/settings/calcom")
      .then((cfg) => setConfig(cfg))
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load Cal.com settings"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSaveApiKey(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) {
      toast.error("Add your Cal.com API key first.");
      return;
    }
    setSaving(true);
    try {
      const cfg = await api.put<CalcomConfigOut>("/settings/calcom", { api_key: apiKey.trim() });
      setConfig(cfg);
      setApiKey("");
      setEventTypes(null);
      toast.success("Cal.com API key saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleLoadEventTypes() {
    setLoadingEventTypes(true);
    try {
      const types = await api.get<CalcomEventTypeOut[]>("/settings/calcom/event-types");
      setEventTypes(types);
      if (types.length === 0) toast.error("No event types found on this Cal.com account.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load event types");
    } finally {
      setLoadingEventTypes(false);
    }
  }

  async function handlePickEventType(eventType: CalcomEventTypeOut) {
    setSaving(true);
    try {
      const cfg = await api.put<CalcomConfigOut>("/settings/calcom", {
        event_type_id: eventType.id,
        event_type_title: eventType.title,
      });
      setConfig(cfg);
      toast.success(`Using "${eventType.title}" for bookings`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save event type");
    } finally {
      setSaving(false);
    }
  }

  const connected = !loading && !!config;
  const ready = connected && config?.event_type_id != null;

  return (
    <Card className="border-outline-variant/60">
      <CardContent className="flex h-full flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-outline-variant/60 text-primary">
              <Icon name="event_available" size={21} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-on-surface">Cal.com</h2>
              <p className="text-xs text-on-surface-variant">
                {ready ? `Booking via "${config?.event_type_title}"` : "Check availability & book appointments"}
              </p>
            </div>
          </div>
          <Badge variant={ready ? "default" : "outline"}>{ready ? "Live" : "Not connected"}</Badge>
        </div>

        <p className="text-sm leading-6 text-on-surface-variant">
          The assistant can check open slots, look up an existing booking by email, propose a new
          booking, and reschedule -- directly against your Cal.com account. Every write is confirmed
          with the customer first.
        </p>

        <div className="grid gap-1.5">
          <Label htmlFor="calcom-key" className="text-xs">
            API key
          </Label>
          <form onSubmit={handleSaveApiKey} className="flex gap-2">
            <Input
              id="calcom-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={connected ? `Saved (${config?.api_key_masked})` : "cal_live_..."}
              className="h-9 flex-1 text-sm"
            />
            <Button type="submit" size="sm" disabled={saving}>
              <Icon name="save" size={15} />
              {saving ? "Saving..." : "Save"}
            </Button>
          </form>
          <p className="text-[11px] text-on-surface-variant">
            From your Cal.com account under Settings &rarr; Developer &rarr; API keys.
          </p>
        </div>

        {connected && (
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Event type</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={loadingEventTypes}
                onClick={handleLoadEventTypes}
              >
                <Icon name="refresh" size={14} />
                {loadingEventTypes ? "Loading..." : "Load event types"}
              </Button>
            </div>
            {eventTypes && (
              <div className="flex flex-col gap-1.5">
                {eventTypes.map((et) => (
                  <button
                    key={et.id}
                    type="button"
                    disabled={saving}
                    onClick={() => handlePickEventType(et)}
                    className={cn(
                      "flex items-center justify-between rounded-lg border p-2.5 text-left text-xs transition-colors",
                      config?.event_type_id === et.id
                        ? "border-primary/50 bg-primary-container/10"
                        : "border-outline-variant/60 hover:bg-surface-container-low",
                    )}
                  >
                    <span className="font-medium text-on-surface">{et.title}</span>
                    <span className="text-on-surface-variant">
                      {et.length ? `${et.length} min` : ""}
                      {config?.event_type_id === et.id ? " · Selected" : ""}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MetaPreviewDialog() {
  return (
    <Dialog>
      <DialogTrigger render={<Button type="button" />}>
        <Icon name="add" size={17} className="text-primary-foreground" />
        Connect Meta Official
      </DialogTrigger>
      <DialogContent className="max-w-2xl p-0">
        <DialogHeader className="border-b border-outline-variant/50 p-5 pb-4">
          <DialogTitle>Quick Setup: Meta Official WhatsApp</DialogTitle>
          <DialogDescription>
            Preview of the future Facebook Login for Business / WhatsApp Embedded Signup flow.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 p-5">
          <div className="grid gap-2">
            <Label htmlFor="meta-instance-name">Instance name</Label>
            <Input id="meta-instance-name" placeholder="E.g. Main clinic WhatsApp" disabled />
            <p className="text-xs text-on-surface-variant">
              This name helps the owner recognize the connected WhatsApp number in the dashboard.
            </p>
          </div>

          <div className="rounded-lg border border-primary/25 bg-primary-container/10 p-4">
            <div className="mb-3 flex items-center justify-center gap-2 text-sm font-semibold text-on-surface">
              <Icon name="bolt" size={18} className="text-primary" />
              Connect through Meta
            </div>
            <p className="mx-auto max-w-md text-center text-sm leading-6 text-on-surface-variant">
              The real button will open Meta&apos;s hosted login and setup window. The client chooses
              the business portfolio, WhatsApp Business Account, and production phone number there.
            </p>
            <Button type="button" disabled className="mx-auto mt-4 flex w-full max-w-md">
              <Icon name="login" size={16} className="text-primary-foreground" />
              Continue with Facebook
            </Button>
          </div>

          <div className="grid gap-2">
            {META_STEPS.map((step, index) => (
              <div key={step.title} className="flex gap-3 rounded-lg border border-outline-variant/60 p-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-container text-xs font-medium text-on-surface">
                  {index + 1}
                </span>
                <div>
                  <div className="text-sm font-medium text-on-surface">{step.title}</div>
                  <p className="mt-1 text-xs leading-5 text-on-surface-variant">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <DialogFooter className="m-0 rounded-b-xl">
          <Button type="button" disabled>
            Backend OAuth not connected yet
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function IntegrationCard({
  integration,
}: {
  integration: {
    name: string;
    icon: string;
    status: string;
    description: string;
    setup: string[];
    fields: string[];
    accent: string;
  };
}) {
  return (
    <Card className="border-outline-variant/60">
      <CardContent className="flex h-full flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg border border-outline-variant/60", integration.accent)}>
              <Icon name={integration.icon} size={21} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-on-surface">{integration.name}</h2>
              <p className="text-xs text-on-surface-variant">{integration.status}</p>
            </div>
          </div>
          <Badge variant="outline">Soon</Badge>
        </div>

        <p className="text-sm leading-6 text-on-surface-variant">{integration.description}</p>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          <div>
            <div className="mb-2 text-xs font-medium text-on-surface">Setup</div>
            <div className="flex flex-col gap-1.5">
              {integration.setup.map((item) => (
                <div key={item} className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <Icon name="radio_button_unchecked" size={14} />
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-on-surface">Data</div>
            <div className="flex flex-wrap gap-1.5">
              {integration.fields.map((field) => (
                <span
                  key={field}
                  className="rounded-full border border-outline-variant/60 px-2 py-0.5 text-[11px] text-on-surface-variant"
                >
                  {field}
                </span>
              ))}
            </div>
          </div>
        </div>

        <Button type="button" variant="outline" disabled className="mt-auto w-fit">
          <Icon name="lock" size={16} />
          Connect later
        </Button>
      </CardContent>
    </Card>
  );
}

function PreviewBlock({ icon, title, text }: { icon: string; title: string; text: string }) {
  return (
    <div className="rounded-lg border border-outline-variant/60 p-3">
      <div className="mb-3 flex h-8 w-8 items-center justify-center rounded bg-surface-container text-on-surface-variant">
        <Icon name={icon} size={17} />
      </div>
      <div className="text-sm font-medium text-on-surface">{title}</div>
      <p className="mt-1 text-xs leading-5 text-on-surface-variant">{text}</p>
    </div>
  );
}
