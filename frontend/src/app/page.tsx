"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading } from "@/components/ui/Loading";
import { useAuth } from "@/lib/auth";

export default function IndexPage() {
  const { apiKey, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    router.replace(apiKey ? "/evaluate" : "/login");
  }, [ready, apiKey, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loading label="Kernl Console" />
    </div>
  );
}
