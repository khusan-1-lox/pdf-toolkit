"use client";

import type { ReactNode } from "react";

type LivePreviewProps = {
  thumb: string | null;
  overlay: ReactNode;
  label: string;
};

export function LivePreview({ thumb, overlay, label }: LivePreviewProps) {
  return (
    <div className="relative overflow-hidden rounded-[12px] border bg-white aspect-[3/4]">
      {thumb ? (
        <img
          src={thumb}
          alt={label}
          className="h-full w-full object-cover object-top"
          draggable={false}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-white/95 to-[rgba(10,132,255,0.07)]">
          <div className="text-center">
            <div className="text-[28px] font-semibold tracking-[-0.02em] text-[#1b1a17]">
              —
            </div>
            <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-[#9a9994]">
              превью
            </div>
          </div>
        </div>
      )}
      <div className="absolute inset-0 pointer-events-none">{overlay}</div>
      <span className="pointer-events-none absolute bottom-1.5 left-1.5 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
        {label}
      </span>
    </div>
  );
}

export default LivePreview;
