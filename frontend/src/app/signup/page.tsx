"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/components/auth-layout";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { TokenResponse } from "@/lib/types";
import { toast } from "sonner";

export default function SignupPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<TokenResponse>(
        "/auth/signup",
        { business_name: businessName, email, password },
        { auth: false },
      );
      login(res.access_token);
      router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">Create your account</h1>
          <p className="text-sm text-on-surface-variant">Set up your WhatsApp AI receptionist.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="business_name">Business name</Label>
            <Input
              id="business_name"
              required
              autoFocus
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="e.g. Green Valley Clinic"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="owner@yourbusiness.com"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-xs text-on-surface-variant">At least 8 characters.</p>
          </div>
          <Button type="submit" disabled={loading} className="mt-2">
            {loading ? "Creating account..." : "Create account"}
          </Button>
        </form>

        <p className="text-center text-sm text-on-surface-variant">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
