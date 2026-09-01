import type { Metadata } from "next";
import {NextIntlClientProvider} from 'next-intl';
import {getMessages, setRequestLocale} from 'next-intl/server';
import Header from "../../components/Header";
import Providers from "../../components/Providers";
import "../globals.css";

export async function generateMetadata({params:{locale}}:{params:{locale:string}}): Promise<Metadata> {
  try {
    const messages: any = (await import(`../../messages/${locale}.json`)).default;
    return {
      title: messages.dashboard?.title || "PDF Toolkit — BETA",
      description: messages.dashboard?.subtitle || "PDF Toolkit BETA — 25 tools",
      alternates: { languages: { en: '/en', ru: '/ru', 'x-default': '/en' } }
    };
  } catch {
    return {
      title: "PDF Toolkit — BETA",
      description: "PDF Toolkit BETA — 25 tools",
      alternates: { languages: { en: '/en', ru: '/ru', 'x-default': '/en' } }
    };
  }
}

export function generateStaticParams(){ return [{locale:'en'}, {locale:'ru'}]; }

export default async function LocaleLayout({children, params:{locale}}:{children:React.ReactNode, params:{locale:string}}){
  setRequestLocale(locale);
  const messages = await getMessages();
  return (
    <html lang={locale}>
      <body className="min-h-screen antialiased selection:bg-[#0a84ff]/20" style={{ background: "radial-gradient(1200px 600px at 20% -10%, rgba(10,132,255,0.08), transparent 55%), radial-gradient(1000px 500px at 90% 0%, rgba(255,159,67,0.06), transparent 60%), #fbfaf8" }}>
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <Header />
            <main className="mx-auto max-w-[1120px] px-6 py-10">{children}</main>
            <footer className="mx-auto max-w-[1120px] px-6 pb-8 text-xs text-[#9a9994]">Files never leave your VPS · Auto-deleted after 5 min · No tracking</footer>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
