"use client";

import { forwardRef, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = "", id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
    
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-[var(--color-gray-700)]">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            w-full px-3 py-2 text-sm
            bg-white border border-[var(--color-gray-300)]
            rounded-[var(--radius-lg)]
            placeholder:text-[var(--color-gray-400)]
            transition-all duration-[var(--transition-normal)]
            focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)] focus:border-transparent
            disabled:bg-[var(--color-gray-100)] disabled:cursor-not-allowed
            ${error ? "border-[var(--color-danger-500)] focus:ring-[var(--color-danger-500)]" : ""}
            ${className}
          `}
          {...props}
        />
        {error && <p className="text-xs text-[var(--color-danger-600)]">{error}</p>}
        {hint && !error && <p className="text-xs text-[var(--color-gray-500)]">{hint}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";
