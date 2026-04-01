"use client";

export interface InitializeButtonProps {
  onClick: () => void;
  disabled: boolean;
  isLoading: boolean;
  insufficientTokens: boolean;
}

export function InitializeButton({
  onClick,
  disabled,
  isLoading,
  insufficientTokens,
}: InitializeButtonProps) {
  const isDisabled = disabled || isLoading || insufficientTokens;

  return (
    <div className="w-full">
      <button
        type="button"
        onClick={onClick}
        disabled={isDisabled}
        className="w-full rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-brand-blue/50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? (
          <span className="inline-flex items-center gap-2">
            <svg
              className="h-4 w-4 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Initializing…
          </span>
        ) : (
          "Initialize A2A Protocol"
        )}
      </button>
      {insufficientTokens && (
        <p className="mt-2 text-center text-sm text-red-600" role="alert">
          Insufficient tokens — resets at midnight UTC
        </p>
      )}
    </div>
  );
}
