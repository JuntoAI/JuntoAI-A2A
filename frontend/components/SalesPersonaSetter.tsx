"use client";

import { useEffect } from "react";
import { useSession } from "@/context/SessionContext";

/**
 * Client component that sets persona="sales" in SessionContext on mount.
 * Rendered as a child of the / (sales) server page.
 */
export default function SalesPersonaSetter() {
  const { setPersona } = useSession();

  useEffect(() => {
    setPersona("sales");
  }, [setPersona]);

  return null;
}
