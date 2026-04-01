"use client";

export interface InformationToggleProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (id: string, checked: boolean) => void;
}

export function InformationToggle({
  id,
  label,
  checked,
  onChange,
}: InformationToggleProps) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 shadow-sm transition-colors hover:border-brand-blue/40"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(id, e.target.checked)}
        className="h-4 w-4 rounded border-gray-300 text-brand-blue focus:ring-brand-blue"
      />
      {label}
    </label>
  );
}
