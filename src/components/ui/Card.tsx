"use client";

import { type ReactNode } from "react";

type CardVariant = "default" | "elevated" | "bordered";

interface CardProps {
  children: ReactNode;
  variant?: CardVariant;
  className?: string;
  onClick?: () => void;
}

const variantStyles: Record<CardVariant, string> = {
  default: "bg-white shadow-sm",
  elevated: "bg-white shadow-lg hover:shadow-xl transition-shadow duration-[var(--transition-normal)]",
  bordered: "bg-white border border-[var(--color-gray-200)]",
};

export function Card({ children, variant = "default", className = "", onClick }: CardProps) {
  return (
    <div
      className={`
        rounded-[var(--radius-xl)]
        ${variantStyles[variant]}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-6 py-4 border-b border-[var(--color-gray-100)] ${className}`}>{children}</div>;
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-6 py-4 ${className}`}>{children}</div>;
}

export function CardFooter({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-6 py-4 border-t border-[var(--color-gray-100)] ${className}`}>{children}</div>;
}
