export async function responseError(response: Response): Promise<Error> {
  const text = await response.text();
  try {
    const data = JSON.parse(text);
    const detail = data.detail || data.message;
    return new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((item: {msg?: string}) => item.msg || "Invalid value").join("; ") : text);
  } catch { return new Error(text || `Request failed (${response.status})`); }
}
export async function callTool(slug: string, files: File[], opts: Record<string, unknown> = {}): Promise<Blob> {
  const fd = new FormData();
  const field = ["merge", "organize-pdf", "jpg-to-pdf"].includes(slug) || (slug === "rotate" && files.length > 1) ? "files" : "file";
  files.forEach((file) => fd.append(field, file));
  Object.entries(opts).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    fd.append(key, value instanceof Blob ? value : typeof value === "object" ? JSON.stringify(value) : String(value));
  });
  const response = await fetch(`/api/${slug}`, {method: "POST", body: fd});
  if (!response.ok) throw await responseError(response);
  return response.blob();
}
export type Comparison = {pages: {index: number; diff: boolean; left_thumb: string; right_thumb: string; left_text: string; right_text: string}[]};
export async function callCompare(file1: File, file2: File): Promise<Comparison> {
  const fd = new FormData(); fd.append("file1", file1); fd.append("file2", file2);
  const response = await fetch("/api/compare", {method: "POST", body: fd});
  if (!response.ok) throw await responseError(response);
  return response.json();
}
export type PreviewPage = {page: number; thumb: string; width?: number; height?: number};
export async function previewPdf(file: File, offset = 0, signal?: AbortSignal): Promise<{pages: PreviewPage[]; numPages: number}> {
  const fd = new FormData(); fd.append("file", file); fd.append("offset", String(offset)); fd.append("limit", "50");
  const response = await fetch("/api/preview", {method: "POST", body: fd, signal});
  if (!response.ok) throw await responseError(response);
  return response.json();
}
