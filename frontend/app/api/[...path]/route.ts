import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Resolve the server at request time so the desktop app can use an available port.
async function proxy(request: NextRequest, {params}: {params: {path: string[]}}) {
  const base = process.env.PDF_TOOLKIT_API_URL || process.env.API_URL || "http://127.0.0.1:8000";
  const target = new URL(`/api/${params.path.map(encodeURIComponent).join("/")}`, base);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ["content-type", "accept"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180_000);
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, {once: true});
  try {
    const upstream = await fetch(target, {
      method: request.method, headers, cache: "no-store", signal: controller.signal,
      ...(request.method === "GET" || request.method === "HEAD" ? {} : {body: request.body, duplex: "half"}),
    } as RequestInit);
    const responseHeaders = new Headers(upstream.headers);
    for (const name of ["connection", "transfer-encoding", "content-encoding", "content-length"]) responseHeaders.delete(name);
    responseHeaders.set("cache-control", "no-store");
    return new Response(upstream.body, {status: upstream.status, headers: responseHeaders});
  } catch {
    return Response.json({detail: "PDF service is unavailable. Restart the app and try again."}, {status: 502});
  } finally {
    clearTimeout(timeout);
    request.signal.removeEventListener("abort", abort);
  }
}
export {proxy as GET, proxy as POST};
