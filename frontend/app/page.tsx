"use client";
import Link from "next/link";
import { useState } from "react";

type Tool = { slug: string; title: string; desc: string; meta: string; span: string; cat: string; icon: string };
type Category = { id: string; label: string; title: string; subtitle: string };

const iconSvgs: Record<string,string> = {
  "merge": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M4.97883 9.68508C2.99294 8.89073 2 8.49355 2 8C2 7.50645 2.99294 7.10927 4.97883 6.31492L7.7873 5.19153C9.77318 4.39718 10.7661 4 12 4C13.2339 4 14.2268 4.39718 16.2127 5.19153L19.0212 6.31492C21.0071 7.10927 22 7.50645 22 8C22 8.49355 21.0071 8.89073 19.0212 9.68508L16.2127 10.8085C14.2268 11.6028 13.2339 12 12 12C10.7661 12 9.77318 11.6028 7.7873 10.8085L4.97883 9.68508Z"/><path stroke-linecap="round" d="M22 12C22 12 21.0071 12.8907 19.0212 13.6851L16.2127 14.8085C14.2268 15.6028 13.2339 16 12 16C10.7661 16 9.77318 15.6028 7.7873 14.8085L4.97883 13.6851C2.99294 12.8907 2 12 2 12"/><path stroke-linecap="round" d="M22 16C22 16 21.0071 16.8907 19.0212 17.6851L16.2127 18.8085C14.2268 19.6028 13.2339 20 12 20C10.7661 20 9.77318 19.6028 7.7873 18.8085L4.97883 17.6851C2.99294 16.8907 2 16 2 16"/></g></svg>`,
  "split": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-linecap="round" stroke-width="1.5"><path d="M16.4013 20.5L6 2M22 19C22 20.6569 20.6569 22 19 22C17.3431 22 16 20.6569 16 19C16 17.3431 17.3431 16 19 16C20.6569 16 22 17.3431 22 19Z"/><path d="M7.59865 20.5L18 2M2 19C2 20.6569 3.34315 22 5 22C6.65685 22 8 20.6569 8 19C8 17.3431 6.65685 16 5 16C3.34315 16 2 17.3431 2 19Z"/></g></svg>`,
  "delete": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path stroke-linecap="round" d="M20.5001 6H3.5"/><path stroke-linecap="round" d="M18.8332 8.5L18.3732 15.3991C18.1962 18.054 18.1077 19.3815 17.2427 20.1907C16.3777 21 15.0473 21 12.3865 21H11.6132C8.95235 21 7.62195 21 6.75694 20.1907C5.89194 19.3815 5.80344 18.054 5.62644 15.3991L5.1665 8.5"/><path stroke-linecap="round" d="M9.5 11L10 16"/><path stroke-linecap="round" d="M14.5 11L14 16"/><path d="M6.5 6C6.55588 6 6.58382 6 6.60915 5.99936C7.43259 5.97849 8.15902 5.45491 8.43922 4.68032C8.44784 4.65649 8.45667 4.62999 8.47434 4.57697L8.57143 4.28571C8.65431 4.03708 8.69575 3.91276 8.75071 3.8072C8.97001 3.38607 9.37574 3.09364 9.84461 3.01877C9.96213 3 10.0932 3 10.3553 3H13.6447C13.9068 3 14.0379 3 14.1554 3.01877C14.6243 3.09364 15.03 3.38607 15.2493 3.8072C15.3043 3.91276 15.3457 4.03708 15.4286 4.28571L15.5257 4.57697C15.5433 4.62992 15.5522 4.65651 15.5608 4.68032C15.841 5.45491 16.5674 5.97849 17.3909 5.99936C17.4162 6 17.4441 6 17.5 6"/></g></svg>`,
  "rotate": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path fill="none" stroke="#e65a2a" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18.364 8.04928L17.6569 7.34217C14.5327 4.21798 9.46734 4.21798 6.34315 7.34217C3.21895 10.4664 3.21895 15.5317 6.34315 18.6559C9.46734 21.7801 14.5327 21.7801 17.6569 18.6559C19.4737 16.8391 20.234 14.3658 19.9377 11.9995M18.364 3.80664V8.04928H14.1213"/></svg>`,
  "crop": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-linecap="round" stroke-width="1.5"><path d="M22 19H13C9.22876 19 7.34315 19 6.17157 17.8284C5 16.6569 5 14.7712 5 11V2"/><path d="M8 5H11C14.7712 5 16.6569 5 17.8284 6.17157C19 7.34315 19 9.22876 19 13V16M2 5H5M19 19V22"/></g></svg>`,
  "compare": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M5 8C5 5.17157 5 3.75736 5.87868 2.87868C6.75736 2 8.17157 2 11 2H13C15.8284 2 17.2426 2 18.1213 2.87868C19 3.75736 19 5.17157 19 8V16C19 18.8284 19 20.2426 18.1213 21.1213C17.2426 22 15.8284 22 13 22H11C8.17157 22 6.75736 22 5.87868 21.1213C5 20.2426 5 18.8284 5 16V8Z"/><path stroke-linecap="round" d="M9 13H15"/><path stroke-linecap="round" d="M9 9H15"/><path stroke-linecap="round" d="M9 17H12"/><path stroke-linecap="round" d="M2 19V5"/><path stroke-linecap="round" d="M22 19V5"/></g></svg>`,
  "compress": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M2 12C2 7.28595 2 4.92893 3.46447 3.46447C4.92893 2 7.28595 2 12 2C16.714 2 19.0711 2 20.5355 3.46447C22 4.92893 22 7.28595 22 12"/><path d="M2 14C2 11.1997 2 9.79961 2.54497 8.73005C3.02433 7.78924 3.78924 7.02433 4.73005 6.54497C5.79961 6 7.19974 6 10 6H14C16.8003 6 18.2004 6 19.27 6.54497C20.2108 7.02433 20.9757 7.78924 21.455 8.73005C22 9.79961 22 11.1997 22 14C22 16.8003 22 18.2004 21.455 19.27C20.9757 20.2108 20.2108 20.9757 19.27 21.455C18.2004 22 16.8003 22 14 22H10C7.19974 22 5.79961 22 4.73005 21.455C3.78924 20.9757 3.02433 20.2108 2.54497 19.27C2 18.2004 2 16.8003 2 14Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M9.5 14.4L10.9286 16L14.5 12"/></g></svg>`,
  "pdf-to-jpg": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M2 12C2 7.28595 2 4.92893 3.46447 3.46447C4.92893 2 7.28595 2 12 2C16.714 2 19.0711 2 20.5355 3.46447C22 4.92893 22 7.28595 22 12C22 16.714 22 19.0711 20.5355 20.5355C19.0711 22 16.714 22 12 22C7.28595 22 4.92893 22 3.46447 20.5355C2 19.0711 2 16.714 2 12Z"/><circle cx="16" cy="8" r="2"/><path stroke-linecap="round" d="M2 12.5001L3.75159 10.9675C4.66286 10.1702 6.03628 10.2159 6.89249 11.0721L11.1822 15.3618C11.8694 16.0491 12.9512 16.1428 13.7464 15.5839L14.0446 15.3744C15.1888 14.5702 16.7369 14.6634 17.7765 15.599L21 18.5001"/></g></svg>`,
  "jpg-to-pdf": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M18.18 8.03933L18.6435 7.57589C19.4113 6.80804 20.6563 6.80804 21.4241 7.57589C22.192 8.34374 22.192 9.58868 21.4241 10.3565L20.9607 10.82M18.18 8.03933C18.18 8.03933 18.238 9.02414 19.1069 9.89309C19.9759 10.762 20.9607 10.82 20.9607 10.82M20.9607 10.82L16.7001 15.0806C16.4115 15.3692 16.2672 15.5135 16.1081 15.6376C15.9204 15.7839 15.7173 15.9094 15.5025 16.0118C15.3203 16.0986 15.1268 16.1632 14.7396 16.2922L13.5 16.7054L13.099 16.8391L12.6979 16.9728C12.5074 17.0363 12.2973 16.9867 12.1553 16.8447C12.0133 16.7027 11.9637 16.4926 12.0272 16.3021L12.1609 15.901L12.2946 15.5L12.7078 14.2604C12.8368 13.8732 12.9014 13.6797 12.9882 13.4975C13.0906 13.2827 13.2161 13.0796 13.3624 12.8919C13.4865 12.7328 13.6308 12.5885 13.9194 12.2999L18.18 8.03933M13.099 16.8391L12.1609 15.901"/><path stroke-linecap="round" d="M8 13H10.5"/><path stroke-linecap="round" d="M8 9H14.5"/><path stroke-linecap="round" d="M8 17H9.5"/><path stroke-linecap="round" d="M19.8284 3.17157C18.6569 2 16.7712 2 13 2H11C7.22876 2 5.34315 2 4.17157 3.17157C3 4.34315 3 6.22876 3 10V14C3 17.7712 3 19.6569 4.17157 20.8284C5.34315 22 7.22876 22 11 22H13C16.7712 22 18.6569 22 19.8284 20.8284C20.7715 19.8853 20.9554 18.4796 20.9913 16"/></g></svg>`,
  "watermark": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M10 17.8332C10 20.1344 8.20914 21.9999 6 21.9999C3.79086 21.9999 2 20.1344 2 17.8332C2 16.3934 3.56593 14.4716 4.73823 13.2347C5.43222 12.5025 6.56778 12.5025 7.26177 13.2347C8.43407 14.4716 10 16.3934 10 17.8332Z"/><path d="M22 17.8332C22 20.1344 20.2091 21.9999 18 21.9999C15.7909 21.9999 14 20.1344 14 17.8332C14 16.3934 15.5659 14.4716 16.7382 13.2347C17.4322 12.5025 18.5678 12.5025 19.2618 13.2347C20.4341 14.4716 22 16.3934 22 17.8332Z"/><path d="M16 7.83319C16 10.1344 14.2091 11.9999 12 11.9999C9.79086 11.9999 8 10.1344 8 7.83319C8 6.39337 9.56593 4.47165 10.7382 3.23473C11.4322 2.50249 12.5678 2.50249 13.2618 3.23473C14.4341 4.47165 16 6.39337 16 7.83319Z"/></g></svg>`,
  "page-numbers": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path d="M10 3L5 21"/><path d="M19 3L14 21"/><path d="M22 9H4"/><path d="M20 16H2"/></g></svg>`,
  "sign": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M16.652 3.45506L17.3009 2.80624C18.3759 1.73125 20.1188 1.73125 21.1938 2.80624C22.2687 3.88124 22.2687 5.62415 21.1938 6.69914L20.5449 7.34795M16.652 3.45506C16.652 3.45506 16.7331 4.83379 17.9497 6.05032C19.1662 7.26685 20.5449 7.34795 20.5449 7.34795M16.652 3.45506L10.6872 9.41993C10.2832 9.82394 10.0812 10.0259 9.90743 10.2487C9.70249 10.5114 9.52679 10.7957 9.38344 11.0965C9.26191 11.3515 9.17157 11.6225 8.99089 12.1646L8.41242 13.9M8.41242 13.9L8.03811 15.0229C7.9492 15.2897 8.01862 15.5837 8.21744 15.7826C8.41626 15.9814 8.71035 16.0508 8.97709 15.9619L10.1 15.5876L11.8354 15.0091C12.3775 14.8284 12.6485 14.7381 12.9035 14.6166C13.2043 14.4732 13.4886 14.2975 13.7513 14.0926C13.9741 13.9188 14.1761 13.7168 14.5801 13.3128L20.5449 7.34795M10.1 15.5876L8.41242 13.9"/><path stroke-linecap="round" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2"/></g></svg>`,
  "redact": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path fill="none" stroke="#e65a2a" stroke-linecap="round" stroke-width="1.5" d="M12 14C5 14 2 7 2 7M22 7C22 7 21.0586 9.19661 19 11.1288C18.0872 11.9856 16.9547 12.7904 15.5872 13.3287C14.5334 13.7435 13.34 14 12 14M12 14V16.5M15.5872 13.3287L17 15.5M19 11.1288L20.5 12.6288M8.41281 13.3287L7 15.5M5 11.1288L3.5 12.6288"/></svg>`,
  "protect": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M2 16C2 13.1716 2 11.7574 2.87868 10.8787C3.75736 10 5.17157 10 8 10H16C18.8284 10 20.2426 10 21.1213 10.8787C22 11.7574 22 13.1716 22 16C22 18.8284 22 20.2426 21.1213 21.1213C20.2426 22 18.8284 22 16 22H8C5.17157 22 3.75736 22 2.87868 21.1213C2 20.2426 2 18.8284 2 16Z"/><path stroke-linecap="round" d="M6 10V8C6 4.68629 8.68629 2 12 2C15.3137 2 18 4.68629 18 8V10"/><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H8.009M11.991 16H12M15.991 16H16"/><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H8.009M11.991 16H12M15.991 16H16"/></g></svg>`,
  "unlock": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M2 16C2 13.1716 2 11.7574 2.87868 10.8787C3.75736 10 5.17157 10 8 10H16C18.8284 10 20.2426 10 21.1213 10.8787C22 11.7574 22 13.1716 22 16C22 18.8284 22 20.2426 21.1213 21.1213C20.2426 22 18.8284 22 16 22H8C5.17157 22 3.75736 22 2.87868 21.1213C2 20.2426 2 18.8284 2 16Z"/><path stroke-linecap="round" d="M6 10V8C6 4.68629 8.68629 2 12 2C14.7958 2 17.1449 3.91216 17.811 6.5"/></g></svg>`,
  "organize-pdf": `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><g fill="none" stroke="#e65a2a" stroke-width="1.5"><path d="M4.97883 9.68508C2.99294 8.89073 2 8.49355 2 8C2 7.50645 2.99294 7.10927 4.97883 6.31492L7.7873 5.19153C9.77318 4.39718 10.7661 4 12 4C13.2339 4 14.2268 4.39718 16.2127 5.19153L19.0212 6.31492C21.0071 7.10927 22 7.50645 22 8C22 8.49355 21.0071 8.89073 19.0212 9.68508L16.2127 10.8085C14.2268 11.6028 13.2339 12 12 12C10.7661 12 9.77318 11.6028 7.7873 10.8085L4.97883 9.68508Z"/><path stroke-linecap="round" d="M22 12C22 12 21.0071 12.8907 19.0212 13.6851L16.2127 14.8085C14.2268 15.6028 13.2339 16 12 16C10.7661 16 9.77318 15.6028 7.7873 14.8085L4.97883 13.6851C2.99294 12.8907 2 12 2 12"/><path stroke-linecap="round" d="M22 16C22 16 21.0071 16.8907 19.0212 17.6851L16.2127 18.8085C14.2268 19.6028 13.2339 20 12 20C10.7661 20 9.77318 19.6028 7.7873 18.8085L4.97883 17.6851C2.99294 16.8907 2 16 2 16"/></g></svg>`,
};

const catColors: Record<string,{bg:string,fg:string}> = {
  organize: { bg: "bg-[#e8f0ff]", fg: "#0a84ff" },
  optimize: { bg: "bg-[#e6f7ed]", fg: "#0ea35a" },
  convert: { bg: "bg-[#f3e8ff]", fg: "#7c3aed" },
  edit: { bg: "bg-[#fef0eb]", fg: "#e65a2a" },
  security: { bg: "bg-[#fee2e2]", fg: "#dc2626" },
  all: { bg: "bg-[#fef0eb]", fg: "#e65a2a" },
};
function Icon({name, cat}:{name:string, cat:string}){ const raw = iconSvgs[name] || ""; const col = catColors[cat]?.fg || "#e65a2a"; const bg = catColors[cat]?.bg || "bg-[#fef0eb]"; const html = raw.replaceAll("#e65a2a", col); return <span className={`flex h-11 w-11 items-center justify-center rounded-xl ${bg} [&_svg]:h-5 [&_svg]:w-5`} style={{color: col}} dangerouslySetInnerHTML={{__html: html}} />; }

const categories: Category[] = [
  { id: "all", label: "Все", title: "Все инструменты", subtitle: "25 инструментов — на вашем VPS" },
  { id: "organize", label: "Организовать PDF", title: "Организовать PDF", subtitle: "Объединяйте, делите, вращайте и упорядочивайте" },
  { id: "optimize", label: "Оптимизация PDF", title: "Оптимизация PDF", subtitle: "Уменьшите размер без потери качества" },
  { id: "convert", label: "Конвертировать PDF", title: "Конвертировать PDF", subtitle: "PDF ↔ JPG и обратно" },
  { id: "edit", label: "Редактировать PDF", title: "Редактировать PDF", subtitle: "Водяной знак, номера, подпись, скрытие" },
  { id: "security", label: "Безопасность PDF", title: "Безопасность PDF", subtitle: "Шифруйте и снимайте пароли" },
];

const tools: Tool[] = [
  { slug: "merge", title: "Объединить PDF", desc: "Объединяйте PDF файлы и упорядочите их легко и быстро в любом порядке, который вам нравится.", meta: "→ 2–10 файлов", span: "sm:col-span-6", cat: "organize", icon: "merge" },
  { slug: "split", title: "Разделить PDF", desc: "Выбирайте диапазон страниц, одну страницу или преобразовывайте каждую страницу документа в независимый PDF-файл.", meta: "→ 1,3-5", span: "sm:col-span-6", cat: "organize", icon: "split" },
  { slug: "delete", title: "Удалить страницы", desc: "Удалите ненужные страницы — оставьте только нужное.", meta: "→ 2, 4", span: "sm:col-span-6", cat: "organize", icon: "delete" },
  { slug: "rotate", title: "Повернуть PDF", desc: "Вращайте несколько PDF одновременно — 90°/180°/270°", meta: "→ multi", span: "sm:col-span-6", cat: "organize", icon: "rotate" },
  { slug: "crop", title: "Обрезка PDF", desc: "Обрезайте поля или область — примените к одной или всем страницам.", meta: "→ mm/pt", span: "sm:col-span-6", cat: "organize", icon: "crop" },
  { slug: "compare", title: "Сравнение PDF", desc: "Сравните два PDF постранично — превью бок о бок с подсветкой.", meta: "→ diff", span: "sm:col-span-6", cat: "organize", icon: "compare" },
  { slug: "organize-pdf", title: "Организовать PDF", desc: "Сортируйте страницы, как вам угодно. Удаляйте или добавляйте страницы по своему усмотрению.", meta: "→ drag & drop", span: "sm:col-span-6", cat: "organize", icon: "organize-pdf" },
  { slug: "compress", title: "Сжать PDF", desc: "Уменьшите размер PDF без потери читаемости — для сканов и экспорта.", meta: "→ low/medium", span: "sm:col-span-12", cat: "optimize", icon: "compress" },
  { slug: "pdf-to-jpg", title: "PDF → JPG", desc: "Рендер каждой страницы в JPG ZIP — 150 dpi.", meta: "→ zip", span: "sm:col-span-6", cat: "convert", icon: "pdf-to-jpg" },
  { slug: "jpg-to-pdf", title: "JPG → PDF", desc: "Картинки → пагинированный PDF.", meta: "→ JPG/PNG", span: "sm:col-span-6", cat: "convert", icon: "jpg-to-pdf" },
  { slug: "watermark", title: "Водяной знак", desc: "Текст или PNG на каждую страницу — позиция и прозрачность.", meta: "→ 0.1-1.0", span: "sm:col-span-6", cat: "edit", icon: "watermark" },
  { slug: "page-numbers", title: "Номера страниц", desc: "1 / N, Page 1 of N — положение и шрифт.", meta: "→ 6–72 pt", span: "sm:col-span-6", cat: "edit", icon: "page-numbers" },
  { slug: "sign", title: "Подписать PDF", desc: "Картинка подписи — позиция и прозрачность.", meta: "→ PNG/JPG", span: "sm:col-span-6", cat: "edit", icon: "sign" },
  { slug: "redact", title: "Скрыть данные", desc: "Безвозвратно закрасьте текст и изображения.", meta: "→ фразы", span: "sm:col-span-6", cat: "edit", icon: "redact" },
  { slug: "protect", title: "Защита PDF", desc: "Пароль 128-bit — печать/копирование.", meta: "→ encrypt", span: "sm:col-span-6", cat: "security", icon: "protect" },
  { slug: "unlock", title: "Открыть PDF", desc: "Снимите пароль если знаете его.", meta: "→ decrypt", span: "sm:col-span-6", cat: "security", icon: "unlock" },
  { slug: "word-to-pdf", title: "Word → PDF", desc: "DOCX/DOC → PDF через LibreOffice, сохраняя форматирование.", meta: "→ docx/doc", span: "sm:col-span-6", cat: "convert", icon: "jpg-to-pdf" },
  { slug: "excel-to-pdf", title: "Excel → PDF", desc: "Таблицы XLSX/XLS → PDF, каждый лист — страница.", meta: "→ xlsx/xls", span: "sm:col-span-6", cat: "convert", icon: "jpg-to-pdf" },
  { slug: "ppt-to-pdf", title: "PowerPoint → PDF", desc: "Презентации PPTX/PPT → PDF.", meta: "→ pptx/ppt", span: "sm:col-span-6", cat: "convert", icon: "jpg-to-pdf" },
  { slug: "pdf-to-word", title: "PDF → Word", desc: "Извлечь текст и картинки в редактируемый DOCX.", meta: "→ docx", span: "sm:col-span-6", cat: "convert", icon: "pdf-to-jpg" },
  { slug: "pdf-to-excel", title: "PDF → Excel", desc: "Текст из PDF в таблицу XLSX.", meta: "→ xlsx", span: "sm:col-span-6", cat: "convert", icon: "pdf-to-jpg" },
  { slug: "pdf-to-ppt", title: "PDF → PowerPoint", desc: "Каждая страница PDF — слайд с картинкой.", meta: "→ pptx", span: "sm:col-span-6", cat: "convert", icon: "pdf-to-jpg" },
  { slug: "ocr-pdf", title: "OCR PDF", desc: "Распознайте текст в скане — сделайте PDF searchable (рус+англ).", meta: "→ searchable", span: "sm:col-span-6", cat: "edit", icon: "redact" },
  { slug: "pdf-to-pdfa", title: "PDF/A", desc: "Конвертируйте в архивный PDF/A для долгого хранения.", meta: "→ PDF/A", span: "sm:col-span-6", cat: "convert", icon: "pdf-to-jpg" },
  { slug: "html-to-pdf", title: "HTML → PDF", desc: "HTML или URL → PDF через WeasyPrint.", meta: "→ url/html", span: "sm:col-span-6", cat: "convert", icon: "jpg-to-pdf" },
  { slug: "repair-pdf", title: "Восстановить PDF", desc: "Починка битых PDF — пересборка xref.", meta: "→ fix", span: "sm:col-span-6", cat: "edit", icon: "compress" },
];

export default function Dashboard() {
  const [active, setActive] = useState("organize");
  const filtered = active === "all" ? tools : tools.filter((t) => t.cat === active);
  return (
    <div className="space-y-8">
      <div className="text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full bg-amber-400 px-3 py-1 text-xs font-bold tracking-[0.08em]">BETA · ТЕСТ С ДРУЗЬЯМИ</div>
        <h1 className="font-[Newsreader] text-[32px] sm:text-[42px] font-[500] tracking-[-0.03em] leading-[0.95] text-[#1b1a17]">PDF Toolkit — 25 инструментов на вашем VPS</h1>
        <p className="mx-auto mt-3 max-w-[760px] text-[14px] leading-6 text-[#6b6a63]">Все файлы остаются на вашем сервере · Автоудаление через 5 мин · BETA</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {categories.map((cat) => (
          <button key={cat.id} onClick={() => setActive(cat.id)} className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${active === cat.id ? "bg-[#1b1a17] text-white shadow" : "bg-white border border-black/10 text-[#1b1a17] hover:bg-white/90"}`}>
            {cat.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-12 gap-4">
        {filtered.map((t) => (
          <Link key={t.slug} href={`/tools/${t.slug}`} className={`group relative flex flex-col rounded-[20px] bg-white p-6 shadow-sm border border-black/[0.06] transition hover:shadow-md hover:border-black/10 ${t.span} col-span-12`}>
            <Icon name={t.icon} cat={t.cat} />
            <h3 className="mt-4 text-[16px] font-semibold tracking-[-0.02em] text-[#1b1a17]">{t.title}</h3>
            <p className="mt-1.5 text-[13px] leading-[1.5] text-[#6b6a63] line-clamp-3">{t.desc}</p>
            <span className="mt-auto pt-4 text-[11px] font-medium tracking-[0.06em] text-[#9a9994]">{t.meta}</span>
          </Link>
        ))}
      </div>
      <div className="rounded-[20px] bg-[#fbfaf8] p-6 text-center text-xs text-[#9a9994]">Local · {tools.length} tools · 50 MB — файлы удаляются через 5 мин</div>
    </div>
  );
}
