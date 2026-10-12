"use client";
import { Link, usePathname } from "@/navigation";
import { useLocale } from "next-intl";
import LocaleSwitcher from "./LocaleSwitcher";
import Icon from "./Icon";
export function Header() {
  const ru = useLocale() === "ru";
  const pathname = usePathname();
  return <header className="site-header"><div className="header-inner"><Link href="/" className="brand" aria-label="PDF Toolkit"><span className="brand-mark"><Icon name="layers" size={24} /></span><span>pdf<span className="brand-light">toolkit</span><span className="brand-dot">.</span></span></Link><nav className="header-nav" aria-label={ru ? "Главная навигация" : "Main navigation"}><Link href="/#tools" className={pathname === "/" ? "nav-link active" : "nav-link"}>{ru ? "Все инструменты" : "All tools"}</Link><Link href="/tools/workflows" className={pathname === "/tools/workflows" ? "nav-link active" : "nav-link"}><Icon name="workflow" size={16} />{ru ? "Цепочки действий" : "Workflows"}</Link></nav><div className="header-right"><span className="header-free"><span className="status-dot" />{ru ? "Открытый код" : "Open source"}</span><LocaleSwitcher /></div></div></header>;
}
export default Header;
