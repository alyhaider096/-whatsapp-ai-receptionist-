"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Icon } from "@/components/ui/icon";
import { api } from "@/lib/api";
import type { ConnectionStatusOut, MeOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard", exact: true },
  { href: "/dashboard/conversations", label: "Conversations", icon: "forum" },
  { href: "/dashboard/knowledge", label: "Knowledge Base", icon: "library_books" },
  { href: "/dashboard/integrations", label: "Integrations", icon: "extension" },
  { href: "/dashboard/settings", label: "Agent Settings", icon: "settings" },
  { href: "/dashboard/status", label: "Connection Status", icon: "cable" },
];

function initials(email: string): string {
  const name = email.split("@")[0];
  return name.slice(0, 2).toUpperCase();
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<MeOut | null>(null);
  const [status, setStatus] = useState<ConnectionStatusOut | null>(null);

  useEffect(() => {
    if (isReady && !token) router.replace("/login");
  }, [isReady, token, router]);

  useEffect(() => {
    if (!token) return;
    api.get<MeOut>("/auth/me").then(setMe).catch(() => {});
    api.get<ConnectionStatusOut>("/settings/status").then(setStatus).catch(() => {});
  }, [token]);

  if (!isReady || !token) return null;

  const live = !!status?.whatsapp_connected && !!status?.llm_connected;

  return (
    <div className="flex min-h-screen bg-surface">
      {/* Sidebar */}
      <nav className="fixed left-0 top-0 z-30 flex h-screen w-56 flex-col border-r border-outline-variant/60 bg-surface-container-lowest py-4">
        <div className="mb-6 flex items-center gap-3 px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-container text-on-primary-container">
            <Icon name="smart_toy" size={18} />
          </div>
          <div>
            <div className="font-semibold leading-tight text-primary">WA Receptionist</div>
            <div className="text-[11px] leading-tight text-on-surface-variant">Ops Dashboard</div>
          </div>
        </div>

        <ul className="flex-1 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname?.startsWith(item.href);
            return (
              <li key={item.href} className="pr-4">
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-r-full px-4 py-2.5 text-sm transition-colors duration-150",
                    active
                      ? "bg-primary/5 font-medium text-primary"
                      : "text-on-surface-variant hover:bg-surface-container-low",
                  )}
                >
                  <Icon name={item.icon} filled={active} size={20} />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="mt-auto flex flex-col gap-2 px-4 pt-4">
          {me && (
            <div className="flex items-center gap-2 rounded-lg border border-outline-variant/50 px-2 py-2">
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-secondary text-[11px] font-semibold text-secondary-foreground">
                {initials(me.email)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-xs font-medium text-on-surface">{me.business_name}</div>
                <div className="truncate text-[11px] text-on-surface-variant">{me.email}</div>
              </div>
            </div>
          )}
          <button
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="flex items-center justify-center gap-2 rounded-lg border border-outline-variant/60 py-2 text-sm text-on-surface-variant transition-colors duration-150 hover:bg-surface-container-low active:scale-[0.98]"
          >
            <Icon name="logout" size={16} />
            Log out
          </button>
        </div>
      </nav>

      {/* Header */}
      <header className="fixed right-0 top-0 z-20 flex h-14 w-[calc(100%-224px)] items-center justify-end border-b border-outline-variant/60 bg-surface-container-lowest px-6">
        <div className="flex items-center gap-2 rounded-full border border-outline-variant/40 bg-surface-container px-3 py-1">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              live ? "bg-primary" : "bg-outline-variant",
              live && "animate-pulse",
            )}
          />
          <span className="text-[11px] font-medium uppercase tracking-wide text-on-surface">
            {live ? "Live" : "Not connected"}
          </span>
        </div>
      </header>

      <main className="ml-56 mt-14 flex-1 overflow-y-auto p-8">{children}</main>
    </div>
  );
}
