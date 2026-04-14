"use client";

import { useEffect } from "react";
import { useSession } from "@/context/SessionContext";

/**
 * Client component that sets persona="founder" in SessionContext on mount.
 * Rendered as a child of the /founders server page.
 */
export default function FoundersPersonaSetter() {
  const { setPersona } = useSession();

  useEffect(() => {
    setPersona("founder");
  }, [setPersona]);

  return null;
}
