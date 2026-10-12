"use client";
import { useEffect, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { Link } from "@/navigation";
import Icon from "@/components/Icon";
import { CATEGORIES, TOOLS } from "@/lib/tools";
export default function Dashboard() {
  const lang = useLocale() === "ru" ? "ru" : "en";
  const ru = lang === "ru";
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLElement && (e.target.matches("input,textarea,select") || e.target.isContentEditable))) { e.preventDefault(); search.current?.focus(); }
      if (e.key === "Escape" && document.activeElement === search.current) { setQuery(""); search.current?.blur(); }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const filtered = TOOLS.filter(tool => (category === "all" || tool.category === category) && `${tool.title.ru} ${tool.title.en} ${tool.description[lang]}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="home-page">
    <section className="hero">
      <div className="hero-copy">
        <div className="eyebrow"><span className="status-dot" />{ru ? "МЕНЬШЕ РУТИНЫ. БОЛЬШЕ ВОЗМОЖНОСТЕЙ." : "LESS BUSYWORK. MORE POSSIBILITIES."}</div>
        <h1>{ru ? "Большие планы." : "Big ideas."}<br /><span>{ru ? "Лёгкие PDF." : "Easy PDFs."}</span><svg className="hero-swoosh" viewBox="0 0 260 20" fill="none" aria-hidden="true"><path d="M3 15C64 3 154 1 255 8" stroke="currentColor" strokeWidth="5" strokeLinecap="round" /></svg></h1>
        <p className="hero-description">{ru ? "Объединяйте, редактируйте и превращайте документы в то, что вам нужно. Всё под рукой. Всё просто." : "Merge, edit and turn your documents into exactly what you need. Everything in reach. Effortlessly simple."}</p>
        <div className="hero-actions"><a className="btn-primary" href="#tools">{ru ? "Выбрать инструмент" : "Explore the tools"}<Icon name="arrow" size={18} /></a><span className="hero-note"><Icon name="check" size={16} />{ru ? "Без регистрации" : "No sign-up needed"}</span></div>
        <div className="hero-features"><span><Icon name="shield" size={16} />{ru ? "Автоудаление файлов" : "Automatic file cleanup"}</span><span><Icon name="bolt" size={16} />{ru ? "Прямо в браузере" : "Right in your browser"}</span></div>
      </div>
      <div className="hero-art" aria-hidden="true">
        <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
        <div className="floating-chip chip-word"><span className="mini-format word-format">W</span><span>Word</span><Icon name="check" size={14} /></div>
        <div className="paper paper-back"><div className="paper-fold" /></div>
        <div className="paper paper-main"><div className="paper-fold" /><div className="paper-symbol"><Icon name="file" size={30} /></div><div className="paper-title">PDF</div><div className="paper-line long" /><div className="paper-line" /><div className="paper-line short" /><div className="paper-chart"><i /><i /><i /><i /><i /></div><div className="paper-footer"><span /> PDF TOOLKIT</div></div>
        <div className="floating-chip chip-done"><span className="done-circle"><Icon name="check" size={15} /></span><div><strong>{ru ? "Готово к отправке" : "Ready to share"}</strong><small>document.pdf <span>·</span> 240 KB</small></div></div>
        <div className="floating-tile tile-image"><Icon name="image" size={26} /></div><div className="floating-tile tile-merge"><Icon name="merge" size={25} /></div><span className="art-star star-one">✦</span><span className="art-star star-two">✦</span>
      </div>
    </section>
    <section id="tools" className="tools-section">
      <div className="section-heading"><div><div className="eyebrow muted">{ru ? "ОДИН НАБОР. ЛЮБАЯ ЗАДАЧА." : "ONE TOOLKIT. EVERYDAY POSSIBILITIES."}</div><h2>{ru ? "Что сделаем с PDF?" : "What’s next for your PDF?"}</h2></div><label className="tool-search"><Icon name="search" size={19} /><input ref={search} value={query} onChange={e => setQuery(e.target.value)} placeholder={ru ? "Найти инструмент…" : "Find a tool…"} aria-label={ru ? "Поиск инструментов" : "Search tools"} />{query ? <button onClick={() => setQuery("")} aria-label={ru ? "Очистить поиск" : "Clear search"}><Icon name="close" size={15} /></button> : <kbd>/</kbd>}</label></div>
      <div className="category-row" aria-label={ru ? "Категории" : "Categories"}>{CATEGORIES.map(cat => <button key={cat.id} className={`category-tab ${category === cat.id ? "active" : ""}`} onClick={() => setCategory(cat.id)} aria-pressed={category === cat.id}><Icon name={cat.icon} size={16} />{cat.title[lang]}{cat.id === "all" && <span>{TOOLS.length}</span>}</button>)}</div>
      <div className="catalog-meta"><span>{query ? (ru ? `Результаты поиска: ${filtered.length}` : `${filtered.length} tools found`) : category === "all" ? (ru ? "Все нужные инструменты — в одном месте" : "Your everyday document essentials, together") : CATEGORIES.find(c => c.id === category)?.title[lang]}</span><span><span className="tiny-dot" />{ru ? "Можно начать прямо сейчас" : "Ready when you are"}</span></div>
      <div className="tool-grid" key={`${category}-${query}`}>
        {filtered.map((tool, i) => <Link className="tool-card" href={`/tools/${tool.slug}`} key={tool.slug} style={{ animationDelay: `${Math.min(i, 7) * 35}ms` }}><div className="card-top"><span className={`tool-icon tone-${tool.color}`}><Icon name={tool.icon} size={25} /></span>{tool.popular && <span className="popular-badge">{ru ? "Популярное" : "Popular"}</span>}<span className="card-arrow"><Icon name="arrow" size={18} /></span></div><h3>{tool.title[lang]}</h3><p>{tool.description[lang]}</p></Link>)}
      </div>
      {filtered.length === 0 && <div className="empty-search"><Icon name="search" size={35} /><h3>{ru ? "Такого инструмента не нашлось" : "No matching tools"}</h3><p>{ru ? "Попробуйте другое название или выберите все категории." : "Try a different name or search across all categories."}</p><button className="btn-secondary" onClick={() => { setCategory("all"); setQuery(""); }}>{ru ? "Показать всё" : "Show all tools"}</button></div>}
    </section>
    <section className="workflow-banner"><div className="workflow-mark"><Icon name="workflow" size={30} /></div><div><span className="eyebrow muted">{ru ? "СДЕЛАЙТЕ ЕЩЁ ПРОЩЕ" : "MAKE IT EVEN SIMPLER"}</span><h2>{ru ? "Несколько действий. Один результат." : "A few steps. One beautiful result."}</h2><p>{ru ? "Сжать, повернуть, добавить нумерацию — соберите свою цепочку действий." : "Compress, rotate, number the pages — create your own sequence."}</p></div><Link className="btn-secondary" href="/tools/workflows">{ru ? "Создать цепочку" : "Create a workflow"}<Icon name="arrow" size={17} /></Link></section>
    <section className="how-it-works"><div><span>01</span><h3>{ru ? "Выберите инструмент" : "Pick your tool"}</h3><p>{ru ? "Для каждой задачи найдётся своё решение." : "There’s a tool for what you have in mind."}</p></div><div><span>02</span><h3>{ru ? "Добавьте документы" : "Add your documents"}</h3><p>{ru ? "Перетащите файлы и настройте результат." : "Drop in your files and make it your own."}</p></div><div><span>03</span><h3>{ru ? "Скачайте результат" : "Make it yours"}</h3><p>{ru ? "Готовый файл — и можно двигаться дальше." : "Download the result and get on with your day."}</p></div></section>
  </div>;
}
