import type { Metadata } from "next";
import {NextIntlClientProvider} from "next-intl";
import {getMessages, setRequestLocale} from "next-intl/server";
import Header from "../../components/Header";
import Providers from "../../components/Providers";
import "../globals.css";
export async function generateMetadata({params:{locale}}:{params:{locale:string}}): Promise<Metadata> {
  return { title: "PDF Toolkit — " + (locale === "ru" ? "Лёгкие PDF" : "Easy PDFs"), description: locale === "ru" ? "Объединяйте, редактируйте, сжимайте и конвертируйте PDF. Удобные инструменты для документов." : "Merge, edit, compress and convert PDFs. Your everyday document toolkit.", alternates: {languages:{en:"/en",ru:"/ru","x-default":"/en"}} };
}
export function generateStaticParams(){return [{locale:"en"},{locale:"ru"}];}
export default async function LocaleLayout({children, params:{locale}}:{children:React.ReactNode,params:{locale:string}}){
  setRequestLocale(locale);
  const messages = await getMessages();
  const ru = locale === "ru";
  return <html lang={locale}><body><NextIntlClientProvider messages={messages}><Providers><Header/><main className="site-main">{children}</main><footer className="site-footer"><span className="footer-brand">pdftoolkit.</span><span>{ru ? "Документы проще. Каждый день." : "Documents made easier. Every day."}</span><div><span>{ru ? "Временные файлы удаляются автоматически" : "Temporary files are cleaned up automatically"}</span><a href="https://github.com/khusan-1-lox/pdf-toolkit" target="_blank" rel="noreferrer">GitHub ↗</a></div></footer></Providers></NextIntlClientProvider></body></html>;
}
