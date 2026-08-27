import type { Metadata } from "next";
import Header from "../components/Header";
import Providers from "../components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "PDF Toolkit — BETA",
  description: "PDF Toolkit BETA — 25 tools, private, free MCP. Auto-deletes after 5 min.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased selection:bg-[#0a84ff]/20" style={{ background: "radial-gradient(1200px 600px at 20% -10%, rgba(10,132,255,0.08), transparent 55%), radial-gradient(1000px 500px at 90% 0%, rgba(255,159,67,0.06), transparent 60%), #fbfaf8" }}>
        <Providers>
          <Header />
          <main className="mx-auto max-w-[1120px] px-6 py-10">{children}</main>
          <footer className="mx-auto max-w-[1120px] px-6 pb-8 text-xs text-[#9a9994]">Files never leave your VPS · Auto-deleted after 5 min · No tracking</footer>
        </Providers>
      </body>
    </html>
  );
}
