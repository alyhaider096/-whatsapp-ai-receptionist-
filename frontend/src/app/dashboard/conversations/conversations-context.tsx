"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import type { ConversationOut } from "@/lib/types";
import { toast } from "sonner";

interface ConversationsContextValue {
  conversations: ConversationOut[];
  loading: boolean;
  refetch: () => Promise<void>;
}

const ConversationsContext = createContext<ConversationsContextValue | undefined>(undefined);

export function ConversationsProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const data = await api.get<ConversationOut[]>("/conversations");
      setConversations(data);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return (
    <ConversationsContext.Provider value={{ conversations, loading, refetch }}>
      {children}
    </ConversationsContext.Provider>
  );
}

export function useConversations(): ConversationsContextValue {
  const ctx = useContext(ConversationsContext);
  if (!ctx) throw new Error("useConversations must be used within ConversationsProvider");
  return ctx;
}
