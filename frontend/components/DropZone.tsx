"use client";

import { useCallback, useState } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { useParams } from "next/navigation";

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

const DEFAULT_ACCEPT = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  // fallback for any image type
  "image/*": [".jpg", ".jpeg", ".png", ".webp"],
};

const ACCEPT_PDF: Record<string, string[]> = {
  "application/pdf": [".pdf"],
};

export function getAcceptForSlug(slug?: string): Record<string, string[]> {
  if (!slug) return DEFAULT_ACCEPT;
  switch (slug) {
    case "word-to-pdf":
      return {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
        "application/msword": [".doc"],
      };
    case "excel-to-pdf":
      return {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        "application/vnd.ms-excel": [".xls"],
      };
    case "ppt-to-pdf":
      return {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
        "application/vnd.ms-powerpoint": [".ppt"],
      };
    case "html-to-pdf":
      return {
        "text/html": [".html", ".htm"],
        "application/pdf": [".pdf"],
      };
    case "jpg-to-pdf":
      return {
        "image/jpeg": [".jpg", ".jpeg"],
        "image/png": [".png"],
        "image/webp": [".webp"],
        "image/*": [".jpg", ".jpeg", ".png", ".webp"],
      };
    default:
      if (slug.startsWith("pdf-to-")) return ACCEPT_PDF;
      if (slug === "pdf-to-pdfa" || slug === "pdfa" || slug === "ocr-pdf" || slug === "repair-pdf" || slug === "repair") return ACCEPT_PDF;
      return ACCEPT_PDF;
  }
}

type DropZoneProps = {
  onFiles: (files: File[]) => void;
  maxFiles?: number;
  accept?: Record<string, string[]>;
};

export function DropZone({ onFiles, maxFiles = 10, accept }: DropZoneProps) {
  const [error, setError] = useState<string | null>(null);
  const params = useParams() as { slug?: string } | null;
  const slugFromParams = params?.slug as string | undefined;
  const resolvedAccept = accept ?? getAcceptForSlug(slugFromParams);

  const onDrop = useCallback(
    (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      setError(null);

      if (fileRejections.length > 0) {
        const messages = fileRejections.flatMap((r) =>
          r.errors.map((e) => `${r.file.name}: ${e.message}`)
        );
        setError(messages.join("; "));
      }

      const valid = acceptedFiles.filter((f) => {
        if (f.size > MAX_FILE_SIZE) {
          setError((prev) =>
            prev ? `${prev}; ${f.name} exceeds 50MB` : `${f.name} exceeds 50MB`
          );
          return false;
        }
        return true;
      });

      if (valid.length === 0) return;

      if (valid.length > maxFiles) {
        setError(`Max ${maxFiles} files per request`);
        onFiles(valid.slice(0, maxFiles));
        return;
      }

      onFiles(valid);
    },
    [onFiles, maxFiles]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: resolvedAccept,
      maxSize: MAX_FILE_SIZE,
      maxFiles,
    });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
          isDragActive
            ? "border-blue-500 bg-blue-50"
            : isDragReject
              ? "border-red-400 bg-red-50"
              : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100"
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-lg font-medium text-gray-700">
          {isDragActive ? "Кидай" : "Перетащи PDF сюда"}
        </p>
        <p className="mt-1 text-sm text-gray-500">
          PDF, JPG, PNG до 50MB, до {maxFiles} файлов
        </p>
        <p className="mt-2 text-xs text-gray-400">или кликни для выбора</p>
      </div>
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default DropZone;
