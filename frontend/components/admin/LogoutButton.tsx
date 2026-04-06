"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogOut } from "lucide-react";

export function LogoutButton() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  async function handleLogout() {
    setIsLoading(true);
    try {
      await fetch("/api/v1/admin/logout", { method: "POST" });
    } catch {
      // Even if the API call fails, redirect to login
    }
    router.push("/admin/login");
  }

  return (
    <button
      onClick={handleLogout}
      disabled={isLoading}
      className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-gray-400 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-50"
    >
      <LogOut size={16} />
      {isLoading ? "Logging out…" : "Logout"}
    </button>
  );
}
