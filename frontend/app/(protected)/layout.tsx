"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/context/SessionContext";
import TokenDisplay from "@/components/TokenDisplay";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, email } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <>
      <div className="flex items-center justify-end gap-3 p-4">
        <span className="truncate max-w-[220px] text-sm text-gray-600" title={email ?? ""}>
          {email}
        </span>
        <TokenDisplay />
      </div>
      {children}
    </>
  );
}
