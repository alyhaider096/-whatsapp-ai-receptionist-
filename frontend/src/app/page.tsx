"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const router = useRouter();
  const { token, isReady } = useAuth();

  useEffect(() => {
    if (!isReady) return;
    router.replace(token ? "/dashboard" : "/login");
  }, [isReady, token, router]);

  return null;
}
