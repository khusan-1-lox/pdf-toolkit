export async function callTool(slug: string, files: File[], opts: Record<string, unknown> = {}): Promise<Blob> {
  const fd = new FormData();
  let field: string;
  if (slug === "merge" || slug === "jpg-to-pdf") field = "files";
  else if (slug === "rotate") field = files.length > 1 ? "files" : "file";
  else if (slug === "compare") {
    // compare uses file1/file2 directly, but fallback if callTool invoked with 2 files
    files.forEach((f, i) => fd.append(i === 0 ? "file1" : "file2", f));
    // opts are not needed for compare, but still append if any
    Object.entries(opts).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      if (v instanceof File) { fd.append(k, v); return; }
      if (v instanceof Blob) { fd.append(k, v); return; }
      const s = String(v);
      if (s.trim() === "") return;
      fd.append(k, s);
    });
    // cannot return blob for compare; caller should use callCompare
    // but keep fetch blob fallback
    const r = await fetch(`/api/${slug}`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    return r.blob();
  } else field = "file";
  files.forEach((f) => fd.append(field, f));
  Object.entries(opts).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    // Handle File objects (e.g., watermark image, sign image)
    if (v instanceof File) {
      fd.append(k, v);
      return;
    }
    if (v instanceof Blob) {
      fd.append(k, v);
      return;
    }
    const s = String(v);
    if (s.trim() === "") return;
    fd.append(k, s);
  });
  // explicit order handling for merge (ensures JSON string passed as-is)
  if (slug === "merge" && opts.order !== undefined && opts.order !== null) {
    if (!fd.has("order") && String(opts.order).trim() !== "") {
      fd.set("order", String(opts.order));
    }
  }
  const r = await fetch(`/api/${slug}`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.blob();
}

export async function callCompare(file1: File, file2: File): Promise<{ pages: { index: number; diff: boolean; left_thumb: string; right_thumb: string; left_text: string; right_text: string }[] }> {
  const fd = new FormData();
  fd.append("file1", file1);
  fd.append("file2", file2);
  const r = await fetch(`/api/compare`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
