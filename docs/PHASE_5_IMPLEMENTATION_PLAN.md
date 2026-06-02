# Phase 5 Implementation Plan — Next.js Frontend Layer (Vercel)

## Goal

Build a beautiful, premium, and responsive Next.js application in the `/frontend` subfolder. Product Managers will be able to browse the catalog of tracked apps, view daily rating/sentiment trend graphs, and ask natural-language questions in a chat interface with exact clickable review citation details.

---

## Technical Specifications & UI Design System

We will implement best practices in modern web design to make the interface feel premium, responsive, and alive:

### 1. Typography & Colors (Harmonious Dark Theme)
* **Fonts**: Google Fonts `Inter` or `Outfit` for sleek readability.
* **Palette**: Sleek dark theme with rich primary colors:
  * Background: Slate/Neutral Dark (`#0B0F19`, `#111827`)
  * Surface Card: HSL dark glassy panels (`#1F2937` with light opacity and border)
  * Accent Primary: Vibrant violet/indigo (`#6366F1`)
  * Sentiment Green (Positive: `#10B981`), Neutral Grey (`#6B7280`), Negative Red (`#EF4444`)
* **Micro-animations**: Subtle transitions on card hovers, smooth message bubbles sliding in, and custom pulse loaders during sync/chat operations.

### 2. Pages Structure (Next.js App Router)
* **Landing Page (`/`)**:
  * Semantic HTML header with app branding.
  * Catalog grid displaying apps fetched from `/catalog`.
  * Cards rendering: Display Name, Store Icons (Play Store / App Store badges), review count, country flags/code, and last synced timestamp.
* **App Detail Dashboard (`/apps/[id]`)**:
  * **Top Section**: App details summary banner.
  * **Split Layout**:
    * **Left (Trends Panel)**:
      * Statistical cards (Avg Rating, Avg Sentiment, Scraped Count).
      * Recharts line graph showing average rating trends over time.
      * Recharts bar/area graph rendering aggregated sentiment scores chronologically.
    * **Right (Chat Console)**:
      * Interactive chat box sending queries to `POST /apps/{id}/chat`.
      * Message feed with user vs assistant bubbles.
      * Clickable citation cards beneath assistant answers. Clicking a card opens a modal display showing full details of the source review.

### 3. SEO & Standard Compliance
* Title tags and meta descriptions on all routes.
* Unique element test IDs.
* Optimized page weights and instant page loads.

---

## Proposed Changes

### Frontend Codebase

#### `frontend/app/layout.tsx`
Root layout setting up Google Fonts, metadata, and Tailwind directives.

#### `frontend/app/page.tsx`
Home component fetching catalog apps and displaying the main catalog grid.

#### `frontend/app/apps/[id]/page.tsx`
Split dashboard loading aggregated rollups (trends) and hosting the RAG chat application.

#### `frontend/components/`
Reusable UI components:
* `CatalogCard.tsx`: Individual app metadata.
* `TrendCharts.tsx`: Line & Bar charts powered by Recharts.
* `ChatPanel.tsx`: Interactive chat console.
* `CitationCard.tsx`: Clickable review citation card.
* `ReviewModal.tsx`: Popup displaying full review body.

---

## Verification Plan

### Manual Verification
1. Initialize the Next.js app.
2. Run in dev server: `make run-web` (at `http://localhost:3000`).
3. Connect `.env.local` to point to the backend API.
4. Verify catalog loads, trends plot points correctly, and chat responds with cited review cards.
