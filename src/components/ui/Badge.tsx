"use client";

import { type ReactNode } from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";
type BadgeSize = "sm" | "md";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-[var(--color-gray-100)] text-[var(--color-gray-700)]",
  success: "bg-transparent text-[var(--color-success-700)] border border-[var(--color-success-500)]/40",
  warning: "bg-transparent text-[var(--color-warning-600)] border border-[var(--color-warning-500)]/40",
  danger: "bg-transparent text-[var(--color-danger-600)] border border-[var(--color-danger-500)]/40",
  info: "bg-transparent text-[var(--color-primary-700)] border border-[var(--color-primary-500)]/40",
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
};

export function Badge({ children, variant = "default", size = "sm", className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center font-medium rounded-[var(--radius-sm)] ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}>
      {children}
    </span>
  );
}
