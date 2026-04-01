"use client";

import { type ReactNode } from "react";
import { SessionProvider } from "@/context/SessionContext";

export default function Providers({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
