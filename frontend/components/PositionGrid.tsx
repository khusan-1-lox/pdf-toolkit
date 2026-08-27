"use client";

type PositionValue =
  | "center"
  | "top-left"
  | "top-center"
  | "top-right"
  | "center-left"
  | "center-right"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right";

type PositionGridProps = {
  value: string;
  onChange: (v: string) => void;
};

const POSITIONS: PositionValue[] = [
  "top-left",
  "top-center",
  "top-right",
  "center-left",
  "center",
  "center-right",
  "bottom-left",
  "bottom-center",
  "bottom-right",
];

const LABELS: Record<PositionValue, string> = {
  "top-left": "Сверху слева",
  "top-center": "Сверху по центру",
  "top-right": "Сверху справа",
  "center-left": "Слева по центру",
  "center": "По центру",
  "center-right": "Справа по центру",
  "bottom-left": "Снизу слева",
  "bottom-center": "Снизу по центру",
  "bottom-right": "Снизу справа",
};

export function PositionGrid({ value, onChange }: PositionGridProps) {
  return (
    <div className="grid grid-cols-3 gap-1 w-fit">
      {POSITIONS.map((pos) => {
        const active = value === pos;
        return (
          <button
            key={pos}
            type="button"
            aria-label={LABELS[pos]}
            title={LABELS[pos]}
            onClick={() => onChange(pos)}
            className={`flex h-8 w-8 items-center justify-center rounded-md border text-xs transition ${
              active
                ? "bg-[#e30613] text-white border-[#e30613] shadow-sm"
                : "bg-white border-black/10 text-[#1b1a17] hover:bg-gray-50"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                active ? "bg-white" : "bg-black/20"
              }`}
            />
          </button>
        );
      })}
    </div>
  );
}

export default PositionGrid;
