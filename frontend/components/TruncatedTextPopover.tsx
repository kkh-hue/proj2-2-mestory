"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

type PopupPosition = { top: number; left: number };

export default function TruncatedTextPopover({
  text,
  className,
}: {
  text: string;
  className: string;
}) {
  const textRef = useRef<HTMLSpanElement>(null);
  const [isTruncated, setIsTruncated] = useState(false);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PopupPosition | null>(null);

  useLayoutEffect(() => {
    const element = textRef.current;
    if (!element) return;

    const measure = () => setIsTruncated(element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [text]);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!textRef.current?.parentElement?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const showPopup = () => {
    if (!isTruncated || !textRef.current) return;
    const rect = textRef.current.getBoundingClientRect();
    const popupWidth = Math.min(320, window.innerWidth - 24);
    setPosition({
      top: rect.bottom + 6,
      left: Math.max(12, Math.min(rect.left, window.innerWidth - popupWidth - 12)),
    });
    setOpen(true);
  };

  return (
    <>
      <span
        ref={textRef}
        className={`${className}${isTruncated ? " truncated-text-trigger" : ""}`}
        title={isTruncated ? undefined : text}
        role={isTruncated ? "button" : undefined}
        tabIndex={isTruncated ? 0 : undefined}
        onClick={isTruncated ? showPopup : undefined}
        onKeyDown={isTruncated ? (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); showPopup(); } } : undefined}
        aria-expanded={isTruncated ? open : undefined}
      >
        {text}
      </span>
      {open && position && (
        <span className="truncated-text-popover" role="tooltip" style={{ top: position.top, left: position.left }}>
          {text}
        </span>
      )}
    </>
  );
}
