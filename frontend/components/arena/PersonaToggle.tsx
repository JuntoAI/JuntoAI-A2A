"use client";

import type { Persona } from "@/context/SessionContext";

export interface PersonaToggleProps {
  persona: Persona;
  onPersonaChange: (persona: "sales" | "founder") => void;
}

/**
 * Two-option segmented control for switching between Sales and Founders personas.
 * Styled to match the Arena UI with gray-900 background and brand-blue active state.
 */
export function PersonaToggle({ persona, onPersonaChange }: PersonaToggleProps) {
  const active = persona ?? "sales";

  return (
    <div
      className="inline-flex rounded-lg bg-gray-900 p-1"
      role="radiogroup"
      aria-label="Persona selector"
    >
      <button
        type="button"
        role="radio"
        aria-checked={active === "sales"}
        className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
          active === "sales"
            ? "bg-brand-blue text-white shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        }`}
        onClick={() => onPersonaChange("sales")}
      >
        Sales
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={active === "founder"}
        className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
          active === "founder"
            ? "bg-brand-blue text-white shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        }`}
        onClick={() => onPersonaChange("founder")}
      >
        Founders
      </button>
    </div>
  );
}
