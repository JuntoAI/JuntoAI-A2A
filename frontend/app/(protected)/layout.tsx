"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/context/SessionContext";
import { isLocalMode } from "@/lib/runMode";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isHydrated } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isLocalMode && isHydrated && !isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, isHydrated, router]);

  if (!isLocalMode && (!isHydrated || !isAuthenticated)) {
    return null;
  }

  return <>{children}</>;
}
