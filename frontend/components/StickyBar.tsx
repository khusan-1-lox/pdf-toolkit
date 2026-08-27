"use client";

type StickyBarProps = {
  fileCount: number;
  onAddMore?: () => void;
  onProcess: () => void;
  loading?: boolean;
  disabled?: boolean;
  label?: string;
};

export function StickyBar({
  fileCount,
  onAddMore,
  onProcess,
  loading = false,
  disabled = false,
  label,
}: StickyBarProps) {
  const handleAddMore = () => {
    if (onAddMore) {
      onAddMore();
      return;
    }
    // fallback: click the dropzone input
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    if (input) input.click();
    else window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="sticky bottom-0 z-20 flex items-center justify-between border-t bg-white px-6 py-3 shadow-lg">
      <div className="flex items-center gap-2 text-sm text-[#1b1a17]">
        <span className="font-medium">{fileCount} файлов</span>
        <span className="text-[#9a9994]">·</span>
        <button
          type="button"
          onClick={handleAddMore}
          className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs font-medium hover:bg-gray-50"
        >
          Добавить еще файлы
        </button>
      </div>
      <button
        type="button"
        onClick={onProcess}
        disabled={disabled || loading}
        className="rounded-lg bg-[#e30613] px-6 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-[#cc0510] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Обработка…" : label ?? "Обработать"}
      </button>
    </div>
  );
}

export default StickyBar;
