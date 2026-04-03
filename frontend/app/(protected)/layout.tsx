"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/context/SessionContext";
import { isLocalMode } from "@/lib/runMode";
import TokenDisplay from "@/components/TokenDisplay";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isHydrated, email, logout } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isLocalMode && isHydrated && !isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, isHydrated, router]);

  if (!isLocalMode && (!isHydrated || !isAuthenticated)) {
    return null;
  }

  const handleLogout = () => {
    logout();
    router.replace("/");
  };

  return (
    <>
      <div className="flex items-center justify-end gap-3 p-4">
        <span className="truncate max-w-[220px] text-sm text-gray-600" title={email ?? ""}>
          {email}
        </span>
        <TokenDisplay />
        {!isLocalMode && (
          <button
            onClick={handleLogout}
            className="rounded-md px-3 py-1 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            Logout
          </button>
        )}
      </div>
      {children}
    </>
  );
}
