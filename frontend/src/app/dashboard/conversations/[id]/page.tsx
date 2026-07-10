"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { avatarColor, avatarInitials } from "@/lib/avatar";
import type { ConversationOut, MessageOut, TeamMemberOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useConversations } from "../conversations-context";

const LEAD_STAGES: { value: string; label: string }[] = [
  { value: "new", label: "New" },
  { value: "qualified", label: "Qualified" },
  { value: "needs_human", label: "Needs human" },
  { value: "booked", label: "Booked" },
  { value: "lost", label: "Lost" },
];

export default function ConversationThreadPage() {
  const params = useParams<{ id: string }>();
  const { conversations, refetch } = useConversations();
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversation = conversations.find((c) => c.id === params.id);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    api
      .get<MessageOut[]>(`/conversations/${params.id}/messages`)
      .then(setMessages)
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [params.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    try {
      const message = await api.post<MessageOut>(`/conversations/${params.id}/reply`, {
        text: draft,
      });
      setMessages((prev) => [...prev, message]);
      setDraft("");
      await refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to send");
    } finally {
      setSending(false);
    }
  }

  if (!conversation) return null;

  return (
    <div className="flex h-full w-full bg-surface">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Thread header */}
        <div className="flex h-16 flex-shrink-0 items-center justify-between border-b border-outline-variant/50 bg-surface-container-lowest px-6">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold",
                avatarColor(conversation.contact.id),
              )}
            >
              {avatarInitials(conversation.contact.name, conversation.contact.phone)}
            </div>
            <div>
              <h2 className="font-semibold text-on-surface">
                {conversation.contact.name ?? conversation.contact.phone}
              </h2>
              <p className="text-xs text-on-surface-variant">{conversation.contact.phone}</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : messages.length === 0 ? (
            <p className="text-sm text-muted-foreground">No messages in this conversation yet.</p>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "flex items-end gap-2",
                    m.direction === "outbound" && "flex-row-reverse",
                  )}
                >
                  <div
                    className={cn(
                      "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                      m.direction === "outbound"
                        ? "bg-primary-container text-on-primary-container"
                        : avatarColor(conversation.contact.id),
                    )}
                  >
                    {m.direction === "outbound" ? (
                      <Icon name="smart_toy" size={14} />
                    ) : (
                      avatarInitials(conversation.contact.name, conversation.contact.phone)
                    )}
                  </div>
                  <div
                    className={cn(
                      "max-w-[70%] rounded-2xl p-3 text-sm shadow-sm",
                      m.direction === "outbound"
                        ? "rounded-br-sm bg-primary-container/10 text-on-primary-fixed-variant"
                        : "rounded-bl-sm border border-outline-variant/30 bg-surface-container-lowest text-on-surface",
                    )}
                  >
                    {m.type !== "text" && (
                      <div className="mb-1 text-xs opacity-70">[{m.type}]</div>
                    )}
                    <p>{m.text}</p>
                    <div
                      className={cn(
                        "mt-1 text-[10px] opacity-60",
                        m.direction === "outbound" ? "text-right" : "",
                      )}
                    >
                      {new Date(m.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Reply box */}
        <div className="flex-shrink-0 border-t border-outline-variant/50 bg-surface-container-lowest p-4">
          <div className="mb-2 flex items-center gap-2 px-1 text-on-surface-variant/70">
            <Icon name="info" size={14} />
            <span className="text-[11px]">
              Sending a message takes this conversation over from the AI.
            </span>
          </div>
          <form onSubmit={handleSend} className="flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type a message to manually reply..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-outline-variant/40 bg-surface-container-low px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary"
            />
            <Button type="submit" disabled={sending || !draft.trim()} size="icon" className="rounded-full">
              <Icon name="send" size={18} className="text-primary-foreground" />
            </Button>
          </form>
        </div>
      </div>
      <ConversationCrmPanel conversation={conversation} messages={messages} />
    </div>
  );
}

function ConversationCrmPanel({
  conversation,
  messages,
}: {
  conversation: ConversationOut;
  messages: MessageOut[];
}) {
  const { refetch } = useConversations();
  const [teamMembers, setTeamMembers] = useState<TeamMemberOut[]>([]);
  const [saving, setSaving] = useState(false);
  const [notesDraft, setNotesDraft] = useState(conversation.lead_notes ?? "");
  const [newTag, setNewTag] = useState("");
  const [addingTag, setAddingTag] = useState(false);

  useEffect(() => {
    api
      .get<TeamMemberOut[]>("/team-members")
      .then(setTeamMembers)
      .catch(() => {
        /* Assign-agent dropdown just stays empty -- not worth a toast. */
      });
  }, []);

  // Keep the notes draft in sync when switching between conversations, but
  // don't clobber what the user is mid-typing on the same conversation.
  useEffect(() => {
    setNotesDraft(conversation.lead_notes ?? "");
  }, [conversation.id, conversation.lead_notes]);

  const lastInbound = [...messages].reverse().find((message) => message.direction === "inbound");
  const patientName = conversation.contact.name ?? "";

  async function updateCrm(body: Record<string, unknown>) {
    setSaving(true);
    try {
      await api.patch(`/conversations/${conversation.id}/crm`, body);
      await refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function saveNotesIfChanged() {
    if (notesDraft === (conversation.lead_notes ?? "")) return;
    updateCrm({ lead_notes: notesDraft });
  }

  async function addTag(e?: React.FormEvent) {
    e?.preventDefault();
    const tag = newTag.trim();
    if (!tag) return;
    setAddingTag(true);
    try {
      await api.post(`/conversations/${conversation.id}/tags`, { tag });
      setNewTag("");
      await refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to add tag");
    } finally {
      setAddingTag(false);
    }
  }

  async function removeTag(tag: string) {
    try {
      await api.delete(`/conversations/${conversation.id}/tags/${encodeURIComponent(tag)}`);
      await refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to remove tag");
    }
  }

  return (
    <aside className="hidden w-80 shrink-0 flex-col overflow-y-auto border-l border-outline-variant/50 bg-surface-container-lowest xl:flex">
      <div className="border-b border-outline-variant/50 p-5">
        <div className="flex items-center gap-3 rounded-lg border border-outline-variant/60 bg-surface p-3">
          <div
            className={cn(
              "flex h-11 w-11 items-center justify-center rounded-full text-sm font-bold",
              avatarColor(conversation.contact.id),
            )}
          >
            {avatarInitials(conversation.contact.name, conversation.contact.phone)}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-on-surface">
              {conversation.contact.name ?? "New contact"}
            </div>
            <div className="flex items-center gap-1 text-xs text-on-surface-variant">
              <Icon name="call" size={13} />
              <span className="truncate">{conversation.contact.phone}</span>
            </div>
          </div>
        </div>
      </div>

      <PanelSection icon="sell" title="Tags">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {conversation.tags.length === 0 && (
            <span className="text-xs text-on-surface-variant/70">No tags yet.</span>
          )}
          {conversation.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="h-6 gap-1 pr-1">
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="rounded-full p-0.5 hover:bg-outline-variant/30"
                aria-label={`Remove tag ${tag}`}
              >
                <Icon name="close" size={12} />
              </button>
            </Badge>
          ))}
        </div>
        <form onSubmit={addTag} className="flex items-center gap-1.5">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="New tag..."
            className="h-8 text-xs"
            maxLength={50}
          />
          <Button type="submit" variant="outline" size="sm" disabled={addingTag || !newTag.trim()}>
            <Icon name="add" size={15} />
          </Button>
        </form>
      </PanelSection>

      <PanelSection icon="support_agent" title="Assign agent">
        <Select
          value={conversation.assigned_user_id ?? "unassigned"}
          onValueChange={(value) =>
            updateCrm({ assigned_user_id: value === "unassigned" ? null : value })
          }
          disabled={saving}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="unassigned">Unassigned</SelectItem>
            {teamMembers.map((member) => (
              <SelectItem key={member.id} value={member.id}>
                {member.email}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PanelSection>

      <PanelSection icon="filter_alt" title="Funnel stage">
        <Select
          value={conversation.lead_status ?? "new"}
          onValueChange={(value) => updateCrm({ lead_status: value })}
          disabled={saving}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            {LEAD_STAGES.map((stage) => (
              <SelectItem key={stage.value} value={stage.value}>
                {stage.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PanelSection>

      <PanelSection icon="notes" title="Notes">
        <Textarea
          value={notesDraft}
          onChange={(event) => setNotesDraft(event.target.value)}
          onBlur={saveNotesIfChanged}
          rows={4}
          placeholder="Add notes here..."
          className="text-sm"
        />
      </PanelSection>

      <PanelSection icon="tune" title="Custom fields">
        <div className="grid gap-3">
          <Field label="ID" value={conversation.id} readOnly />
          <Field label="Patient name" value={patientName} readOnly />
          <Field label="Phone WhatsApp" value={conversation.contact.phone} readOnly />
          <Field label="Status" value={conversation.status.replace("_", " ")} readOnly />
          <Field
            label="Last inbound"
            value={lastInbound ? new Date(lastInbound.created_at).toLocaleString() : ""}
            readOnly
          />
        </div>
      </PanelSection>
    </aside>
  );
}

function PanelSection({
  icon,
  title,
  children,
}: {
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-outline-variant/50 p-5">
      <div className="mb-3 flex items-center gap-2 text-on-surface">
        <Icon name={icon} size={18} className="text-on-surface-variant" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  value,
  readOnly,
}: {
  label: string;
  value: string;
  readOnly?: boolean;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs text-on-surface-variant">{label}</Label>
      <Input value={value} readOnly={readOnly} className="h-9 text-xs" />
    </div>
  );
}
