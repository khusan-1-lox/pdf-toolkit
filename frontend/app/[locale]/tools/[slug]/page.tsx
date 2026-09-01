"use client";

import { useState, useEffect, useCallback } from "react";
import { DropZone, getAcceptForSlug } from "@/components/DropZone";
import { PositionGrid } from "@/components/PositionGrid";
import { StickyBar } from "@/components/StickyBar";
import { LivePreview } from "@/components/LivePreview";
import { FileList } from "@/components/FileList";
import { callTool, callCompare } from "@/lib/api";
import {Link} from "@/navigation";
import {useTranslations} from "next-intl";

import {
  DndContext,
  closestCenter,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  rectSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const TOOL_META_KEYS = ["merge","split","delete","compress","pdf-to-jpg","jpg-to-pdf","rotate","watermark","page-numbers","crop","protect","unlock","redact","sign","compare","organize-pdf","word-to-pdf","excel-to-pdf","ppt-to-pdf","pdf-to-word","pdf-to-excel","pdf-to-ppt","ocr-pdf","pdf-to-pdfa","html-to-pdf","repair-pdf","repair","pdfa"] as const;
const VALID_SLUGS = new Set(TOOL_META_KEYS as unknown as string[]);

type PageItem = {
  id: string;
  fileIndex: number;
  pageIndex: number;
  fileName: string;
  thumb?: string;
};

function filenameForSlug(slug: string, blobType: string): string {
  if (blobType.includes("zip")) return `${slug}.zip`;
  if (blobType.includes("pdf")) return `${slug}.pdf`;
  if (blobType.includes("jpeg") || blobType.includes("jpg")) return `${slug}.jpg`;
  return `result-${slug}`;
}

function positionToFlex(pos: string): string {
  switch (pos) {
    case "top-left":
      return "items-start justify-start";
    case "top-center":
      return "items-start justify-center";
    case "top-right":
      return "items-start justify-end";
    case "center-left":
      return "items-center justify-start";
    case "center":
      return "items-center justify-center";
    case "center-right":
      return "items-center justify-end";
    case "bottom-left":
      return "items-end justify-start";
    case "bottom-center":
      return "items-end justify-center";
    case "bottom-right":
      return "items-end justify-end";
    default:
      return "items-center justify-center";
  }
}

function serializePages(set: Set<number>): string {
  if (set.size === 0) return "";
  const sorted = Array.from(set).sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    const cur = sorted[i];
    if (cur === prev + 1) {
      prev = cur;
      continue;
    }
    if (start === prev) ranges.push(String(start));
    else ranges.push(`${start}-${prev}`);
    start = cur;
    prev = cur;
  }
  if (start === prev) ranges.push(String(start));
  else ranges.push(`${start}-${prev}`);
  return ranges.join(",");
}

function parsePagesToSet(pagesStr: string, total: number | null): Set<number> | null {
  try {
    const s = new Set<number>();
    const parts = pagesStr.split(",");
    for (const token of parts) {
      const t = token.trim();
      if (!t) return null;
      if (t.includes("-")) {
        const split = t.split("-");
        if (split.length !== 2) return null;
        const a = split[0].trim();
        const b = split[1].trim();
        if (!a || !b) return null;
        const start = parseInt(a, 10);
        const end = parseInt(b, 10);
        if (isNaN(start) || isNaN(end)) return null;
        if (start > end) return null;
        for (let p = start; p <= end; p++) s.add(p);
      } else {
        const n = parseInt(t, 10);
        if (isNaN(n)) return null;
        s.add(n);
      }
    }
    if (total !== null) {
      if (Array.from(s).some((n) => n < 1 || n > total)) return null;
    }
    if (s.size === 0) return null;
    return s;
  } catch {
    return null;
  }
}

function SortablePageCard({ item, position, onRemove }: { item: PageItem; position: number; onRemove?: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`group relative flex cursor-grab flex-col gap-2 rounded-[18px] p-2.5 text-left transition-all active:cursor-grabbing ${
        isDragging ? "z-10 opacity-70 ring-2 ring-[#0a84ff]/30" : "hover:shadow-[0_12px_40px_rgba(27,26,23,0.12)]"
      } glass ${isDragging ? "bg-white/90" : ""}`}
    >
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(item.id);
          }}
          onPointerDown={(e) => e.stopPropagation()}
          className="absolute right-1.5 top-1.5 z-10 inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-[#e30613] shadow-md ring-1 ring-black/10 opacity-0 transition-opacity hover:bg-[#fff1f1] group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto"
          aria-label={`╨г╨┤╨░╨╗╨╕╤В╤М ╤Б╤В╤А ${item.pageIndex + 1}`}
        >
          ╨г╨┤╨░╨╗╨╕╤В╤М
        </button>
      )}
      <div className="flex items-center justify-between px-1">
        <span className="glass-icon flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold tracking-wide text-[#1b1a17]">
          {position + 1}
        </span>
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/70 text-[#9a9994]">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="4" cy="4" r="1.2" />
            <circle cx="12" cy="4" r="1.2" />
            <circle cx="4" cy="8" r="1.2" />
            <circle cx="12" cy="8" r="1.2" />
            <circle cx="4" cy="12" r="1.2" />
            <circle cx="12" cy="12" r="1.2" />
          </svg>
        </span>
      </div>

      <div className="relative overflow-hidden rounded-[12px] border border-white/60 bg-white">
        {item.thumb ? (
          <img src={item.thumb} alt={`╨б╤В╤А. ${item.pageIndex + 1}`} className="aspect-[3/4] w-full object-cover object-top" draggable={false} />
        ) : (
          <div className="flex aspect-[3/4] items-center justify-center bg-gradient-to-br from-white/95 to-[rgba(10,132,255,0.07)]">
            <div className="text-center">
              <div className="text-[28px] font-semibold tracking-[-0.02em] text-[#1b1a17]">{item.pageIndex + 1}</div>
              <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-[#9a9994]">╤Б╤В╤А.</div>
            </div>
          </div>
        )}
        <span className="pointer-events-none absolute bottom-1.5 left-1.5 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">╤Б╤В╤А. {item.pageIndex + 1}</span>
      </div>

      <div className="min-w-0 px-1">
        <p className="truncate text-[11.5px] font-medium leading-tight text-[#1b1a17]">{item.fileName}</p>
        <p className="text-[11px] text-[#6b6a63]">╨д╨░╨╣╨╗ {item.fileIndex + 1}</p>
      </div>
    </div>
  );
}

function SelectablePageCard({
  pageNum,
  thumb,
  selected,
  onToggle,
}: {
  pageNum: number;
  thumb?: string;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`group relative flex flex-col gap-2 rounded-[18px] p-2.5 text-left transition-all glass ${
        selected ? "ring-2 ring-[#0a84ff]/50 bg-white/90 shadow-[0_12px_40px_rgba(27,26,23,0.12)]" : "hover:shadow-[0_12px_40px_rgba(27,26,23,0.08)]"
      }`}
    >
      <div className="flex items-center justify-between px-1">
        <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${selected ? "bg-[#0a84ff] text-white" : "glass-icon text-[#1b1a17]"}`}>{pageNum}</span>
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full border-2 transition ${
            selected ? "border-[#0a84ff] bg-[#0a84ff] text-white" : "border-black/10 bg-white/80"
          }`}
        >
          {selected && (
            <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2.5 6L5 8.5L9.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>
      </div>
      <div className="relative overflow-hidden rounded-[12px] border border-white/60 bg-white">
        {thumb ? (
          <img src={thumb} alt={`╨б╤В╤А. ${pageNum}`} className="aspect-[3/4] w-full object-cover object-top" draggable={false} />
        ) : (
          <div className="flex aspect-[3/4] items-center justify-center bg-gradient-to-br from-white/95 to-[rgba(10,132,255,0.07)]">
            <div className="text-center">
              <div className="text-[28px] font-semibold tracking-[-0.02em] text-[#1b1a17]">{pageNum}</div>
              <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-[#9a9994]">╤Б╤В╤А.</div>
            </div>
          </div>
        )}
        <span className="pointer-events-none absolute bottom-1.5 left-1.5 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">╤Б╤В╤А. {pageNum}</span>
      </div>
    </button>
  );
}

export default function ToolPage({ params }: { params: { slug: string, locale: string } }) {
  const slug = params.slug;
  const t = useTranslations("dashboard.tools");
  const te = useTranslations("errors");
  const tc = useTranslations("tool");
  const tCommon = useTranslations("common");
  const TOOL_META: Record<string, { title: string; description: string; multi: boolean }> = {
    merge: { title: t("merge.title"), description: t("merge.desc"), multi: true },
    split: { title: t("split.title"), description: t("split.desc"), multi: false },
    delete: { title: t("delete.title"), description: t("delete.desc"), multi: false },
    compress: { title: t("compress.title"), description: t("compress.desc"), multi: false },
    "pdf-to-jpg": { title: t("pdf-to-jpg.title"), description: t("pdf-to-jpg.desc"), multi: false },
    "jpg-to-pdf": { title: t("jpg-to-pdf.title"), description: t("jpg-to-pdf.desc"), multi: true },
    rotate: { title: t("rotate.title"), description: t("rotate.desc"), multi: true },
    watermark: { title: t("watermark.title"), description: t("watermark.desc"), multi: false },
    "page-numbers": { title: t("page-numbers.title"), description: t("page-numbers.desc"), multi: false },
    crop: { title: t("crop.title"), description: t("crop.desc"), multi: false },
    protect: { title: t("protect.title"), description: t("protect.desc"), multi: false },
    unlock: { title: t("unlock.title"), description: t("unlock.desc"), multi: false },
    redact: { title: t("redact.title"), description: t("redact.desc"), multi: false },
    sign: { title: t("sign.title"), description: t("sign.desc"), multi: false },
    compare: { title: t("compare.title"), description: t("compare.desc"), multi: false },
    "organize-pdf": { title: t("organize-pdf.title"), description: t("organize-pdf.desc"), multi: false },
    "word-to-pdf": { title: t("word-to-pdf.title"), description: t("word-to-pdf.desc"), multi: false },
    "excel-to-pdf": { title: t("excel-to-pdf.title"), description: t("excel-to-pdf.desc"), multi: false },
    "ppt-to-pdf": { title: t("ppt-to-pdf.title"), description: t("ppt-to-pdf.desc"), multi: false },
    "pdf-to-word": { title: t("pdf-to-word.title"), description: t("pdf-to-word.desc"), multi: false },
    "pdf-to-excel": { title: t("pdf-to-excel.title"), description: t("pdf-to-excel.desc"), multi: false },
    "pdf-to-ppt": { title: t("pdf-to-ppt.title"), description: t("pdf-to-ppt.desc"), multi: false },
    "ocr-pdf": { title: t("ocr-pdf.title"), description: t("ocr-pdf.desc"), multi: false },
    "pdf-to-pdfa": { title: t("pdf-to-pdfa.title"), description: t("pdf-to-pdfa.desc"), multi: false },
    "html-to-pdf": { title: t("html-to-pdf.title"), description: t("html-to-pdf.desc"), multi: false },
    "repair-pdf": { title: t("repair-pdf.title"), description: t("repair-pdf.desc"), multi: false },
    repair: { title: t("repair-pdf.title"), description: t("repair-pdf.desc"), multi: false },
    pdfa: { title: t("pdf-to-pdfa.title"), description: t("pdf-to-pdfa.desc"), multi: false },
  };

  function friendlyError(raw: string): string {
  let detail = raw;
  const trimmed = raw.trim();
  if (trimmed.startsWith("{")) {
    try {
      const obj = JSON.parse(trimmed);
      if (obj.detail) detail = String(obj.detail);
      else if (obj.message) detail = String(obj.message);
    } catch {
    }
  }
  const outOfRangeMatch = detail.match(/Page\s+(\d+)\s+out of range\s*\(file has\s+(\d+)\s+pages\)/i);
  if (outOfRangeMatch) {
    return te("pageOutOfRange", {page: outOfRangeMatch[1], n: outOfRangeMatch[2]});
  }
  if (/Page out of range/i.test(detail)) {
    const nMatch = detail.match(/file has\s+(\d+)/i);
    if (nMatch) return te("pageOutOfRange", {page: "?", n: nMatch[1]});
    return te("pageOutOfRangeGeneric");
  }
  if (/Invalid pages format/i.test(detail)) return te("invalidPagesFormat");
  if (/Invalid page range/i.test(detail)) return te("invalidRange");
  if (/No valid pages/i.test(detail)) return te("noValidPages");
  if (/pages parameter required/i.test(detail)) return te("pagesRequired");
  if (/Cannot delete all pages/i.test(detail)) return te("cannotDeleteAll");
  if (/Encrypted PDF/i.test(detail)) return te("encryptedPdf");
  if (/Invalid PDF/i.test(detail)) return te("invalidPdf");
  if (/PDF has no pages/i.test(detail)) return te("pdfNoPages");
  if (/File too large/i.test(detail)) return te("fileTooLarge");
  if (/Empty file/i.test(detail)) return te("emptyFile");
  if (/Crop margins too large/i.test(detail)) return te("cropMarginsTooLarge");
  if (/Crop rect out of bounds/i.test(detail)) return te("cropRectOutOfBounds");
  if (/Crop rect too small/i.test(detail)) return te("cropRectTooSmall");
  if (/No crop margins provided/i.test(detail)) return te("noCropMargins");
  if (/No crop rect/i.test(detail)) return te("noCropRect");
  if (/Invalid top|Invalid bottom|Invalid left|Invalid right|Invalid x|Invalid y|Invalid w|Invalid h/i.test(detail)) return te("invalidCropParams");
  if (/Invalid mode/i.test(detail)) return te("invalidMode");
  if (/Invalid unit/i.test(detail)) return te("invalidUnit");
  if (/user_password required/i.test(detail)) return te("userPasswordRequired");
  if (/password required/i.test(detail)) return te("passwordRequired");
  if (/Invalid password/i.test(detail)) return te("invalidPassword");
  if (/No texts or hide_images/i.test(detail)) return te("noTextsOrImages");
  if (/At least text or image required/i.test(detail)) return te("textOrImageRequired");
  if (/Invalid position/i.test(detail)) return te("invalidPosition");
  if (/Invalid opacity/i.test(detail)) return te("invalidOpacity");
  if (/Two files required/i.test(detail)) return te("twoFilesRequired");
  if (/Sign rect out of bounds/i.test(detail)) return te("signRectOutOfBounds");
  return detail;
}


  if (!VALID_SLUGS.has(slug)) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          тЖР ╨Э╨░╨╖╨░╨┤
        </Link>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <h1 className="text-lg font-semibold text-red-800">Unknown tool: {slug}</h1>
          <p className="mt-1 text-sm text-red-600">Available: {Object.keys(TOOL_META).join(", ")}</p>
        </div>
      </div>
    );
  }

  const meta = TOOL_META[slug];
  const isMulti = meta.multi;

  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");

  // per-tool opts
  const [pages, setPages] = useState("1,3-5");
  const [quality, setQuality] = useState("medium");
  const [angle, setAngle] = useState("90");
  const [pdfToJpgDpi, setPdfToJpgDpi] = useState("150");
  const [jpgToPdfOrientation, setJpgToPdfOrientation] = useState("portrait");
  const [jpgToPdfPageSize, setJpgToPdfPageSize] = useState("A4");
  const [jpgToPdfMargin, setJpgToPdfMargin] = useState("medium");

  // watermark opts
  const [wmText, setWmText] = useState("╨Ю╨▒╤А╨░╨╖╨╡╤Ж");
  const [wmImage, setWmImage] = useState<File | null>(null);
  const [wmPosition, setWmPosition] = useState("center");
  const [wmOpacity, setWmOpacity] = useState(30);
  const [wmFontSize, setWmFontSize] = useState("36");
  const [wmColor, setWmColor] = useState("#C8C8C8");
  const [wmRotation, setWmRotation] = useState("45");
  const [wmTiling, setWmTiling] = useState(false);
  const [wmFontFamily, setWmFontFamily] = useState("Helvetica");

  // page-numbers opts
  const [pnPosition, setPnPosition] = useState("bottom-center");
  const [pnFormat, setPnFormat] = useState("1");
  const [pnFontSize, setPnFontSize] = useState("12");
  const [pnColor, setPnColor] = useState("#000000");
  const [pnMarginX, setPnMarginX] = useState("20");
  const [pnMarginY, setPnMarginY] = useState("20");
  const [pnStart, setPnStart] = useState("1");
  const [pnPreview, setPnPreview] = useState<{ numPages: number; pages: { page: number; thumb: string }[] } | null>(null);
  const [pnPreviewLoading, setPnPreviewLoading] = useState(false);

  // crop opts
  const [cropMode, setCropMode] = useState<"margins" | "rect">("margins");
  const [cropUnit, setCropUnit] = useState<"mm" | "pt">("mm");
  const [cropTop, setCropTop] = useState("10");
  const [cropBottom, setCropBottom] = useState("10");
  const [cropLeft, setCropLeft] = useState("10");
  const [cropRight, setCropRight] = useState("10");
  const [cropX, setCropX] = useState("0");
  const [cropY, setCropY] = useState("0");
  const [cropW, setCropW] = useState("200");
  const [cropH, setCropH] = useState("200");
  const [cropPages, setCropPages] = useState("all");
  const [cropPreview, setCropPreview] = useState<{ numPages: number; pages: { page: number; thumb: string }[] } | null>(null);
  const [cropPreviewLoading, setCropPreviewLoading] = useState(false);

  // protect
  const [protectPass, setProtectPass] = useState("");
  const [protectOwnerPass, setProtectOwnerPass] = useState("");
  const [protectAllowPrint, setProtectAllowPrint] = useState(true);
  const [protectAllowCopy, setProtectAllowCopy] = useState(true);
  const [protectAllowModify, setProtectAllowModify] = useState(true);
  const [protectAllowAnnotate, setProtectAllowAnnotate] = useState(true);
  // unlock
  const [unlockPass, setUnlockPass] = useState("");
  // redact
  const [redactTexts, setRedactTexts] = useState("╤Б╨╡╨║╤А╨╡╤В, ╨║╨╛╨╜╤Д╨╕╨┤╨╡╨╜╤Ж╨╕╨░╨╗╤М╨╜╨╛");
  const [redactHideImages, setRedactHideImages] = useState(false);
  // sign
  const [signImage, setSignImage] = useState<File | null>(null);
  const [signPosition, setSignPosition] = useState("bottom-right");
  const [signOpacity, setSignOpacity] = useState(80);
  const [signPage, setSignPage] = useState("all");
  const [signX, setSignX] = useState("");
  const [signY, setSignY] = useState("");
  const [signW, setSignW] = useState("");
  const [signH, setSignH] = useState("");
  const [signPreview, setSignPreview] = useState<{ numPages: number; pages: { page: number; thumb: string }[] } | null>(null);
  const [signPreviewLoading, setSignPreviewLoading] = useState(false);
  const [signThumbUrl, setSignThumbUrl] = useState<string | null>(null);
  // compare
  const [compareFile1, setCompareFile1] = useState<File | null>(null);
  const [compareFile2, setCompareFile2] = useState<File | null>(null);
  const [compareResult, setCompareResult] = useState<{ pages: { index: number; diff: boolean; left_thumb: string; right_thumb: string; left_text: string; right_text: string }[] } | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  // merge page-level reorder state
  const [pageItems, setPageItems] = useState<PageItem[]>([]);
  const [pagesLoading, setPagesLoading] = useState(false);

  // split/delete preview + visual selector
  const [preview, setPreview] = useState<{ numPages: number; pages: { page: number; thumb: string }[] } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } })
  );

  // Build pageItems from files via server-side PyMuPDF preview (robust, no pdfjs) for merge
  useEffect(() => {
    if (slug !== "merge") {
      setPageItems([]);
      return;
    }
    if (files.length === 0) {
      setPageItems([]);
      return;
    }
    let cancelled = false;
    async function build() {
      setPagesLoading(true);
      try {
        const expanded: PageItem[] = [];
        for (let fi = 0; fi < files.length; fi++) {
          const file = files[fi];
          const isPdf = file.type.includes("pdf") || file.name.toLowerCase().endsWith(".pdf");
          if (!isPdf) {
            // images: local object URL
            let thumb: string | undefined;
            try {
              thumb = URL.createObjectURL(file);
            } catch {}
            expanded.push({ id: `${fi}-0`, fileIndex: fi, pageIndex: 0, fileName: file.name, thumb });
            continue;
          }
          // PDF: fetch server-side thumbnail via /api/preview (PyMuPDF)
          try {
            const fd = new FormData();
            fd.append("file", file);
            const resp = await fetch("/api/preview", { method: "POST", body: fd });
            if (!resp.ok) {
              const txt = await resp.text().catch(() => "");
              console.error("preview failed", file.name, resp.status, txt);
              throw new Error(txt || `preview ${resp.status}`);
            }
            const data: { pages: { page: number; thumb: string }[]; numPages: number } = await resp.json();
            const pages = data.pages || [];
            if (pages.length === 0) {
              // fallback: at least one placeholder card (will show blue number)
              expanded.push({ id: `${fi}-0`, fileIndex: fi, pageIndex: 0, fileName: file.name });
            } else {
              for (const p of pages) {
                if (cancelled) break;
                expanded.push({ id: `${fi}-${p.page}`, fileIndex: fi, pageIndex: p.page, fileName: file.name, thumb: p.thumb });
              }
            }
          } catch (e) {
            console.error("preview error for", file.name, e);
            // keep single card without thumb as fallback (placeholder)
            expanded.push({ id: `${fi}-0`, fileIndex: fi, pageIndex: 0, fileName: file.name });
          }
          if (cancelled) break;
        }

        if (cancelled) return;

        setPageItems((prev) => {
          if (prev.length === 0) return expanded;
          const newIdSet = new Set(expanded.map((e) => e.id));
          const prevFiltered = prev.filter((p) => newIdSet.has(p.id)).map((p) => {
            const fresh = expanded.find((m) => m.id === p.id);
            // prefer fresh thumb from server; keep old if fresh missing
            if (fresh?.thumb) return { ...p, thumb: fresh.thumb };
            return p;
          });
          const prevIdSet = new Set(prev.map((p) => p.id));
          const appended = expanded.filter((e) => !prevIdSet.has(e.id));
          if (prevFiltered.length + appended.length !== expanded.length) return expanded;
          return [...prevFiltered, ...appended];
        });
      } finally {
        if (!cancelled) setPagesLoading(false);
      }
    }
    build();
    return () => {
      cancelled = true;
    };
  }, [files, slug]);

  // Preview for split/delete/watermark (single file) тАУ Task2 LivePreview
  useEffect(() => {
    if (slug !== "split" && slug !== "delete" && slug !== "watermark") {
      setPreview(null);
      return;
    }
    if (files.length === 0) {
      setPreview(null);
      setSelectedPages(new Set());
      setPreviewLoading(false);
      return;
    }
    const file = files[0];
    let cancelled = false;
    async function loadPreview() {
      setPreviewLoading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const resp = await fetch("/api/preview", { method: "POST", body: fd });
        if (!resp.ok) {
          if (!cancelled) setPreview(null);
          return;
        }
        const data: { pages: { page: number; thumb: string }[]; numPages: number } = await resp.json();
        if (cancelled) return;
        setPreview({ numPages: data.numPages, pages: data.pages || [] });
        // try to sync selectedPages from current pages input if valid
        const parsed = parsePagesToSet(pages, data.numPages);
        if (parsed && parsed.size > 0) {
          // filter to valid range (already)
          setSelectedPages(parsed);
        }
      } catch (e) {
        console.error("preview error", e);
        if (!cancelled) setPreview(null);
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    }
    loadPreview();
    return () => {
      cancelled = true;
    };
    // only re-run when file changes; pages intentionally not in deps to avoid loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, slug]);

  // Preview for page-numbers
  useEffect(() => {
    if (slug !== "page-numbers") {
      setPnPreview(null);
      return;
    }
    if (files.length === 0) {
      setPnPreview(null);
      setPnPreviewLoading(false);
      return;
    }
    const file = files[0];
    let cancelled = false;
    async function loadPnPreview() {
      setPnPreviewLoading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const resp = await fetch("/api/preview", { method: "POST", body: fd });
        if (!resp.ok) {
          if (!cancelled) setPnPreview(null);
          return;
        }
        const data: { pages: { page: number; thumb: string }[]; numPages: number } = await resp.json();
        if (cancelled) return;
        setPnPreview({ numPages: data.numPages, pages: data.pages || [] });
      } catch (e) {
        console.error("pn preview error", e);
        if (!cancelled) setPnPreview(null);
      } finally {
        if (!cancelled) setPnPreviewLoading(false);
      }
    }
    loadPnPreview();
    return () => {
      cancelled = true;
    };
  }, [files, slug]);

  // Preview for crop
  useEffect(() => {
    if (slug !== "crop") {
      setCropPreview(null);
      return;
    }
    if (files.length === 0) {
      setCropPreview(null);
      setCropPreviewLoading(false);
      return;
    }
    const file = files[0];
    let cancelled = false;
    async function loadCropPreview() {
      setCropPreviewLoading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const resp = await fetch("/api/preview", { method: "POST", body: fd });
        if (!resp.ok) {
          if (!cancelled) setCropPreview(null);
          return;
        }
        const data: { pages: { page: number; thumb: string }[]; numPages: number } = await resp.json();
        if (cancelled) return;
        setCropPreview({ numPages: data.numPages, pages: data.pages || [] });
      } catch (e) {
        console.error("crop preview error", e);
        if (!cancelled) setCropPreview(null);
      } finally {
        if (!cancelled) setCropPreviewLoading(false);
      }
    }
    loadCropPreview();
    return () => {
      cancelled = true;
    };
  }, [files, slug]);

  // Preview for sign тАУ Task2 LivePreview
  useEffect(() => {
    if (slug !== "sign") {
      setSignPreview(null);
      return;
    }
    if (files.length === 0) {
      setSignPreview(null);
      setSignPreviewLoading(false);
      return;
    }
    const file = files[0];
    let cancelled = false;
    async function loadSignPreview() {
      setSignPreviewLoading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const resp = await fetch("/api/preview", { method: "POST", body: fd });
        if (!resp.ok) {
          if (!cancelled) setSignPreview(null);
          return;
        }
        const data: { pages: { page: number; thumb: string }[]; numPages: number } = await resp.json();
        if (cancelled) return;
        setSignPreview({ numPages: data.numPages, pages: data.pages || [] });
      } catch (e) {
        console.error("sign preview error", e);
        if (!cancelled) setSignPreview(null);
      } finally {
        if (!cancelled) setSignPreviewLoading(false);
      }
    }
    loadSignPreview();
    return () => {
      cancelled = true;
    };
  }, [files, slug]);

  // signThumbUrl object URL handling
  useEffect(() => {
    if (!signImage) {
      setSignThumbUrl(null);
      return;
    }
    const url = URL.createObjectURL(signImage);
    setSignThumbUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [signImage]);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setPageItems((prev) => {
        const oldIdx = prev.findIndex((p) => p.id === active.id);
        const newIdx = prev.findIndex((p) => p.id === over.id);
        if (oldIdx === -1 || newIdx === -1) return prev;
        return arrayMove(prev, oldIdx, newIdx);
      });
    }
  }, []);

  const handleResetOrder = useCallback(() => {
    setPageItems((prev) => {
      // sort by natural fileIndex, pageIndex
      const sorted = [...prev].sort((a, b) => a.fileIndex - b.fileIndex || a.pageIndex - b.pageIndex);
      return sorted;
    });
  }, []);

  // revoke previous blob URL when replaced or unmounted
  useEffect(() => {
    return () => {
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    };
  }, [downloadUrl]);

  const revokeDownload = useCallback(() => {
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl);
      setDownloadUrl(null);
    }
  }, [downloadUrl]);

  const handleFiles = useCallback(
    (incoming: File[]) => {
      setError(null);
      revokeDownload();
      if (isMulti) {
        // append, cap 10
        setFiles((prev) => {
          const combined = [...prev, ...incoming];
          if (combined.length > 10) {
            setError("Max 10 files per request");
            return combined.slice(0, 10);
          }
          return combined;
        });
      } else {
        // single-file tools: replace with last file
        setFiles(incoming.slice(-1));
      }
    },
    [isMulti, revokeDownload]
  );

  const handleRemove = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    setError(null);
    revokeDownload();
  };

  const handlePagesInputChange = (value: string) => {
    setPages(value);
    if (preview && preview.numPages) {
      const parsed = parsePagesToSet(value, preview.numPages);
      if (parsed) {
        setSelectedPages(parsed);
      } else if (value.trim() === "") {
        setSelectedPages(new Set());
      }
      // if invalid, keep previous selection (don't clear) to avoid flicker
    }
  };

  const handleTogglePage = (pageNum: number) => {
    setSelectedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNum)) next.delete(pageNum);
      else next.add(pageNum);
      const serialized = serializePages(next);
      setPages(serialized);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (!preview) return;
    const all = new Set<number>();
    for (let i = 1; i <= preview.numPages; i++) all.add(i);
    setSelectedPages(all);
    setPages(serializePages(all));
  };

  const handleClearSelection = () => {
    setSelectedPages(new Set());
    setPages("");
  };

  const handleCompareProcess = async () => {
    if (!compareFile1 || !compareFile2) {
      setError(friendlyError(JSON.stringify({ detail: "Two files required" })));
      return;
    }
    setCompareLoading(true);
    setError(null);
    setCompareResult(null);
    try {
      const data = await callCompare(compareFile1, compareFile2);
      setCompareResult(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(friendlyError(msg || "Processing failed"));
    } finally {
      setCompareLoading(false);
    }
  };

  const handleProcess = async () => {
    if (slug === "compare") {
      await handleCompareProcess();
      return;
    }
    if (files.length === 0) {
      setError("Add at least one file");
      return;
    }
    // validate per-tool required opts
    const opts: Record<string, unknown> = {};
    if (slug === "split" || slug === "delete") {
      if (!pages.trim()) {
        setError(friendlyError(JSON.stringify({ detail: "pages parameter required" })));
        return;
      }
      // client-side validation if we know numPages
      if (preview && preview.numPages) {
        const n = preview.numPages;
        const parts = pages.split(",");
        for (const token of parts) {
          const t = token.trim();
          if (!t) {
            setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж. ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ ╤Д╨╛╤А╨╝╨░╤В 1,3-5`);
            return;
          }
          if (t.includes("-")) {
            const dashIdx = t.indexOf("-");
            const sStr = t.slice(0, dashIdx).trim();
            const eStr = t.slice(dashIdx + 1).trim();
            if (!sStr || !eStr) {
              setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж. ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ ╤Д╨╛╤А╨╝╨░╤В 1,3-5`);
              return;
            }
            const s = Number(sStr);
            const e = Number(eStr);
            if (!Number.isInteger(s) || !Number.isInteger(e)) {
              setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж. ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ ╤Д╨╛╤А╨╝╨░╤В 1,3-5`);
              return;
            }
            if (s < 1 || e < 1 || s > n || e > n) {
              const bad = s < 1 || s > n ? s : e;
              setError(`╨б╤В╤А╨░╨╜╨╕╤Ж╨░ ${bad} ╨▓╨╜╨╡ ╨┤╨╕╨░╨┐╨░╨╖╨╛╨╜╨░. ╨Т ╤Д╨░╨╣╨╗╨╡ ${n} ╤Б╤В╤А╨░╨╜╨╕╤Ж тАФ ╨▓╨▓╨╡╨┤╨╕ 1..${n} (╨╜╨░╨┐╤А╨╕╨╝╨╡╤А 1,3-5)`);
              return;
            }
            if (s > e) {
              setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╨┤╨╕╨░╨┐╨░╨╖╨╛╨╜ тАФ ╨╜╨░╤З╨░╨╗╨╛ ╨▒╨╛╨╗╤М╤И╨╡ ╨║╨╛╨╜╤Ж╨░ (╨╜╨░╨┐╤А╨╕╨╝╨╡╤А 5-3).`);
              return;
            }
          } else {
            const num = Number(t);
            if (!Number.isInteger(num)) {
              setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж. ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ ╤Д╨╛╤А╨╝╨░╤В 1,3-5`);
              return;
            }
            if (num < 1 || num > n) {
              setError(`╨б╤В╤А╨░╨╜╨╕╤Ж╨░ ${num} ╨▓╨╜╨╡ ╨┤╨╕╨░╨┐╨░╨╖╨╛╨╜╨░. ╨Т ╤Д╨░╨╣╨╗╨╡ ${n} ╤Б╤В╤А╨░╨╜╨╕╤Ж тАФ ╨▓╨▓╨╡╨┤╨╕ 1..${n} (╨╜╨░╨┐╤А╨╕╨╝╨╡╤А 1,3-5)`);
              return;
            }
          }
        }
        if (slug === "delete") {
          const set = parsePagesToSet(pages, n);
          if (set && set.size >= n) {
            setError(`╨Э╨╡╨╗╤М╨╖╤П ╤Г╨┤╨░╨╗╨╕╤В╤М ╨▓╤Б╨╡ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л тАФ ╨╛╤Б╤В╨░╨▓╤М ╤Е╨╛╤В╤П ╨▒╤Л ╨╛╨┤╨╜╤Г.`);
            return;
          }
        }
      }
      opts.pages = pages.trim();
    }
    if (slug === "compress") {
      opts.quality = quality;
    }
    if (slug === "rotate") {
      opts.angle = angle;
    }
    if (slug === "merge" && pageItems.length > 0) {
      const order = pageItems.map((p) => ({ file: p.fileIndex, page: p.pageIndex }));
      opts.order = JSON.stringify(order);
    }
    if (slug === "watermark") {
      const hasText = wmText.trim() !== "";
      const hasImg = wmImage !== null;
      if (!hasText && !hasImg) {
        setError("╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╤В╨╡╨║╤Б╤В ╨╕╨╗╨╕ ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╨┤╨╗╤П ╨▓╨╛╨┤╤П╨╜╨╛╨│╨╛ ╨╖╨╜╨░╨║╨░");
        return;
      }
      if (hasText) opts.text = wmText.trim();
      if (hasImg && wmImage) opts.image = wmImage;
      opts.position = wmPosition;
      opts.opacity = String(wmOpacity / 100);
      opts.fontSize = wmFontSize;
      opts.color = wmColor;
      opts.rotation = wmRotation;
      opts.tiling = wmTiling ? "true" : "false";
      opts.fontFamily = wmFontFamily;
    }
    if (slug === "page-numbers") {
      opts.position = pnPosition;
      opts.format = pnFormat;
      opts.fontSize = pnFontSize;
      opts.color = pnColor;
      opts.marginX = pnMarginX;
      opts.marginY = pnMarginY;
      opts.startNumber = pnStart;
    }
    if (slug === "crop") {
      opts.mode = cropMode;
      opts.pages = cropPages.trim() || "all";
      opts.unit = cropUnit;
      if (cropMode === "margins") {
        // validate at least one
        const hasAny = [cropTop, cropBottom, cropLeft, cropRight].some((v) => String(v).trim() !== "" && Number(String(v).replace(",", ".")) !== 0);
        if (!hasAny) {
          setError("╨г╨║╨░╨╢╨╕ ╤Е╨╛╤В╤П ╨▒╤Л ╨╛╨┤╨╜╨╛ ╨┐╨╛╨╗╨╡ ╨┤╨╗╤П ╨╛╨▒╤А╨╡╨╖╨║╨╕");
          return;
        }
        opts.top = cropTop;
        opts.bottom = cropBottom;
        opts.left = cropLeft;
        opts.right = cropRight;
      } else {
        if (!cropW.trim() || !cropH.trim()) {
          setError("╨г╨║╨░╨╢╨╕ ╤И╨╕╤А╨╕╨╜╤Г ╨╕ ╨▓╤Л╤Б╨╛╤В╤Г ╨╛╨▒╨╗╨░╤Б╤В╨╕");
          return;
        }
        const wNum = Number(String(cropW).replace(",", "."));
        const hNum = Number(String(cropH).replace(",", "."));
        if (isNaN(wNum) || isNaN(hNum) || wNum <= 0 || hNum <= 0) {
          setError("╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╡ ╤А╨░╨╖╨╝╨╡╤А╤Л ╨╛╨▒╨╗╨░╤Б╤В╨╕");
          return;
        }
        opts.x = cropX;
        opts.y = cropY;
        opts.w = cropW;
        opts.h = cropH;
      }
      // client pages validation if not all
      if (opts.pages !== "all" && cropPreview && cropPreview.numPages) {
        const n = cropPreview.numPages;
        const parsed = parsePagesToSet(String(opts.pages), n);
        if (!parsed) {
          setError(`╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж. ╨Т ╤Д╨░╨╣╨╗╨╡ ${n} ╤Б╤В╤А╨░╨╜╨╕╤Ж тАФ ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ all ╨╕╨╗╨╕ 1,3-5`);
          return;
        }
      }
    }
    if (slug === "protect") {
      if (!protectPass.trim()) {
        setError(friendlyError(JSON.stringify({ detail: "user_password required" })));
        return;
      }
      opts.user_password = protectPass.trim();
      if (protectOwnerPass.trim()) opts.owner_password = protectOwnerPass.trim();
      opts.allow_print = String(protectAllowPrint);
      opts.allow_copy = String(protectAllowCopy);
      opts.allow_modify = String(protectAllowModify);
      opts.allow_annotate = String(protectAllowAnnotate);
      // also send as generic print/copy for backend flexibility
      opts.print = String(protectAllowPrint);
      opts.copy = String(protectAllowCopy);
    }
    if (slug === "unlock") {
      if (!unlockPass.trim()) {
        setError(friendlyError(JSON.stringify({ detail: "password required" })));
        return;
      }
      opts.password = unlockPass.trim();
    }
    if (slug === "redact") {
      const hasTexts = redactTexts.trim() !== "";
      if (!hasTexts && !redactHideImages) {
        setError(friendlyError(JSON.stringify({ detail: "No texts or hide_images provided" })));
        return;
      }
      if (hasTexts) opts.texts = redactTexts.trim();
      opts.hide_images = String(redactHideImages);
      opts.redact_images = String(redactHideImages);
    }
    if (slug === "sign") {
      if (!signImage) {
        setError("╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨╕");
        return;
      }
      opts.image = signImage;
      opts.position = signPosition;
      opts.opacity = String(signOpacity / 100);
      opts.page = signPage.trim() || "all";
      // if using explicit xywh mode: send if user filled
      if (signX.trim() && signY.trim() && signW.trim() && signH.trim()) {
        opts.x = signX.trim();
        opts.y = signY.trim();
        opts.w = signW.trim();
        opts.h = signH.trim();
      }
    }
    if (slug === "pdf-to-jpg") {
      opts.dpi = pdfToJpgDpi;
    }
    if (slug === "jpg-to-pdf") {
      opts.orientation = jpgToPdfOrientation;
      opts.pageSize = jpgToPdfPageSize;
      opts.margin = jpgToPdfMargin;
    }

    setLoading(true);
    setError(null);
    revokeDownload();

    try {
      const blob = await callTool(slug, files, opts);
      // revoke previous if any
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      setDownloadName(filenameForSlug(slug, blob.type));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(friendlyError(msg || "Processing failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    // trigger via temporary link to ensure filename
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // auto-revoke after click per spec (delay to let browser start)
    setTimeout(() => {
      URL.revokeObjectURL(downloadUrl);
      setDownloadUrl(null);
    }, 1000);
  };

  // helper to get thumb for page number 1-indexed
  const getThumbForPage = (pageNum: number): string | undefined => {
    if (!preview) return undefined;
    const found = preview.pages.find((p) => p.page === pageNum - 1);
    return found?.thumb || undefined;
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link href="/" className="inline-block text-sm text-blue-600 hover:underline">
        тЖР Dashboard
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-gray-900">{meta.title}</h1>
        <p className="mt-1 text-sm text-gray-600">{meta.description}</p>
      </div>

      {slug === "compare" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-medium text-[#1b1a17]">╨д╨░╨╣╨╗ 1 (╤Б╨╗╨╡╨▓╨░)</p>
            <DropZone onFiles={(f) => { setCompareFile1(f[0] || null); setError(null); setCompareResult(null); }} maxFiles={1} />
            {compareFile1 && (
              <div className="glass flex items-center justify-between rounded-[12px] px-3 py-2 text-xs">
                <span className="truncate font-medium text-[#1b1a17]">{compareFile1.name}</span>
                <button type="button" onClick={() => setCompareFile1(null)} className="ml-2 rounded-full border border-black/10 bg-white px-2 py-0.5 text-xs hover:bg-gray-50">╨г╨┤╨░╨╗╨╕╤В╤М</button>
              </div>
            )}
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-[#1b1a17]">╨д╨░╨╣╨╗ 2 (╤Б╨┐╤А╨░╨▓╨░)</p>
            <DropZone onFiles={(f) => { setCompareFile2(f[0] || null); setError(null); setCompareResult(null); }} maxFiles={1} />
            {compareFile2 && (
              <div className="glass flex items-center justify-between rounded-[12px] px-3 py-2 text-xs">
                <span className="truncate font-medium text-[#1b1a17]">{compareFile2.name}</span>
                <button type="button" onClick={() => setCompareFile2(null)} className="ml-2 rounded-full border border-black/10 bg-white px-2 py-0.5 text-xs hover:bg-gray-50">╨г╨┤╨░╨╗╨╕╤В╤М</button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <DropZone onFiles={handleFiles} maxFiles={10} accept={getAcceptForSlug(slug)} />
      )}

      {/* Merge: page-level reorder */}
      {slug === "merge" && files.length > 0 && (
        <div className="space-y-3">
          <div className="glass flex flex-col gap-1 rounded-[16px] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[13px] font-medium text-[#1b1a17]">╨Я╨╡╤А╨╡╤В╨░╤Й╨╕ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╤З╤В╨╛╨▒╤Л ╨╕╨╖╨╝╨╡╨╜╨╕╤В╤М ╨┐╨╛╤А╤П╨┤╨╛╨║ ╨║╨░╨║ ╨▓ ilovepdf</p>
              <p className="text-xs text-[#6b6a63]">
                {pagesLoading ? "╨Ч╨░╨│╤А╤Г╨╖╨║╨░ ╤Б╤В╤А╨░╨╜╨╕╤ЖтАж" : `${pageItems.length} ╤Б╤В╤А. ┬╖ ╨┐╨╡╤А╨╡╤В╨░╤Й╨╕ ╨║╨░╤А╤В╨╛╤З╨║╤Г ╤З╤В╨╛╨▒╤Л ╨┐╨╛╨╝╨╡╨╜╤П╤В╤М ╨┐╨╛╤А╤П╨┤╨╛╨║`}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  const el = document.querySelector<HTMLInputElement>('input[type="file"]');
                  if (el) el.click();
                  else window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                className="rounded-full bg-[#e30613] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#cc0510]"
              >
                ╨Ф╨╛╨▒╨░╨▓╨╕╤В╤М ╨╡╤Й╨╡ ╤Д╨░╨╣╨╗╤Л
              </button>
              <button
                type="button"
                onClick={handleResetOrder}
                disabled={pagesLoading || pageItems.length === 0}
                className="rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-xs font-medium backdrop-blur hover:bg-white disabled:opacity-40"
              >
                ╨б╨▒╤А╨╛╤Б╨╕╤В╤М
              </button>
            </div>
          </div>

          {pagesLoading ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {Array.from({ length: Math.max(4, pageItems.length || 4) }).map((_, i) => (
                <div key={i} className="glass animate-pulse rounded-[18px] p-3">
                  <div className="aspect-[3/4] rounded-[12px] bg-white/60" />
                  <div className="mt-3 h-3 rounded bg-white/60" />
                  <div className="mt-1.5 h-2 w-2/3 rounded bg-white/40" />
                </div>
              ))}
            </div>
          ) : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={pageItems.map((p) => p.id)} strategy={rectSortingStrategy}>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                  {pageItems.map((item, idx) => (
                    <SortablePageCard key={item.id} item={item} position={idx} onRemove={(id) => setPageItems((prev) => prev.filter((p) => p.id !== id))} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>
      )}

      {/* For non-merge, show FileList; for merge also show file list compact for removal */}
      {slug !== "compare" && (
        slug !== "merge" ? (
          <FileList files={files} onRemove={handleRemove} />
        ) : (
          files.length > 0 && (
            <div className="rounded-[16px] border border-white/60 bg-white/60 backdrop-blur">
              <FileList files={files} onRemove={handleRemove} />
            </div>
          )
        )
      )}

      {slug !== "compare" && isMulti && files.length > 0 && files.length < 10 && (
        <button
          type="button"
          onClick={() => {
            const el = document.querySelector<HTMLInputElement>('input[type="file"]');
            if (el) el.click();
          }}
          className="w-full rounded-[12px] border border-dashed border-black/10 bg-white/50 px-4 py-3 text-sm font-medium text-[#1b1a17] hover:bg-white"
        >
          + ╨Ф╨╛╨▒╨░╨▓╨╕╤В╤М ╨╡╤Й╨╡ ╤Д╨░╨╣╨╗╤Л
        </button>
      )}

      {/* Visual page selector for split/delete */}
      {(slug === "split" || slug === "delete") && files.length > 0 && (
        <div className="space-y-3">
          <div className="glass flex flex-col gap-2 rounded-[16px] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[13px] font-medium text-[#1b1a17]">
                {slug === "split" ? "╨Т╤Л╨▒╨╡╤А╨╕ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╨┤╨╗╤П ╨╕╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П тАФ ╨║╨╗╨╕╨║ ╨┐╨╛ ╨╝╨╕╨╜╨╕╨░╤В╤О╤А╨╡" : "╨Т╤Л╨▒╨╡╤А╨╕ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╨┤╨╗╤П ╤Г╨┤╨░╨╗╨╡╨╜╨╕╤П тАФ ╨║╨╗╨╕╨║ ╨┐╨╛ ╨╝╨╕╨╜╨╕╨░╤В╤О╤А╨╡"}
              </p>
              <p className="text-xs text-[#6b6a63]">
                {previewLoading ? "╨Ч╨░╨│╤А╤Г╨╖╨║╨░ ╤Б╤В╤А╨░╨╜╨╕╤ЖтАж" : preview ? `╨Т ╤Д╨░╨╣╨╗╨╡ ${preview.numPages} ╤Б╤В╤А╨░╨╜╨╕╤Ж ┬╖ ╨▓╤Л╨▒╤А╨░╨╜╨╛ ${selectedPages.size}` : "╨Ч╨░╨│╤А╤Г╨╖╨║╨░ ╨┐╤А╨╡╨▓╤М╤ОтАж"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleSelectAll}
                disabled={!preview || previewLoading}
                className="rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-xs font-medium backdrop-blur hover:bg-white disabled:opacity-40"
              >
                ╨Т╤Б╨╡
              </button>
              <button
                type="button"
                onClick={handleClearSelection}
                disabled={selectedPages.size === 0}
                className="rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-xs font-medium backdrop-blur hover:bg-white disabled:opacity-40"
              >
                ╨б╨╜╤П╤В╤М
              </button>
            </div>
          </div>

          {previewLoading ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="glass animate-pulse rounded-[18px] p-3">
                  <div className="aspect-[3/4] rounded-[12px] bg-white/60" />
                  <div className="mt-3 h-3 rounded bg-white/60" />
                </div>
              ))}
            </div>
          ) : preview ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {Array.from({ length: preview.numPages }, (_, i) => i + 1).map((pageNum) => (
                <SelectablePageCard
                  key={pageNum}
                  pageNum={pageNum}
                  thumb={getThumbForPage(pageNum)}
                  selected={selectedPages.has(pageNum)}
                  onToggle={() => handleTogglePage(pageNum)}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-[16px] border border-dashed border-black/10 bg-white/50 p-6 text-center text-sm text-[#6b6a63]">╨Я╤А╨╡╨▓╤М╤О ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛ тАФ ╨▓╨▓╨╡╨┤╨╕ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╨▓╤А╤Г╤З╨╜╤Г╤О</div>
          )}
        </div>
      )}

      {/* Per-tool params */}
      {(slug === "split" || slug === "delete") && (
        <div>
          <label htmlFor="pages" className="block text-sm font-medium text-gray-700">
            Pages {slug === "split" ? "(e.g. 1,3-5 or 1-2)" : "(e.g. 2 or 1,3)"}
          </label>
          <input
            id="pages"
            type="text"
            value={pages}
            onChange={(e) => handlePagesInputChange(e.target.value)}
            placeholder="1,3-5"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {(() => {
            const parsed = parsePagesToSet(pages, preview?.numPages ?? null);
            if (!parsed || parsed.size === 0) return null;
            const serialized = serializePages(parsed);
            const chips = serialized ? serialized.split(",").map((s) => s.trim()).filter(Boolean) : Array.from(parsed).sort((a, b) => a - b).map(String);
            const handleRemoveChip = (tok: string) => {
              const cur = parsePagesToSet(pages, preview?.numPages ?? null);
              if (!cur) return;
              if (tok.includes("-")) {
                const [aStr, bStr] = tok.split("-");
                const a = parseInt(aStr.trim(), 10);
                const b = parseInt(bStr.trim(), 10);
                if (!isNaN(a) && !isNaN(b)) {
                  for (let p = a; p <= b; p++) cur.delete(p);
                }
              } else {
                const n = parseInt(tok.trim(), 10);
                if (!isNaN(n)) cur.delete(n);
              }
              const newPages = serializePages(cur);
              setPages(newPages);
              setSelectedPages(new Set(cur));
            };
            return (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {chips.map((chip) => (
                  <span key={chip} className="inline-flex items-center gap-1 rounded-full bg-[#e30613] px-2 py-0.5 text-xs font-medium text-white">
                    {chip}
                    <button
                      type="button"
                      onClick={() => handleRemoveChip(chip)}
                      className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-white/20 text-[10px] leading-none hover:bg-white/30"
                      aria-label={`╨г╨┤╨░╨╗╨╕╤В╤М ${chip}`}
                    >
                      ├Ч
                    </button>
                  </span>
                ))}
              </div>
            );
          })()}
          <p className="mt-1 text-xs text-gray-500">
            1-indexed. Ranges with dash, multiple with comma.
            {preview && !previewLoading && ` ╨Т ╤Д╨░╨╣╨╗╨╡ ${preview.numPages} ╤Б╤В╤А╨░╨╜╨╕╤Ж.`}
          </p>
          <p className="mt-1 text-xs text-gray-500">╨Э╨░╨╢╨╝╨╕ ╨╜╨░ ╨╝╨╕╨╜╨╕╨░╤В╤О╤А╤Г ╨╕╨╗╨╕ ╨▓╨▓╨╡╨┤╨╕ ╨▓╤А╤Г╤З╨╜╤Г╤О</p>
          {preview && !previewLoading && (
            <p className="mt-1 text-xs font-medium text-[#0a84ff]">╨Т ╤Д╨░╨╣╨╗╨╡ {preview.numPages} ╤Б╤В╤А╨░╨╜╨╕╤Ж тАФ ╨▓╨▓╨╡╨┤╨╕ 1..{preview.numPages} (╨╜╨░╨┐╤А╨╕╨╝╨╡╤А 1,3-5)</p>
          )}
        </div>
      )}

      {slug === "compress" && (
        <div>
          <p className="text-sm font-medium text-[#1b1a17]">╨г╤А╨╛╨▓╨╡╨╜╤М ╤Б╨╢╨░╤В╨╕╤П</p>
          <p className="mt-1 text-xs text-[#6b6a63]">╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨▒╨░╨╗╨░╨╜╤Б ╨╝╨╡╨╢╨┤╤Г ╤А╨░╨╖╨╝╨╡╤А╨╛╨╝ ╤Д╨░╨╣╨╗╨░ ╨╕ ╨║╨░╤З╨╡╤Б╤В╨▓╨╛╨╝.</p>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <button
              type="button"
              onClick={() => setQuality("low")}
              className={`rounded-[16px] border p-4 text-left transition ${quality === "low" ? "border-[#e30613] bg-[#fef2f2] shadow-sm" : "border-black/10 bg-white/80 hover:bg-white"}`}
            >
              <p className="text-sm font-semibold text-[#1b1a17]">╨н╨║╤Б╤В╤А╨╡╨╝╨░╨╗╤М╨╜╨╛╨╡</p>
              <p className="mt-1 text-xs text-[#6b6a63]">╨Ь╨░╨║╤Б╨╕╨╝╨░╨╗╤М╨╜╨╛╨╡ ╤Б╨╢╨░╤В╨╕╨╡</p>
              <span className="mt-2 inline-block rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-[#6b6a63] border border-black/10">~70% ╨╝╨╡╨╜╤М╤И╨╡</span>
            </button>
            <button
              type="button"
              onClick={() => setQuality("medium")}
              className={`rounded-[16px] border p-4 text-left transition ${quality === "medium" ? "border-[#e30613] bg-[#fef2f2] shadow-sm" : "border-black/10 bg-white/80 hover:bg-white"}`}
            >
              <p className="text-sm font-semibold text-[#1b1a17]">╨а╨╡╨║╨╛╨╝╨╡╨╜╨┤╤Г╨╡╨╝╨╛╨╡</p>
              <p className="mt-1 text-xs text-[#6b6a63]">╨С╨░╨╗╨░╨╜╤Б ╨║╨░╤З╨╡╤Б╤В╨▓╨░</p>
              <span className="mt-2 inline-block rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-[#6b6a63] border border-black/10">~40% ╨╝╨╡╨╜╤М╤И╨╡</span>
            </button>
            <button
              type="button"
              onClick={() => setQuality("high")}
              className={`rounded-[16px] border p-4 text-left transition ${quality === "high" ? "border-[#e30613] bg-[#fef2f2] shadow-sm" : "border-black/10 bg-white/80 hover:bg-white"}`}
            >
              <p className="text-sm font-semibold text-[#1b1a17]">╨Э╨╕╨╖╨║╨╛╨╡</p>
              <p className="mt-1 text-xs text-[#6b6a63]">╨Ы╤Г╤З╤И╨╡╨╡ ╨║╨░╤З╨╡╤Б╤В╨▓╨╛</p>
              <span className="mt-2 inline-block rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-[#6b6a63] border border-black/10">~10% ╨╝╨╡╨╜╤М╤И╨╡</span>
            </button>
          </div>
        </div>
      )}

      {slug === "rotate" && (
        <div>
          <label htmlFor="angle" className="block text-sm font-medium text-gray-700">
            Angle
          </label>
          <select
            id="angle"
            value={angle}
            onChange={(e) => setAngle(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="90">90┬░</option>
            <option value="180">180┬░</option>
            <option value="270">270┬░</option>
          </select>
        </div>
      )}

      {slug === "watermark" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Т╨╛╨┤╤П╨╜╨╛╨╣ ╨╖╨╜╨░╨║ тАФ ╤В╨╡╨║╤Б╤В ╨╕╨╗╨╕ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡</p>
            <p className="text-xs text-[#6b6a63]">╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╨╕╨╗╨╕ ╤В╨╡╨║╤Б╤В, ╨║╨╛╤В╨╛╤А╤Л╨╡ ╨▓╤Л ╤Е╨╛╤В╨╕╤В╨╡ ╨▓╤Б╤В╨░╨▓╨╕╤В╤М ╨▓ ╨▓╨░╤И PDF. ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡, ╨┐╤А╨╛╨╖╤А╨░╤З╨╜╨╛╤Б╤В╤М ╨╕ ╤И╤А╨╕╤Д╤В.</p>

            <div>
              <label htmlFor="wmText" className="block text-sm font-medium text-gray-700">╨в╨╡╨║╤Б╤В</label>
              <input
                id="wmText"
                type="text"
                value={wmText}
                onChange={(e) => setWmText(e.target.value)}
                placeholder="╨Э╨░╨┐╤А╨╕╨╝╨╡╤А: ╨Ъ╨╛╨╜╤Д╨╕╨┤╨╡╨╜╤Ж╨╕╨░╨╗╤М╨╜╨╛"
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">╨Ш╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ (╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╨╛)</label>
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/webp"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setWmImage(f);
                }}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm file:mr-3 file:rounded-full file:border-0 file:bg-[#0a84ff] file:px-3 file:py-1 file:text-xs file:font-medium file:text-white hover:file:bg-blue-600"
              />
              {wmImage && (
                <div className="mt-2 flex items-center justify-between rounded-md bg-white/80 px-3 py-2 text-xs">
                  <span className="truncate font-medium text-[#1b1a17]">{wmImage.name}</span>
                  <button type="button" onClick={() => setWmImage(null)} className="ml-2 rounded-full border border-black/10 bg-white px-2 py-0.5 text-xs hover:bg-gray-50">╨г╨┤╨░╨╗╨╕╤В╤М</button>
                </div>
              )}
              <p className="mt-1 text-xs text-gray-500">╨Я╨╛╨┤╨┤╨╡╤А╨╢╨╕╨▓╨░╨╡╤В╤Б╤П PNG/JPG/WEBP. ╨Я╤А╨╛╨╖╤А╨░╤З╨╜╨╛╤Б╤В╤М ╨▒╤Г╨┤╨╡╤В ╨┐╤А╨╕╨╝╨╡╨╜╨╡╨╜╨░.</p>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">╨Я╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡</label>
                <div className="mt-2">
                  <PositionGrid value={wmPosition} onChange={setWmPosition} />
                </div>
              </div>

              <div>
                <label htmlFor="wmFontSize" className="block text-sm font-medium text-gray-700">╨а╨░╨╖╨╝╨╡╤А ╤И╤А╨╕╤Д╤В╨░</label>
                <select
                  id="wmFontSize"
                  value={wmFontSize}
                  onChange={(e) => setWmFontSize(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="16">16</option>
                  <option value="24">24</option>
                  <option value="36">36</option>
                  <option value="48">48</option>
                  <option value="72">72</option>
                  <option value="96">96</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="wmFontFamily" className="block text-sm font-medium text-gray-700">╨и╤А╨╕╤Д╤В</label>
                <select
                  id="wmFontFamily"
                  value={wmFontFamily}
                  onChange={(e) => setWmFontFamily(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="Helvetica">Helvetica</option>
                  <option value="Arial">Arial</option>
                  <option value="Times">Times</option>
                  <option value="Courier">Courier</option>
                  <option value="Georgia">Georgia</option>
                  <option value="Verdana">Verdana</option>
                </select>
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm font-medium text-[#1b1a17]">
                  <input
                    type="checkbox"
                    checked={wmTiling}
                    onChange={(e) => setWmTiling(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]"
                  />
                  ╨Я╨╛╨▓╤В╨╛╤А╤П╤В╤М ╨┐╨╛ ╨┤╨╕╨░╨│╨╛╨╜╨░╨╗╨╕ (╨┐╨╗╨╕╤В╨║╨░)
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium text-[#1b1a17]">╨Я╤А╨╡╨▓╤М╤О {preview ? `${preview.numPages} ╤Б╤В╤А.` : ""} {previewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : ""}</p>
              <LivePreview
                thumb={preview?.pages[0]?.thumb ?? null}
                label="╨Я╤А╨╡╨▓╤М╤О"
                overlay={
                  <div className={`flex h-full w-full p-4 ${positionToFlex(wmPosition)}`}>
                    <span style={{ color: wmColor, fontSize: `${wmFontSize}px`, opacity: wmOpacity / 100, transform: `rotate(${wmRotation}deg)`, fontFamily: wmFontFamily }}>{wmText || "╨Ю╨▒╤А╨░╨╖╨╡╤Ж"}</span>
                  </div>
                }
              />
            </div>

            <div>
              <label htmlFor="wmOpacity" className="block text-sm font-medium text-gray-700">╨Я╤А╨╛╨╖╤А╨░╤З╨╜╨╛╤Б╤В╤М: {wmOpacity}%</label>
              <input
                id="wmOpacity"
                type="range"
                min={10}
                max={100}
                step={5}
                value={wmOpacity}
                onChange={(e) => setWmOpacity(Number(e.target.value))}
                className="mt-2 w-full accent-[#0a84ff]"
              />
              <div className="flex justify-between text-[11px] text-[#6b6a63]">
                <span>10%</span><span>100%</span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="wmColor" className="block text-sm font-medium text-gray-700">╨ж╨▓╨╡╤В</label>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    id="wmColor"
                    type="color"
                    value={wmColor}
                    onChange={(e) => setWmColor(e.target.value)}
                    className="h-9 w-12 rounded-md border border-gray-300 bg-white p-1"
                  />
                  <input
                    type="text"
                    value={wmColor}
                    onChange={(e) => setWmColor(e.target.value)}
                    placeholder="#C8C8C8"
                    className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="wmRotation" className="block text-sm font-medium text-gray-700">╨Я╨╛╨▓╨╛╤А╨╛╤В (┬░)</label>
                <select
                  id="wmRotation"
                  value={wmRotation}
                  onChange={(e) => setWmRotation(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="0">0┬░</option>
                  <option value="45">45┬░</option>
                  <option value="90">90┬░</option>
                  <option value="180">180┬░</option>
                  <option value="270">270┬░</option>
                  <option value="315">315┬░</option>
                </select>
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-500">╨в╤А╨╡╨▒╤Г╨╡╤В╤Б╤П ╤В╨╡╨║╤Б╤В ╨╕╨╗╨╕ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡. ╨Я╤А╨╕ ╤Г╨║╨░╨╖╨░╨╜╨╕╨╕ ╨╛╨▒╨╛╨╕╤Е тАФ ╨▒╤Г╨┤╤Г╤В ╨╜╨░╨╜╨╡╤Б╨╡╨╜╤Л ╨╛╨▒╨░ ╤Б╨╗╨╛╤П ╨╜╨░ ╨║╨░╨╢╨┤╤Г╤О ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Г.</p>
        </div>
      )}

      {slug === "crop" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Ю╨▒╤А╨╡╨╖╨║╨░ тАФ ╨┐╨╛╨╗╤П ╨╕╨╗╨╕ ╨╛╨▒╨╗╨░╤Б╤В╤М</p>
            <p className="text-xs text-[#6b6a63]">╨Ю╨▒╤А╨╡╨╖╨░╨╣╤В╨╡ ╨┐╨╛╨╗╤П ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓ PDF ╨╕╨╗╨╕ ╨▓╤Л╨▒╨╕╤А╨░╨╣╤В╨╡ ╨╛╨▒╨╗╨░╤Б╤В╨╕, ╨░ ╨╖╨░╤В╨╡╨╝ ╨┐╤А╨╕╨╝╨╡╨╜╤П╨╣╤В╨╡ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╨║ ╨╛╨┤╨╜╨╛╨╣ ╤Б╤В╤А╨░╨╜╨╕╤Ж╨╡ ╨╕╨╗╨╕ ╨▓╤Б╨╡╨╝╤Г ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Г.</p>

            {/* mode toggle */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setCropMode("margins")}
                className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${cropMode === "margins" ? "bg-[#0a84ff] text-white shadow" : "bg-white/80 border border-black/10 text-[#1b1a17] hover:bg-white"}`}
              >
                ╨Я╨╛╨╗╤П
              </button>
              <button
                type="button"
                onClick={() => setCropMode("rect")}
                className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${cropMode === "rect" ? "bg-[#0a84ff] text-white shadow" : "bg-white/80 border border-black/10 text-[#1b1a17] hover:bg-white"}`}
              >
                ╨Ю╨▒╨╗╨░╤Б╤В╤М (x,y,w,h)
              </button>
            </div>

            {cropMode === "margins" ? (
              <>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setCropUnit("mm")}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${cropUnit === "mm" ? "bg-[#1b1a17] text-white" : "bg-white/70 border border-black/10"}`}
                  >
                    ╨╝╨╝
                  </button>
                  <button
                    type="button"
                    onClick={() => setCropUnit("pt")}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${cropUnit === "pt" ? "bg-[#1b1a17] text-white" : "bg-white/70 border border-black/10"}`}
                  >
                    pt
                  </button>
                  <span className="ml-2 text-[11px] text-[#6b6a63] self-center">1 ╨╝╨╝ = 2.83 pt</span>
                </div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div>
                    <label htmlFor="cropTop" className="block text-sm font-medium text-gray-700">╨б╨▓╨╡╤А╤Е╤Г</label>
                    <input id="cropTop" type="number" min={0} max={1000} step={cropUnit === "mm" ? 1 : 5} value={cropTop} onChange={(e) => setCropTop(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="10" />
                    <span className="text-[11px] text-[#9a9994]">{cropUnit}</span>
                  </div>
                  <div>
                    <label htmlFor="cropBottom" className="block text-sm font-medium text-gray-700">╨б╨╜╨╕╨╖╤Г</label>
                    <input id="cropBottom" type="number" min={0} max={1000} step={cropUnit === "mm" ? 1 : 5} value={cropBottom} onChange={(e) => setCropBottom(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="10" />
                    <span className="text-[11px] text-[#9a9994]">{cropUnit}</span>
                  </div>
                  <div>
                    <label htmlFor="cropLeft" className="block text-sm font-medium text-gray-700">╨б╨╗╨╡╨▓╨░</label>
                    <input id="cropLeft" type="number" min={0} max={1000} step={cropUnit === "mm" ? 1 : 5} value={cropLeft} onChange={(e) => setCropLeft(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="10" />
                    <span className="text-[11px] text-[#9a9994]">{cropUnit}</span>
                  </div>
                  <div>
                    <label htmlFor="cropRight" className="block text-sm font-medium text-gray-700">╨б╨┐╤А╨░╨▓╨░</label>
                    <input id="cropRight" type="number" min={0} max={1000} step={cropUnit === "mm" ? 1 : 5} value={cropRight} onChange={(e) => setCropRight(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="10" />
                    <span className="text-[11px] text-[#9a9994]">{cropUnit}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <label htmlFor="cropX" className="block text-sm font-medium text-gray-700">X</label>
                  <input id="cropX" type="number" min={0} value={cropX} onChange={(e) => setCropX(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="0" />
                  <span className="text-[11px] text-[#9a9994]">pt</span>
                </div>
                <div>
                  <label htmlFor="cropY" className="block text-sm font-medium text-gray-700">Y</label>
                  <input id="cropY" type="number" min={0} value={cropY} onChange={(e) => setCropY(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="0" />
                  <span className="text-[11px] text-[#9a9994]">pt</span>
                </div>
                <div>
                  <label htmlFor="cropW" className="block text-sm font-medium text-gray-700">╨и╨╕╤А╨╕╨╜╨░ (w)</label>
                  <input id="cropW" type="number" min={1} value={cropW} onChange={(e) => setCropW(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="200" />
                  <span className="text-[11px] text-[#9a9994]">pt</span>
                </div>
                <div>
                  <label htmlFor="cropH" className="block text-sm font-medium text-gray-700">╨Т╤Л╤Б╨╛╤В╨░ (h)</label>
                  <input id="cropH" type="number" min={1} value={cropH} onChange={(e) => setCropH(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="200" />
                  <span className="text-[11px] text-[#9a9994]">pt</span>
                </div>
              </div>
            )}

            <div>
              <label htmlFor="cropPages" className="block text-sm font-medium text-gray-700">╨б╤В╤А╨░╨╜╨╕╤Ж╤Л</label>
              <div className="mt-1 flex gap-2">
                <input
                  id="cropPages"
                  type="text"
                  value={cropPages}
                  onChange={(e) => setCropPages(e.target.value)}
                  placeholder='all ╨╕╨╗╨╕ 1,3-5'
                  className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button type="button" onClick={() => setCropPages("all")} className={`rounded-full px-4 py-2 text-xs font-medium whitespace-nowrap ${cropPages === "all" ? "bg-[#0a84ff] text-white" : "bg-white border border-black/10"}`}>╨Т╤Б╨╡</button>
              </div>
              <p className="mt-1 text-xs text-gray-500">all тАФ ╨▓╨╡╤Б╤М ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В, ╨╕╨╗╨╕ ╤Г╨║╨░╨╢╨╕ 1,3-5. {cropPreview && !cropPreviewLoading && ` ╨Т ╤Д╨░╨╣╨╗╨╡ ${cropPreview.numPages} ╤Б╤В╤А.`}</p>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium text-[#1b1a17]">Live ╨┐╤А╨╡╨▓╤М╤О тАФ ╤Б╨╕╨╜╨╕╨╣ ╨║╨╛╨╜╤В╤Г╤А = ╨╛╨▒╨╗╨░╤Б╤В╤М ╨┐╨╛╤Б╨╗╨╡ ╨╛╨▒╤А╨╡╨╖╨║╨╕ {cropPreview ? `${cropPreview.numPages} ╤Б╤В╤А.` : ""} {cropPreviewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : ""}</p>
              <LivePreview
                thumb={cropPreview?.pages[0]?.thumb ?? null}
                label="╨Я╤А╨╡╨▓╤М╤О"
                overlay={(() => {
                  const isTarget = (() => {
                    if (!cropPreview) return true;
                    if (cropPages.trim().toLowerCase() === "all" || cropPages.trim() === "") return true;
                    const set = parsePagesToSet(cropPages, cropPreview.numPages);
                    return set ? set.has(1) : false;
                  })();
                  if (!isTarget) return <div className="flex h-full w-full items-center justify-center p-4"><span className="rounded-full bg-white/90 px-2 py-1 text-[10px] font-medium text-[#6b6a63]">╨▒╨╡╨╖ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╨╣</span></div>;
                  if (cropMode === "margins") {
                    const toPt = (v: string) => {
                      const num = parseFloat(String(v).replace(",", ".")) || 0;
                      return cropUnit === "mm" ? num * 2.83465 : num;
                    };
                    const topPt = toPt(cropTop);
                    const botPt = toPt(cropBottom);
                    const leftPt = toPt(cropLeft);
                    const rightPt = toPt(cropRight);
                    const pw = 595;
                    const ph = 842;
                    const topPct = Math.min(40, (topPt / ph) * 100);
                    const botPct = Math.min(40, (botPt / ph) * 100);
                    const leftPct = Math.min(40, (leftPt / pw) * 100);
                    const rightPct = Math.min(40, (rightPt / pw) * 100);
                    return <div style={{ position: "absolute", inset: 0 }}><div style={{ position: "absolute", border: "2px solid #0a84ff", background: "rgba(10,132,255,0.08)", top: `${topPct}%`, bottom: `${botPct}%`, left: `${leftPct}%`, right: `${rightPct}%` } as React.CSSProperties} /></div>;
                  } else {
                    const xNum = parseFloat(String(cropX).replace(",", ".")) || 0;
                    const yNum = parseFloat(String(cropY).replace(",", ".")) || 0;
                    const wNum = parseFloat(String(cropW).replace(",", ".")) || 0;
                    const hNum = parseFloat(String(cropH).replace(",", ".")) || 0;
                    const pw = 595;
                    const ph = 842;
                    const xPct = Math.max(0, Math.min(90, (xNum / pw) * 100));
                    const yPct = Math.max(0, Math.min(90, (yNum / ph) * 100));
                    const wPct = Math.max(5, Math.min(90, (wNum / pw) * 100));
                    const hPct = Math.max(5, Math.min(90, (hNum / ph) * 100));
                    return <div style={{ position: "absolute", border: "2px solid #0a84ff", background: "rgba(10,132,255,0.12)", left: `${xPct}%`, top: `${yPct}%`, width: `${wPct}%`, height: `${hPct}%` } as React.CSSProperties} />;
                  }
                })()}
              />
            </div>

            {/* preview thumbnails with crop overlay */}
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-[#1b1a17]">╨Я╤А╨╡╨▓╤М╤О{cropPreview ? ` ${cropPreview.numPages} ╤Б╤В╤А.` : ""} {cropPreviewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : "тАФ ╤Б╨╕╨╜╨╕╨╣ ╨║╨╛╨╜╤В╤Г╤А = ╨╛╨▒╨╗╨░╤Б╤В╤М ╨┐╨╛╤Б╨╗╨╡ ╨╛╨▒╤А╨╡╨╖╨║╨╕"}</p>
                {cropPreviewLoading ? (
                  <div className="grid grid-cols-3 gap-2">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="glass animate-pulse rounded-[12px] p-2"><div className="aspect-[3/4] rounded bg-white/60" /></div>
                    ))}
                  </div>
                ) : cropPreview && cropPreview.pages.length > 0 ? (
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {cropPreview.pages.slice(0, 8).map((p) => {
                      const isTarget = (() => {
                        if (cropPages.trim().toLowerCase() === "all" || cropPages.trim() === "") return true;
                        const set = parsePagesToSet(cropPages, cropPreview.numPages);
                        return set ? set.has(p.page + 1) : false;
                      })();
                      // compute overlay styles
                      let overlayStyle: React.CSSProperties | null = null;
                      let shadeTop: React.CSSProperties | null = null;
                      let shadeBottom: React.CSSProperties | null = null;
                      let shadeLeft: React.CSSProperties | null = null;
                      let shadeRight: React.CSSProperties | null = null;
                      if (isTarget) {
                        if (cropMode === "margins") {
                          // estimate page size: assume A4-ish if unknown; use percentages derived from margins
                          const toPt = (v: string) => {
                            const num = parseFloat(String(v).replace(",", ".")) || 0;
                            return cropUnit === "mm" ? num * 2.83465 : num;
                          };
                          const topPt = toPt(cropTop);
                          const botPt = toPt(cropBottom);
                          const leftPt = toPt(cropLeft);
                          const rightPt = toPt(cropRight);
                          // assume page 595x842 pt (A4) for preview percentages
                          const pw = 595;
                          const ph = 842;
                          const topPct = Math.min(40, (topPt / ph) * 100);
                          const botPct = Math.min(40, (botPt / ph) * 100);
                          const leftPct = Math.min(40, (leftPt / pw) * 100);
                          const rightPct = Math.min(40, (rightPt / pw) * 100);
                          overlayStyle = { position: "absolute", border: "2px solid #0a84ff", background: "rgba(10,132,255,0.08)", top: `${topPct}%`, bottom: `${botPct}%`, left: `${leftPct}%`, right: `${rightPct}%` } as React.CSSProperties;
                        } else {
                          const xNum = parseFloat(String(cropX).replace(",", ".")) || 0;
                          const yNum = parseFloat(String(cropY).replace(",", ".")) || 0;
                          const wNum = parseFloat(String(cropW).replace(",", ".")) || 0;
                          const hNum = parseFloat(String(cropH).replace(",", ".")) || 0;
                          const pw = 595;
                          const ph = 842;
                          const xPct = Math.max(0, Math.min(90, (xNum / pw) * 100));
                          const yPct = Math.max(0, Math.min(90, (yNum / ph) * 100));
                          const wPct = Math.max(5, Math.min(90, (wNum / pw) * 100));
                          const hPct = Math.max(5, Math.min(90, (hNum / ph) * 100));
                          overlayStyle = { position: "absolute", border: "2px solid #0a84ff", background: "rgba(10,132,255,0.12)", left: `${xPct}%`, top: `${yPct}%`, width: `${wPct}%`, height: `${hPct}%` } as React.CSSProperties;
                        }
                      }
                      return (
                        <div key={p.page} className={`relative overflow-hidden rounded-[12px] border bg-white ${isTarget ? "border-[#0a84ff]/40 shadow-[0_0_0_2px_rgba(10,132,255,0.15)]" : "border-white/60 opacity-60"}`}>
                          <img src={p.thumb} alt={`╤Б╤В╤А ${p.page + 1}`} className="aspect-[3/4] w-full object-cover object-top" />
                          {overlayStyle && <div style={overlayStyle} />}
                          <span className="absolute bottom-1 left-1 rounded-full bg-black/70 px-1.5 py-0.5 text-[9px] font-medium text-white">╤Б╤В╤А. {p.page + 1}</span>
                          {!isTarget && <span className="absolute top-1 right-1 rounded-full bg-white/90 px-1.5 py-0.5 text-[8px] font-medium text-[#6b6a63]">╨▒╨╡╨╖ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╨╣</span>}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-[12px] border border-dashed border-black/10 bg-white/50 p-4 text-center text-xs text-[#6b6a63]">╨Я╤А╨╡╨▓╤М╤О ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛</div>
                )}
                {cropPreview && cropPreview.numPages > 8 && <p className="text-[11px] text-[#9a9994]">╨Я╨╛╨║╨░╨╖╨░╨╜╤Л ╨┐╨╡╤А╨▓╤Л╨╡ 8 ╨╕╨╖ {cropPreview.numPages} ╤Б╤В╤А╨░╨╜╨╕╤Ж.</p>}
              </div>
            )}
          </div>
        </div>
      )}

      {slug === "protect" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Ч╨░╤Й╨╕╤В╨░ PDF тАФ ╨┐╨░╤А╨╛╨╗╨╕ ╨╕ ╨┐╤А╨░╨▓╨░</p>
            <p className="text-xs text-[#6b6a63]">╨г╤Б╤В╨░╨╜╨╛╨▓╨╕╤В╨╡ ╨┐╨░╤А╨╛╨╗╤М ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П (╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╨╡╨╜) ╨╕ ╨▓╨╗╨░╨┤╨╡╨╗╤М╤Ж╨░ (╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╨╛). ╨Э╨░╤Б╤В╤А╨╛╨╣╤В╨╡ ╤А╨░╨╖╤А╨╡╤И╨╡╨╜╨╕╤П.</p>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨Я╨░╤А╨╛╨╗╤М ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П *</label>
              <input type="password" value={protectPass} onChange={(e) => setProtectPass(e.target.value)} placeholder="тАвтАвтАвтАвтАвтАвтАвтАв" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨Я╨░╤А╨╛╨╗╤М ╨▓╨╗╨░╨┤╨╡╨╗╤М╤Ж╨░ (╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╨╛)</label>
              <input type="password" value={protectOwnerPass} onChange={(e) => setProtectOwnerPass(e.target.value)} placeholder="тАвтАвтАвтАвтАвтАвтАвтАв" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
              <p className="mt-1 text-xs text-gray-500">╨Х╤Б╨╗╨╕ ╨╜╨╡ ╤Г╨║╨░╨╖╨░╨╜ тАФ ╤Б╨╛╨▓╨┐╨░╨┤╨░╨╡╤В ╤Б ╨┐╨░╤А╨╛╨╗╨╡╨╝ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex items-center gap-2 text-sm text-[#1b1a17]"><input type="checkbox" checked={protectAllowPrint} onChange={(e) => setProtectAllowPrint(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]" /> ╨Я╨╡╤З╨░╤В╤М</label>
              <label className="flex items-center gap-2 text-sm text-[#1b1a17]"><input type="checkbox" checked={protectAllowCopy} onChange={(e) => setProtectAllowCopy(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]" /> ╨Ъ╨╛╨┐╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡</label>
              <label className="flex items-center gap-2 text-sm text-[#1b1a17]"><input type="checkbox" checked={protectAllowModify} onChange={(e) => setProtectAllowModify(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]" /> ╨Ш╨╖╨╝╨╡╨╜╨╡╨╜╨╕╨╡</label>
              <label className="flex items-center gap-2 text-sm text-[#1b1a17]"><input type="checkbox" checked={protectAllowAnnotate} onChange={(e) => setProtectAllowAnnotate(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]" /> ╨Р╨╜╨╜╨╛╤В╨░╤Ж╨╕╨╕</label>
            </div>
            <p className="text-xs text-gray-500">╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╡╤В╤Б╤П 128-bit ╤И╨╕╤Д╤А╨╛╨▓╨░╨╜╨╕╨╡ (AES-128).</p>
          </div>
        </div>
      )}

      {slug === "unlock" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Ю╤В╨║╤А╤Л╤В╤М PDF тАФ ╨▓╨▓╨╛╨┤ ╨┐╨░╤А╨╛╨╗╤П</p>
            <p className="text-xs text-[#6b6a63]">╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨┐╨░╤А╨╛╨╗╤М ╨╛╤В ╨╖╨░╤И╨╕╤Д╤А╨╛╨▓╨░╨╜╨╜╨╛╨│╨╛ PDF, ╤З╤В╨╛╨▒╤Л ╤Б╨╜╤П╤В╤М ╨╖╨░╤Й╨╕╤В╤Г.</p>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨Я╨░╤А╨╛╨╗╤М *</label>
              <input type="password" value={unlockPass} onChange={(e) => setUnlockPass(e.target.value)} placeholder="тАвтАвтАвтАвтАвтАвтАвтАв" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
          </div>
        </div>
      )}

      {slug === "redact" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨б╨║╤А╤Л╤В╤М ╨┤╨░╨╜╨╜╤Л╨╡ тАФ ╨▒╨╡╨╖╨▓╨╛╨╖╨▓╤А╨░╤В╨╜╨╛╨╡ ╨╖╨░╨║╤А╨░╤И╨╕╨▓╨░╨╜╨╕╨╡</p>
            <p className="text-xs text-[#6b6a63]">╨г╨║╨░╨╢╨╕╤В╨╡ ╤Д╤А╨░╨╖╤Л ╤З╨╡╤А╨╡╨╖ ╨╖╨░╨┐╤П╤В╤Г╤О тАФ ╨╛╨╜╨╕ ╨▒╤Г╨┤╤Г╤В ╨╖╨░╨║╤А╨░╤И╨╡╨╜╤Л ╤З╤С╤А╨╜╤Л╨╝. ╨Ш╨╗╨╕ ╤Б╨║╤А╨╛╨╣╤В╨╡ ╨▓╤Б╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П.</p>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨д╤А╨░╨╖╤Л ╨┤╨╗╤П ╤Б╨║╤А╤Л╤В╨╕╤П (╤З╨╡╤А╨╡╨╖ ╨╖╨░╨┐╤П╤В╤Г╤О)</label>
              <input type="text" value={redactTexts} onChange={(e) => setRedactTexts(e.target.value)} placeholder="╨╜╨░╨┐╤А╨╕╨╝╨╡╤А: ╤Б╨╡╨║╤А╨╡╤В, ╨║╨╛╨╜╤Д╨╕╨┤╨╡╨╜╤Ж╨╕╨░╨╗╤М╨╜╨╛" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
              <p className="mt-1 text-xs text-gray-500">╨Я╨╛╨╕╤Б╨║ ╤З╤Г╨▓╤Б╤В╨▓╨╕╤В╨╡╨╗╨╡╨╜ ╨║ ╤А╨╡╨│╨╕╤Б╤В╤А╤Г? ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╡╤В ╤В╨╛╤З╨╜╤Л╨╣ ╨┐╨╛╨╕╤Б╨║. ╨Я╤Г╤Б╤В╨╛ = ╤В╨╛╨╗╤М╨║╨╛ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П.</p>
            </div>
            <label className="flex items-center gap-2 text-sm font-medium text-[#1b1a17]">
              <input type="checkbox" checked={redactHideImages} onChange={(e) => setRedactHideImages(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-[#0a84ff] focus:ring-[#0a84ff]" />
              ╨б╨║╤А╤Л╤В╤М ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П (╨╖╨░╨║╤А╨░╤Б╨╕╤В╤М ╤З╤С╤А╨╜╤Л╨╝)
            </label>
          </div>
        </div>
      )}

      {slug === "sign" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Я╨╛╨┤╨┐╨╕╤Б╨░╤В╤М PDF тАФ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨╕</p>
            <p className="text-xs text-[#6b6a63]">╨Ч╨░╨│╤А╤Г╨╖╨╕╤В╨╡ PNG/JPG ╨┐╨╛╨┤╨┐╨╕╤Б╨╕ ╨╕ ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡, ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Г ╨╕ ╨┐╤А╨╛╨╖╤А╨░╤З╨╜╨╛╤Б╤В╤М.</p>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨Ш╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨╕ (PNG/JPG) *</label>
              <input type="file" accept="image/png,image/jpeg,image/jpg,image/webp" onChange={(e) => { const f = e.target.files?.[0] || null; setSignImage(f); }} className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm file:mr-3 file:rounded-full file:border-0 file:bg-[#0a84ff] file:px-3 file:py-1 file:text-xs file:font-medium file:text-white hover:file:bg-blue-600" />
              {signImage && <div className="mt-2 flex items-center justify-between rounded-md bg-white/80 px-3 py-2 text-xs"><span className="truncate font-medium text-[#1b1a17]">{signImage.name}</span><button type="button" onClick={() => setSignImage(null)} className="ml-2 rounded-full border border-black/10 bg-white px-2 py-0.5 text-xs hover:bg-gray-50">╨г╨┤╨░╨╗╨╕╤В╤М</button></div>}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">╨Я╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡</label>
                <div className="mt-2">
                  <PositionGrid value={signPosition} onChange={setSignPosition} />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">╨б╤В╤А╨░╨╜╨╕╤Ж╨░</label>
                <input type="text" value={signPage} onChange={(e) => setSignPage(e.target.value)} placeholder='all ╨╕╨╗╨╕ 1,2' className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-[#1b1a17]">╨Я╤А╨╡╨▓╤М╤О {signPreview ? `${signPreview.numPages} ╤Б╤В╤А.` : ""} {signPreviewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : ""}</p>
              <LivePreview
                thumb={signPreview?.pages[0]?.thumb ?? null}
                label="╨Я╤А╨╡╨▓╤М╤О"
                overlay={
                  <div className={`flex h-full w-full p-4 ${positionToFlex(signPosition)}`}>
                    {signThumbUrl ? (
                      <img
                        src={signThumbUrl}
                        alt="╨┐╨╛╨┤╨┐╨╕╤Б╤М"
                        style={{ opacity: signOpacity / 100, maxWidth: "40%", maxHeight: "30%", objectFit: "contain" }}
                        draggable={false}
                      />
                    ) : (
                      <span className="text-[11px] text-[#9a9994]">╨╖╨░╨│╤А╤Г╨╖╨╕╤В╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╤М ╨┤╨╗╤П ╨┐╤А╨╡╨▓╤М╤О</span>
                    )}
                  </div>
                }
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">╨Я╤А╨╛╨╖╤А╨░╤З╨╜╨╛╤Б╤В╤М: {signOpacity}%</label>
              <input type="range" min={10} max={100} step={5} value={signOpacity} onChange={(e) => setSignOpacity(Number(e.target.value))} className="mt-2 w-full accent-[#0a84ff]" />
            </div>
            <details className="rounded-[12px] border border-white/60 bg-white/50 p-3">
              <summary className="cursor-pointer text-sm font-medium text-[#1b1a17]">╨в╨╛╤З╨╜╤Л╨╡ ╨║╨╛╨╛╤А╨┤╨╕╨╜╨░╤В╤Л x,y,w,h (╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╨╛)</summary>
              <p className="mt-1 text-xs text-[#6b6a63]">╨Х╤Б╨╗╨╕ ╨╖╨░╨┐╨╛╨╗╨╜╨╡╨╜╤Л тАФ ╨┐╨╛╨╖╨╕╤Ж╨╕╤П ╨╕╨│╨╜╨╛╤А╨╕╤А╤Г╨╡╤В╤Б╤П, ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╡╤В╤Б╤П ╨┐╤А╤П╨╝╨╛╤Г╨│╨╛╨╗╤М╨╜╨╕╨║.</p>
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div><label className="block text-xs font-medium text-gray-700">X (pt)</label><input type="number" value={signX} onChange={(e) => setSignX(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="20" /></div>
                <div><label className="block text-xs font-medium text-gray-700">Y (pt)</label><input type="number" value={signY} onChange={(e) => setSignY(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="20" /></div>
                <div><label className="block text-xs font-medium text-gray-700">W</label><input type="number" value={signW} onChange={(e) => setSignW(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="120" /></div>
                <div><label className="block text-xs font-medium text-gray-700">H</label><input type="number" value={signH} onChange={(e) => setSignH(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="60" /></div>
              </div>
            </details>
          </div>
        </div>
      )}

      {slug === "compare" && compareResult && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨а╨╡╨╖╤Г╨╗╤М╤В╨░╤В ╤Б╤А╨░╨▓╨╜╨╡╨╜╨╕╤П тАФ {compareResult.pages.length} ╤Б╤В╤А.</p>
            <p className="text-xs text-[#6b6a63]">╨Ъ╤А╨░╤Б╨╜╨░╤П ╤А╨░╨╝╨║╨░ тАФ ╤А╨░╨╖╨╗╨╕╤З╨╕╤П ╨▓ ╤В╨╡╨║╤Б╤В╨╡. ╨б╨╡╤А╤Л╨╣ тАФ ╤Б╨╛╨▓╨┐╨░╨┤╨╡╨╜╨╕╨╡.</p>
          </div>
          <div className="space-y-4">
            {compareResult.pages.map((pg) => (
              <div key={pg.index} className={`glass rounded-[16px] p-4 space-y-3 ${pg.diff ? "ring-2 ring-red-400/50 bg-red-50/40" : "ring-1 ring-emerald-200/50"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#1b1a17]">╨б╤В╤А. {pg.index + 1}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${pg.diff ? "bg-red-500 text-white" : "bg-emerald-500 text-white"}`}>{pg.diff ? "╤А╨░╨╖╨╗╨╕╤З╨░╨╡╤В╤Б╤П" : "╤Б╨╛╨▓╨┐╨░╨┤╨░╨╡╤В"}</span>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[#6b6a63]">╨б╨╗╨╡╨▓╨░</p>
                    <div className="overflow-hidden rounded-[12px] border border-white/60 bg-white">
                      {pg.left_thumb ? <img src={pg.left_thumb} alt={`left ${pg.index+1}`} className="w-full object-contain" /> : <div className="flex h-32 items-center justify-center text-xs text-[#9a9994]">╨╜╨╡╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л</div>}
                    </div>
                    <div className="rounded-[8px] bg-white/70 p-2 text-xs leading-relaxed text-[#1b1a17] max-h-32 overflow-auto whitespace-pre-wrap">{pg.left_text?.slice(0,800) || "тАФ ╨┐╤Г╤Б╤В╨╛ тАФ"}</div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[#6b6a63]">╨б╨┐╤А╨░╨▓╨░</p>
                    <div className="overflow-hidden rounded-[12px] border border-white/60 bg-white">
                      {pg.right_thumb ? <img src={pg.right_thumb} alt={`right ${pg.index+1}`} className="w-full object-contain" /> : <div className="flex h-32 items-center justify-center text-xs text-[#9a9994]">╨╜╨╡╤В ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л</div>}
                    </div>
                    <div className="rounded-[8px] bg-white/70 p-2 text-xs leading-relaxed text-[#1b1a17] max-h-32 overflow-auto whitespace-pre-wrap">{pg.right_text?.slice(0,800) || "тАФ ╨┐╤Г╤Б╤В╨╛ тАФ"}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {slug === "page-numbers" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">╨Э╨╛╨╝╨╡╤А╨░ ╤Б╤В╤А╨░╨╜╨╕╤Ж тАФ ╨┐╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡ ╨╕ ╤Б╤В╨╕╨╗╤М</p>
            <p className="text-xs text-[#6b6a63]">╨Ы╨╡╨│╨║╨╛ ╨┤╨╛╨▒╨░╨▓╨╗╤П╨╣╤В╨╡ ╨╜╨╛╨╝╨╡╤А╨░ ╤Б╤В╤А╨░╨╜╨╕╤Ж ╨▓ PDF ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л. ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡, ╤А╨░╨╖╨╝╨╡╤А╤Л, ╤Д╨╛╤А╨╝╨░╤В ╨╕ ╤И╤А╨╕╤Д╤В!</p>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">╨Я╨╛╨╗╨╛╨╢╨╡╨╜╨╕╨╡</label>
                <div className="mt-2">
                  <PositionGrid value={pnPosition} onChange={setPnPosition} />
                </div>
              </div>
              <div>
                <label htmlFor="pnFormat" className="block text-sm font-medium text-gray-700">╨д╨╛╤А╨╝╨░╤В</label>
                <select
                  id="pnFormat"
                  value={pnFormat}
                  onChange={(e) => setPnFormat(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="1">1</option>
                  <option value="1 / N">1 / N</option>
                  <option value="Page 1">Page 1</option>
                  <option value="Page 1 of N">Page 1 of N</option>
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium text-[#1b1a17]">╨Я╤А╨╡╨▓╤М╤О Live {pnPreview ? `${pnPreview.numPages} ╤Б╤В╤А.` : ""} {pnPreviewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : ""}</p>
              <LivePreview
                thumb={pnPreview?.pages[0]?.thumb ?? null}
                label="╨Я╤А╨╡╨▓╤М╤О"
                overlay={
                  <div className={`flex h-full w-full p-4 ${positionToFlex(pnPosition)}`}>
                    <span style={{ color: pnColor, fontSize: `${pnFontSize}px` }}>
                      {(() => {
                        const startNum = Number(pnStart) || 1;
                        const total = pnPreview?.numPages ?? 1;
                        if (pnFormat === "1") return String(startNum);
                        if (pnFormat === "1 / N") return `${startNum} / ${total}`;
                        if (pnFormat === "Page 1") return `Page ${startNum}`;
                        if (pnFormat === "Page 1 of N") return `Page ${startNum} of ${total}`;
                        return String(startNum);
                      })()}
                    </span>
                  </div>
                }
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="pnFontSize" className="block text-sm font-medium text-gray-700">╨а╨░╨╖╨╝╨╡╤А ╤И╤А╨╕╤Д╤В╨░</label>
                <select
                  id="pnFontSize"
                  value={pnFontSize}
                  onChange={(e) => setPnFontSize(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="8">8</option>
                  <option value="10">10</option>
                  <option value="12">12</option>
                  <option value="14">14</option>
                  <option value="16">16</option>
                  <option value="18">18</option>
                  <option value="24">24</option>
                  <option value="36">36</option>
                </select>
              </div>
              <div>
                <label htmlFor="pnStart" className="block text-sm font-medium text-gray-700">╨Э╨░╤З╨░╨╗╤М╨╜╤Л╨╣ ╨╜╨╛╨╝╨╡╤А</label>
                <input
                  id="pnStart"
                  type="number"
                  min={1}
                  max={100000}
                  value={pnStart}
                  onChange={(e) => setPnStart(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="pnColor" className="block text-sm font-medium text-gray-700">╨ж╨▓╨╡╤В</label>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    id="pnColor"
                    type="color"
                    value={pnColor}
                    onChange={(e) => setPnColor(e.target.value)}
                    className="h-9 w-12 rounded-md border border-gray-300 bg-white p-1"
                  />
                  <input
                    type="text"
                    value={pnColor}
                    onChange={(e) => setPnColor(e.target.value)}
                    placeholder="#000000"
                    className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="pnMarginX" className="block text-sm font-medium text-gray-700">╨Ю╤В╤Б╤В╤Г╨┐ X (px)</label>
                <input
                  id="pnMarginX"
                  type="number"
                  min={0}
                  max={100}
                  value={pnMarginX}
                  onChange={(e) => setPnMarginX(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="pnMarginY" className="block text-sm font-medium text-gray-700">╨Ю╤В╤Б╤В╤Г╨┐ Y (px)</label>
                <input
                  id="pnMarginY"
                  type="number"
                  min={0}
                  max={100}
                  value={pnMarginY}
                  onChange={(e) => setPnMarginY(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* live preview thumbnails */}
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-[#1b1a17]">╨Я╤А╨╡╨▓╤М╤О {pnPreview ? `${pnPreview.numPages} ╤Б╤В╤А.` : ""} {pnPreviewLoading ? "тАФ ╨╖╨░╨│╤А╤Г╨╖╨║╨░тАж" : ""}</p>
                {pnPreviewLoading ? (
                  <div className="grid grid-cols-3 gap-2">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="glass animate-pulse rounded-[12px] p-2">
                        <div className="aspect-[3/4] rounded bg-white/60" />
                      </div>
                    ))}
                  </div>
                ) : pnPreview && pnPreview.pages.length > 0 ? (
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {pnPreview.pages.slice(0, 8).map((p) => (
                      <div key={p.page} className="relative overflow-hidden rounded-[12px] border border-white/60 bg-white">
                        <img src={p.thumb} alt={`╤Б╤В╤А ${p.page + 1}`} className="aspect-[3/4] w-full object-cover object-top" />
                        <span className="absolute bottom-1 left-1 rounded-full bg-black/70 px-1.5 py-0.5 text-[9px] font-medium text-white">
                          {(() => {
                            const num = Number(pnStart) + p.page;
                            if (pnFormat === "1") return String(num);
                            if (pnFormat === "1 / N") return `${num} / ${pnPreview.numPages}`;
                            if (pnFormat === "Page 1") return `Page ${num}`;
                            if (pnFormat === "Page 1 of N") return `Page ${num} of ${pnPreview.numPages}`;
                            return String(num);
                          })()}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[12px] border border-dashed border-black/10 bg-white/50 p-4 text-center text-xs text-[#6b6a63]">╨Я╤А╨╡╨▓╤М╤О ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛</div>
                )}
                <p className="text-[11px] text-[#6b6a63]">╨Я╤А╨╕╨╝╨╡╤А ╨╛╤В╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П ╤Д╨╛╤А╨╝╨░╤В╨░ ┬л{pnFormat}┬╗ ╨▓ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕ ┬л{pnPosition}┬╗.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {slug === "pdf-to-jpg" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">PDF тЖТ JPG тАФ ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕</p>
            <p className="text-xs text-[#6b6a63]">╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨║╨░╤З╨╡╤Б╤В╨▓╨╛ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣ (DPI). ╨Т╤Л╤И╨╡ DPI тАФ ╤З╤С╤В╤З╨╡, ╨╜╨╛ ╨▒╨╛╨╗╤М╤И╨╡ ╤А╨░╨╖╨╝╨╡╤А ╨░╤А╤Е╨╕╨▓╨░.</p>
            <div>
              <label htmlFor="pdfToJpgDpi" className="block text-sm font-medium text-gray-700">DPI</label>
              <select
                id="pdfToJpgDpi"
                value={pdfToJpgDpi}
                onChange={(e) => setPdfToJpgDpi(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="72">72 DPI (╨▒╤Л╤Б╤В╤А╨╛, ╨╝╨╡╨╜╤М╤И╨╡ ╤Д╨░╨╣╨╗)</option>
                <option value="150">150 DPI (╤А╨╡╨║╨╛╨╝╨╡╨╜╨┤╤Г╨╡╨╝╨╛╨╡)</option>
                <option value="300">300 DPI (╨▓╤Л╤Б╨╛╨║╨╛╨╡ ╨║╨░╤З╨╡╤Б╤В╨▓╨╛)</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {slug === "jpg-to-pdf" && (
        <div className="space-y-4">
          <div className="glass rounded-[16px] p-5 space-y-4">
            <p className="text-[13px] font-medium text-[#1b1a17]">JPG тЖТ PDF тАФ ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕</p>
            <p className="text-xs text-[#6b6a63]">╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╛╤А╨╕╨╡╨╜╤В╨░╤Ж╨╕╤О, ╤А╨░╨╖╨╝╨╡╤А ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╨╕ ╨┐╨╛╨╗╤П.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="jpgToPdfOrientation" className="block text-sm font-medium text-gray-700">╨Ю╤А╨╕╨╡╨╜╤В╨░╤Ж╨╕╤П</label>
                <select
                  id="jpgToPdfOrientation"
                  value={jpgToPdfOrientation}
                  onChange={(e) => setJpgToPdfOrientation(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="portrait">╨Ъ╨╜╨╕╨╢╨╜╨░╤П (portrait)</option>
                  <option value="landscape">╨Р╨╗╤М╨▒╨╛╨╝╨╜╨░╤П (landscape)</option>
                </select>
              </div>
              <div>
                <label htmlFor="jpgToPdfPageSize" className="block text-sm font-medium text-gray-700">╨а╨░╨╖╨╝╨╡╤А ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л</label>
                <select
                  id="jpgToPdfPageSize"
                  value={jpgToPdfPageSize}
                  onChange={(e) => setJpgToPdfPageSize(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="A4">A4</option>
                  <option value="A3">A3</option>
                  <option value="Letter">Letter</option>
                  <option value="fit">╨Я╨╛ ╤А╨░╨╖╨╝╨╡╤А╤Г ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П (fit)</option>
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="jpgToPdfMargin" className="block text-sm font-medium text-gray-700">╨Я╨╛╨╗╤П</label>
              <select
                id="jpgToPdfMargin"
                value={jpgToPdfMargin}
                onChange={(e) => setJpgToPdfMargin(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="none">╨С╨╡╨╖ ╨┐╨╛╨╗╨╡╨╣</option>
                <option value="small">╨Ь╨░╨╗╨╡╨╜╤М╨║╨╕╨╡</option>
                <option value="medium">╨б╤А╨╡╨┤╨╜╨╕╨╡</option>
                <option value="large">╨С╨╛╨╗╤М╤И╨╕╨╡</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <StickyBar
        fileCount={slug === "compare" ? (compareFile1 ? 1 : 0) + (compareFile2 ? 1 : 0) : files.length}
        onAddMore={() => {
          const el = document.querySelector<HTMLInputElement>('input[type="file"]');
          if (el) el.click();
          else window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        onProcess={handleProcess}
        loading={slug === "compare" ? compareLoading : loading}
        disabled={slug === "compare" ? !compareFile1 || !compareFile2 : files.length === 0 || (slug === "merge" && pagesLoading)}
        label={slug === "compare" ? "╨б╤А╨░╨▓╨╜╨╕╤В╤М" : "╨Ю╨▒╤А╨░╨▒╨╛╤В╨░╤В╤М"}
      />

      {/* Error toast */}
      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Download block */}
      {downloadUrl && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-4">
          <p className="text-sm font-medium text-green-800">╨У╨╛╤В╨╛╨▓╨╛ тАФ ╤Д╨░╨╣╨╗ ╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜ ╨┤╨╗╤П ╤Б╨║╨░╤З╨╕╨▓╨░╨╜╨╕╤П</p>
          <button
            type="button"
            onClick={handleDownload}
            className="mt-3 rounded-lg bg-green-600 px-6 py-2 text-sm font-semibold text-white hover:bg-green-700"
          >
            ╨б╨║╨░╤З╨░╤В╤М {downloadName}
          </button>
          <p className="mt-2 text-xs text-green-700">╨б╤Б╤Л╨╗╨║╨░ ╨▒╤Г╨┤╨╡╤В ╨╛╤В╨╛╨╖╨▓╨░╨╜╨░ ╨┐╨╛╤Б╨╗╨╡ ╨║╨╗╨╕╨║╨░ (blob URL).</p>
        </div>
      )}
    </div>
  );
}
