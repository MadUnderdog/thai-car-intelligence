"use client";

import { useState } from "react";
import Link from "next/link";

const navLinks = [
  { href: "/", label: "หน้าแรก" },
  { href: "/cars", label: "รถยนต์" },
  { href: "/search", label: "ค้นหา" },
  { href: "/compare", label: "เปรียบเทียบ" },
  { href: "/ai-ask", label: "ถาม AI" },
];

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-[var(--z-sticky)] bg-white/80 backdrop-blur-md border-b border-[var(--color-gray-200)]">
      <div className="container-wide">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 font-bold text-xl text-[var(--color-gray-900)]">
            <span className="w-8 h-8 bg-[var(--color-primary-600)] rounded-[var(--radius-lg)] flex items-center justify-center text-white text-sm">
              🚗
            </span>
            <span className="hidden sm:inline">Car Intelligence</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="px-4 py-2 text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-gray-900)] hover:bg-[var(--color-gray-100)] rounded-[var(--radius-lg)] transition-all duration-[var(--transition-normal)]"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 text-[var(--color-gray-600)] hover:bg-[var(--color-gray-100)] rounded-[var(--radius-lg)]"
            aria-label={mobileOpen ? "ปิดเมนู" : "เปิดเมนู"}
          >
            {mobileOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <nav className="md:hidden py-4 border-t border-[var(--color-gray-100)]">
            <div className="flex flex-col gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="px-4 py-3 text-sm font-medium text-[var(--color-gray-700)] hover:bg-[var(--color-gray-100)] rounded-[var(--radius-lg)]"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
