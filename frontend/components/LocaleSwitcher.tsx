"use client";
import {useLocale} from 'next-intl';
import {usePathname, useRouter} from '@/navigation';

export default function LocaleSwitcher(){
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const nextLocale = locale === 'en' ? 'ru' : 'en';
  const label = locale === 'en' ? 'RU' : 'EN';
  return (
    <button
      onClick={()=> router.replace(pathname as any, {locale: nextLocale as any})}
      aria-label={`Switch to ${nextLocale}`}
      className="rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-xs font-medium backdrop-blur hover:bg-white"
    >
      {label}
    </button>
  );
}
