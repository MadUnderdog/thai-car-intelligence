"use client";

import { useState } from "react";

type SafeImageProps = {
  src: string;
  alt: string;
  className?: string;
  fallback?: React.ReactNode;
};

export default function SafeImage({ src, alt, className, fallback }: SafeImageProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div className={className} style={{ display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#f3f4f6" }}>
        {fallback || <span style={{ fontSize: "2rem" }}>🚗</span>}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
}
