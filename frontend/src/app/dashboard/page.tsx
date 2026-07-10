"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { Card, CardContent } from "@/components/ui/card";
import { avatarColor, avatarInitials } from "@/lib/avatar";
import { api, ApiError } from "@/lib/api";
import type { ConversationOut, LeadOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const STAT_ICONS = {
  active: "forum",
  needsHuman: "front_hand",
  leads: "person_add",
} as const;

export default function DashboardOverviewPage() {
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [leads, setLeads] = useState<LeadOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<ConversationOut[]>("/conversations"),
      api.get<LeadOut[]>("/leads"),
    ])
      .then(([c, l]) => {
        setConversations(c);
        setLeads(l);
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  const activeCount = conversations.filter((c) => c.status === "open").length;
  const needsHumanCount = conversations.filter((c) => c.status === "needs_human").length;
  const recent = [...conversations]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 6);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-on-surface">Dashboard</h1>
        <p className="text-sm text-on-surface-variant">
          A quick read on what the assistant is handling right now.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={STAT_ICONS.active}
          label="Active Conversations"
          value={loading ? "--" : activeCount}
        />
        <StatCard
          icon={STAT_ICONS.needsHuman}
          label="Needs Human"
          value={loading ? "--" : needsHumanCount}
          alert={needsHumanCount > 0}
        />
        <StatCard icon={STAT_ICONS.leads} label="Total Leads" value={loading ? "--" : leads.length} />
      </div>

      <Card>
        <div className="flex items-center justify-between border-b border-outline-variant/30 p-4">
          <h2 className="font-semibold text-on-surface">Recent Activity</h2>
          <Link href="/dashboard/conversations" className="text-sm text-primary hover:underline">
            View all
          </Link>
        </div>
        <CardContent className="p-0">
          {loading ? (
            <p className="p-4 text-sm text-muted-foreground">Loading...</p>
          ) : recent.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              No conversations yet -- they&apos;ll show up here once a customer messages your number.
            </p>
          ) : (
            <div className="divide-y divide-outline-variant/30">
              {recent.map((c) => (
                <Link
                  key={c.id}
                  href={`/dashboard/conversations/${c.id}`}
                  className="flex items-center justify-between gap-4 p-4 transition-colors duration-150 hover:bg-surface-container-low"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                        avatarColor(c.contact.id),
                      )}
                    >
                      {avatarInitials(c.contact.name, c.contact.phone)}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-on-surface">
                        {c.contact.name ?? c.contact.phone}
                      </div>
                      <div className="line-clamp-1 text-xs text-on-surface-variant">
                        {c.last_message_text ?? "No messages yet"}
                      </div>
                    </div>
                  </div>
                  <span className="flex-shrink-0 text-xs text-on-surface-variant">
                    {new Date(c.updated_at).toLocaleString()}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  alert = false,
}: {
  icon: string;
  label: string;
  value: string | number;
  alert?: boolean;
}) {
  return (
    <Card className={cn(alert && "border-error-container")}>
      <CardContent className="flex items-center gap-4 p-4">
        <div
          className={cn(
            "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border",
            alert ? "border-error-container text-destructive" : "border-outline-variant/60 text-primary",
          )}
        >
          <Icon name={icon} size={22} />
        </div>
        <div>
          <div className="mb-1 text-xs text-on-surface-variant">{label}</div>
          <div
            className={cn(
              "text-2xl font-semibold leading-none",
              alert ? "text-destructive" : "text-on-surface",
            )}
          >
            {value}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
