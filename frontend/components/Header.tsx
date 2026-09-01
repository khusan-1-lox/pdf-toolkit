"use client";
import {Link} from "@/navigation";
import LocaleSwitcher from "./LocaleSwitcher";
import {useTranslations} from 'next-intl';
import { signIn, signOut, useSession } from "next-auth/react";

export function Header() {
  const t = useTranslations('header');
  const tc = useTranslations('common');
  const { data: session, status } = useSession();
  const isLocal = process.env.NEXT_PUBLIC_DISABLE_AUTH === "true";

  return (
    <header className="sticky top-0 z-40 border-b border-white/40 glass">
      <div className="mx-auto flex max-w-[1120px] items-center justify-between px-6 py-3.5">
        <Link href="/" className="flex items-center gap-3">
          <div className="glass-icon flex h-9 w-9 items-center justify-center rounded-xl">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0a84ff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <div className="leading-none">
            <div className="flex items-center gap-2 text-[17px] font-semibold tracking-[-0.02em]">PDF Toolkit <span className="rounded-full bg-amber-400 px-2 py-0.5 text-[10px] font-bold tracking-[0.08em] text-black">{tc('beta')}</span></div>
            <div className="text-[11px] font-medium tracking-[0.08em] text-[#6b6a63]">{t('subtitle')}</div>
          </div>
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <Link href="/" className="hidden sm:inline text-[13px] font-medium text-[#6b6a63] hover:text-black">{t('dashboard')}</Link>
          <LocaleSwitcher/>
          {isLocal ? (
            <span className="glass-icon rounded-full px-3 py-1.5 text-xs font-medium text-emerald-700">{tc('localBadge')}</span>
          ) : status === "loading" ? (
            <span className="text-xs text-gray-400">{t('loading')}</span>
          ) : session?.user ? (
            <>
              <span className="hidden sm:inline max-w-[180px] truncate text-xs font-medium text-[#1b1a17] glass-icon rounded-full px-3 py-1.5">{session.user.email}</span>
              <button onClick={() => signOut()} className="rounded-full border border-black/10 bg-white/80 px-3.5 py-1.5 text-xs font-medium backdrop-blur hover:bg-white">{t('signOut')}</button>
            </>
          ) : (
            <button onClick={() => signIn("google")} className="rounded-full bg-[#0a84ff] px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-[#0a6ee0]">{t('signIn')}</button>
          )}
        </nav>
      </div>
    </header>
  );
}
export default Header;
