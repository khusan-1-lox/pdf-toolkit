# PDF Toolkit — i18n RU/EN with next-intl — Design Spec

**Date:** 2026-09-01
**Status:** Draft → Approved (user: "делай как нужно" 2026-09-01)
**Goal:** Полная двуязычность RU/EN без смешанного языка, SEO-дружелюбно для GitHub stars. Дефолт `en`.
**Stack:** Next.js 14.2.0 (App Router) + `next-intl@3.26` + `next-intl/plugin`

---

## 1. Context & Scope

Текущее: `pdf-toolkit/frontend` — Next 14 App Router, `app/page.tsx` (Dashboard с категориями/тулами на RU), `app/tools/[slug]/page.tsx` (TOOL_META + friendlyError на RU, часть EN), `components/Header.tsx`, `lib/api.ts`. Нет i18n, `lang="en"` хардкод.

Нужно: RU и EN переключаются везде (Dashboard, Header, tool-страницы, ошибки, валидация), URL с локалью (`/en`, `/ru`), детект браузера, шарингабельные ссылки, отсутствие микса языков.

**In scope:**
- Роутинг `[locale]`, middleware, messages, LocaleSwitcher, миграция `app/` под `[locale]`, коррекция `next.config.mjs`, SEO metadata.
- Перевод всех строк из `page.tsx` и `tools/[slug]/page.tsx` (categories, tools, friendlyError, валидации, тултипы).

**Out of scope:**
- Перевод backend сообщений (backend остается EN, frontend мапит via friendlyError), добавление третьего языка, перевод `docs/`, `promo/`.

Constraints: Next 14.2 → `next-intl@3.26.x` (4.x требует Next 15). Сохранить `rewrites /api -> API_URL`, security headers. Не ломать `app/api/auth`.

---

## 2. Architecture

```
request → middleware (next-intl) → app/[locale]/layout.tsx (NextIntlClientProvider + html lang)
                                  → app/[locale]/page.tsx / app/[locale]/tools/[slug]/page.tsx (useTranslations)
                                  → components/Header + LocaleSwitcher (useLocale, useRouter)
messages/ru.json, messages/en.json ← i18n.ts (getRequestConfig)
routing.ts (defineRouting)
next.config.mjs = withNextIntl(...)
```

**Routing:** `defineRouting({ locales: ['en','ru'], defaultLocale: 'en', localePrefix: 'always' })` — всегда `/en/...` и `/ru/...`. Альтернатива `as-needed` отклонена: теряется каноникал и шаринг.

**Middleware:** `createMiddleware(routing)` на `matcher: ['/', '/(ru|en)/:path*', '/((?!api|_next|_vercel|.*\\..*).*)']` — исключает `api`, статику, `_next`. Редирект `/` → `/{defaultLocale}` via детект `Accept-Language` / `NEXT_LOCALE` cookie.

**Next config:** `const withNextIntl = createNextIntlPlugin('./i18n.ts'); export default withNextIntl(nextConfig);`

**Файловая миграция:**
- `app/layout.tsx` → `app/[locale]/layout.tsx` (принимает `params.locale`, `setRequestLocale`, `getMessages`)
- `app/page.tsx` → `app/[locale]/page.tsx`
- `app/tools/[slug]/page.tsx` → `app/[locale]/tools/[slug]/page.tsx`
- `app/api/**` остается на месте (вне `[locale]`, middleware его не трогает)
- Новые: `i18n.ts`, `routing.ts`, `middleware.ts`, `messages/en.json`, `messages/ru.json`, `components/LocaleSwitcher.tsx`

**Версии:** `next-intl@3.26.5` (последняя 3.x). Установка: `npm i next-intl@3.26.5`.

---

## 3. Components & Data Flow

**messages structure (плоский, type-safe):**
```json
{
  "common": { "beta": "BETA", "dashboard": "Dashboard", "back": "← Back" },
  "header": { "subtitle": "PRIVATE · 25 TOOLS · MCP", "signIn": "Sign In", "signOut": "Sign Out", "localBadge": "Local · no login" },
  "dashboard": {
    "title": "PDF Toolkit — 25 tools on your VPS",
    "subtitle": "Files stay on your server · Auto-delete in 5 min · BETA",
    "categories": { "all": "All", "organize": "Organize PDF", "...": "..." },
    "tools": { "merge": { "title": "Merge PDF", "desc": "...", "meta": "→ 2–10 files" } }
  },
  "tool": { "unknown": "Unknown tool: {slug}", "addMore": "+ Add more files", "dragHint": "Drag pages to reorder" },
  "errors": { "pageOutOfRange": "Page {page} out of range. File has {n} pages — enter 1..{n} (e.g. 1,3-5)", "...": "..." }
}
```
Ключи 1:1 между `ru.json` и `en.json`; скрипт проверки отсутствующих ключей.

**LocaleSwitcher:** `"use client"`; `const locale = useLocale(); const router = useRouter(); const pathname = usePathname();` — рендерит `EN | RU` toggle (active = `bg-[#1b1a17] text-white`). При клике: `router.replace(pathname, {locale: next})` + `document.cookie = NEXT_LOCALE=...`. Сохраняет query/параметры tool-страницы (файлы не сбрасываются — state в памяти, но pathname меняется).

**Header:** добавить `<LocaleSwitcher/>` между Dashboard линком и auth блоком. Линки `href="/"` → `href="/" locale aware` (next-intl `Link` из `navigation.ts` или `next/link` с префиксом).

**i18n.ts:**
```ts
import {getRequestConfig} from 'next-intl/server';
import {routing} from './routing';
export default getRequestConfig(async ({locale}) => ({
  messages: (await import(`./messages/${locale}.json`)).default
}));
```

**routing.ts:**
```ts
import {defineRouting} from 'next-intl/routing';
export const routing = defineRouting({ locales: ['en','ru'], defaultLocale: 'en', localePrefix: 'always' });
```

**Data flow SEO:**
- `app/[locale]/layout.tsx`: `export function generateMetadata({params:{locale}})` → `title/description` из messages, `alternates: { languages: {en:'/en', ru:'/ru', 'x-default':'/en'} }`, `html lang={locale}`.
- Детект: middleware читает `Accept-Language`, если `ru` в приоритете → редирект `/` → `/ru`, иначе `/en`. Пользовательский выбор (cookie) приоритетнее.

---

## 4. Error Handling & Edge Cases

- Отсутствующий ключ: `next-intl` fallback на `en`, в dev `onError` логирует.
- Невалидная локаль (`/fr/...`): middleware редиректит на `/en/...` (или 404 с линком на `/en`).
- `friendlyError` в `tools/[slug]/page.tsx` → все строки через `t('errors.xxx', {page, n})`, бэкенд EN-детали мапятся на RU/EN.
- Валидации `pages` (split/delete/crop) — сообщения через `t('errors.*')`, клиентская проверка до `callTool`.
- Файлы/состояние при смене локали: смена `locale` — это `replace` того же pathname, React state (files, pageItems) не сбрасывается (тот же компонент, другой locale param).
- `app/api/auth/[...nextauth]` — вне `[locale]`, rewrites `/api/:path*` сохранены.

---

## 5. Dependencies & Infra

**Install:** `npm i next-intl@3.26.5` в `pdf-toolkit/frontend`.

**next.config.mjs diff:**
```js
import createNextIntlPlugin from 'next-intl/plugin';
const withNextIntl = createNextIntlPlugin('./i18n.ts');
export default withNextIntl(nextConfig);
```

**middleware.ts** (корень `frontend/`):
```ts
import createMiddleware from 'next-intl/middleware';
import {routing} from './routing';
export default createMiddleware(routing);
export const config = { matcher: ['/', '/(ru|en)/:path*', '/((?!api|_next|_vercel|.*\\..*).*)'] };
```

**Impact:** +~30KB gzip. Build тестирует обе локали. Docker/NGINX без изменений (Next standalone). `docker-compose.yml` не меняется.

---

## 6. Frontend Migration Details

- **app/layout.tsx** → `app/[locale]/layout.tsx`: добавить `import {NextIntlClientProvider} from 'next-intl'; import {getMessages} from 'next-intl/server';` + `setRequestLocale(locale)` + `<html lang={locale}>` + `NextIntlClientProvider`.
- **app/page.tsx** → `app/[locale]/page.tsx`: заменить `categories`, `tools` константы на `useTranslations('dashboard')` / `t('tools.merge.title')`. Удалить хардкод RU.
- **app/tools/[slug]/page.tsx** → `app/[locale]/tools/[slug]/page.tsx`: `TOOL_META` через `t('tools')`, `friendlyError` через `t('errors.*')`, валидации через `t`. Сигнатура: `export default function ToolPage({params:{slug, locale}})`.
- **components/Header.tsx**: импорт `LocaleSwitcher`, замена `Link` на `Link` из `navigation` (или префикс). Сохранить `useSession` логику.
- **navigation.ts** (опц.): `createNavigation(routing)` для типизированных `Link`, `useRouter`, `usePathname`.

---

## 7. Testing

- `npm run build` — должен сгенерить `/en` и `/ru` роуты без ошибок.
- Ручной smoke: `/` → редирект на `/en` (или `/ru` если браузер RU), тоггл RU↔EN на Dashboard и на каждом `tools/[slug]` (merge, split, rotate, watermark), проверить что ошибки (неверные страницы, пустой пароль) показывают переведенный текст.
- Скрипт `scripts/check-i18n.mjs` (опц.): сравнение ключей `ru.json` vs `en.json`, fail если рассинхрон.
- Регресс: существующие `test_frontend.py` / `final_test.py` — обновить URL на `/{locale}/tools/...` если нужно.

---

## 8. Rollout Plan

1. `npm i next-intl@3.26.5`, создать `routing.ts`, `i18n.ts`, `middleware.ts`, `messages/*.json` (вынести все строки из текущих файлов).
2. Обернуть `next.config.mjs`, создать `app/[locale]/` структуру, переместить layout/page/tools, добавить `LocaleSwitcher` в Header.
3. `npm run build` локально, фикс импортов.
4. `npm run dev`, ручной smoke RU↔EN, проверка SEO `lang` и `alternates`.
5. Обновить `README.md` (бейдж EN/RU), деплой, проверка на VPS.

---

## 9. Open Questions (resolved)

- Default locale: `en` (для GitHub stars) — approved.
- localePrefix: `always` — approved.
- next-intl версия: 3.26 для Next 14.2 — approved.

---
**Approval:** User 2026-09-01 "делай как нужно" — переход к writing-plans.
