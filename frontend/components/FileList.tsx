"use client";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type FileListProps = {
  files: File[];
  onRemove: (index: number) => void;
};

export function FileList({ files, onRemove }: FileListProps) {
  if (files.length === 0) return null;

  return (
    <ul className="mt-4 divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
      {files.map((file, idx) => (
        <li
          key={`${file.name}-${idx}`}
          className="flex items-center justify-between px-4 py-3"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-gray-900">
              {file.name}
            </p>
            <p className="text-xs text-gray-500">
              {formatSize(file.size)} • {file.type || "unknown"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="ml-4 rounded px-2 py-1 text-sm text-red-600 hover:bg-red-50"
            aria-label={`Remove ${file.name}`}
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}

export default FileList;
