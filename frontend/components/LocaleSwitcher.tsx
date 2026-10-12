"use client";
import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/navigation";
import Icon from "./Icon";
export default function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  return <button className="locale-button" onClick={() => router.replace(pathname, { locale: locale === "ru" ? "en" : "ru" })} aria-label={locale === "ru" ? "Switch to English" : "Переключить на русский"}><Icon name="globe" size={16} />{locale === "ru" ? "RU" : "EN"}</button>;
}
