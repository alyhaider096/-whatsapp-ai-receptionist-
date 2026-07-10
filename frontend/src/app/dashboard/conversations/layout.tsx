"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { avatarColor, avatarInitials } from "@/lib/avatar";
import { cn } from "@/lib/utils";
import { ConversationsProvider, useConversations } from "./conversations-context";
import type { ConversationOut } from "@/lib/types";

const STATUS_LABEL: Record<ConversationOut["status"], string> = {
  open: "AI Handling",
  needs_human: "Needs Human",
  human: "You're Handling",
  closed: "Closed",
};

const STATUS_CLASS: Record<ConversationOut["status"], string> = {
  open: "bg-primary-container/15 text-primary",
  needs_human: "bg-error-container text-on-error-container",
  human: "bg-secondary text-secondary-foreground",
  closed: "bg-surface-container text-on-surface-variant",
};

function ConversationList() {
  const { conversations, loading } = useConversations();
  const params = useParams<{ id?: string }>();

  return (
    <div className="flex h-full w-full flex-col border-r border-outline-variant/50 bg-surface-container-lowest md:w-[360px]">
      <div className="flex items-center justify-between border-b border-outline-variant/30 p-4">
        <h1 className="font-semibold text-on-surface">Conversations</h1>
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground">Loading...</p>
        ) : conversations.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">
            No conversations yet -- they&apos;ll show up here once a customer messages your number.
          </p>
        ) : (
          conversations.map((c) => {
            const active = params.id === c.id;
            return (
              <Link
                key={c.id}
                href={`/dashboard/conversations/${c.id}`}
                className={cn(
                  "flex gap-3 border-l-2 p-4 transition-colors duration-150",
                  active
                    ? "border-primary bg-primary/5"
                    : "border-transparent hover:bg-surface-container-low",
                )}
              >
                <div
                  className={cn(
                    "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold",
                    avatarColor(c.contact.id),
                  )}
                >
                  {avatarInitials(c.contact.name, c.contact.phone)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="mb-0.5 flex items-baseline justify-between gap-2">
                    <h3 className="truncate text-sm font-semibold text-on-surface">
                      {c.contact.name ?? c.contact.phone}
                    </h3>
                    <span className="flex-shrink-0 text-[11px] text-on-surface-variant">
                      {new Date(c.updated_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="truncate text-sm text-on-surface-variant">
                    {c.last_message_text ?? "No messages yet"}
                  </p>
                  <span
                    className={cn(
                      "mt-1 inline-block rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide",
                      STATUS_CLASS[c.status],
                    )}
                  >
                    {STATUS_LABEL[c.status]}
                  </span>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function ConversationsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConversationsProvider>
      <div className="-m-8 flex h-[calc(100vh-3.5rem)]">
        <ConversationList />
        <div className="hidden flex-1 md:flex">{children}</div>
      </div>
    </ConversationsProvider>
  );
}
