# Skolinspektionen DATA - Arkitekturförslag

## Vision
Ett system som gör Skolinspektionens beslut och rapporter tillgängliga som:
1. **Strukturerad JSON-data** (API)
2. **Läsbar Markdown** (fulltext)
3. **MCP-server** (AI-integration)

---

## Datakällor (identifierade)

### Primära källor
| Källa | URL | Data | Format |
|-------|-----|------|--------|
| **Skolinspektionen Publikationer** | skolinspektionen.se/beslut-rapporter/publikationssok/ | ~334 rapporter | HTML→JSON/MD |
| **Skolverket Sökportal** | skolverket.se/.../sok-rapporter-och-beslut-fran-skolinspektionen | Beslut per skola | HTML→JSON |
| **Skolverket API** | api.skolverket.se/skolenhetsregistret/ | Skolenheter + koppling till SI | REST JSON |

### Sekundära källor
| Källa | URL | Data | Format |
|-------|-----|------|--------|
| **jplusplus/skolstatistik** | S3: skolverket-statistik.s3.eu-north-1.amazonaws.com | Skolenkäter | JSON |
| **Diariet** | externsearchport.skolinspektionen.se | Ärenden | HTML |

---

## Arkitekturförslag

### Option A: "g0vse-modellen" (Statisk)
Fördelar: Enkelt, billigt (gratis hosting), beprövat
Nackdelar: Kräver lagring av all data, långsam uppdatering

```
┌─────────────────────────────────────────────────────────────────┐
│  SCRAPER (Python + Camoufox)                                   │
│  Kör nattligen via GitHub Actions                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DATA BRANCH (GitHub)                                          │
│  ├── api/                                                      │
│  │   ├── publications.json                                     │
│  │   ├── decisions.json                                        │
│  │   ├── schools.json                                          │
│  │   └── latest_updated.json                                   │
│  ├── kvalitetsgranskning/                                      │
│  │   └── 2025/rapport-namn.md                                  │
│  └── beslut/                                                   │
│      └── kommun/skola/2025-beslut.md                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  GITHUB PAGES (skolinspektionen-data.github.io)                │
│                                                                 │
│  URL-mönster:                                                  │
│  skolinspektionen.se/beslut-rapporter/publikationer/.../foo/   │
│       ↓                                                        │
│  si-data.se/publikationer/.../foo.md                           │
└─────────────────────────────────────────────────────────────────┘
```

---

### Option B: "Hybrid MCP" (Rekommenderas!)
Fördelar: Real-time data, intelligent sökning, AI-integration
Nackdelar: Kräver server (men kan vara serverless)

```
┌─────────────────────────────────────────────────────────────────┐
│  MCP SERVER (TypeScript/Python)                                │
│  Hostad på: Render/Vercel/Cloudflare Workers                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TOOLS:                                                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ search_decisions                                            ││
│  │   - query: string (fritext)                                 ││
│  │   - kommun?: string                                         ││
│  │   - skolform?: string                                       ││
│  │   - year?: number                                           ││
│  │   - type?: "tillsyn" | "granskning" | "enkat"              ││
│  │   → Returnerar: lista med beslut (titel, datum, url, etc)  ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ get_decision_content                                        ││
│  │   - url: string (skolinspektionen.se URL)                  ││
│  │   → Returnerar: fulltext i Markdown + metadata             ││
│  │   → Hämtar ON-DEMAND (inte förlagrat)                      ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ get_school_info                                             ││
│  │   - school_id: string (från Skolverket API)                ││
│  │   → Returnerar: skolinfo + alla relaterade beslut          ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ list_publications                                           ││
│  │   - type?: "kvalitetsgranskning" | "regeringsrapport" | ...││
│  │   - year?: number                                           ││
│  │   - theme?: string                                          ││
│  │   → Returnerar: lista med publikationer                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  RESOURCES:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ decision://[url-path]                                       ││
│  │   → Returnerar Markdown-version av beslut/rapport          ││
│  │   → Exempel: decision://publikationer/2025/rapport-namn    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Skolinspektionen│ │ Skolverket API  │ │ jplusplus S3    │
│ (webscraping)   │ │ (REST)          │ │ (enkätdata)     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Rekommendation: Hybrid-modellen

### Varför?
1. **On-demand hämtning** - Inget behov av att lagra alla filer
2. **Real-time data** - Alltid aktuell information
3. **Smart caching** - Cacha populära sidor, rensa gamla
4. **AI-native** - MCP gör det enkelt för AI att hitta och visa beslut

### Hur det fungerar för användaren:

```
Användare: "Visa senaste tillsynsbeslut för skolor i Uppsala"

AI (via MCP):
1. Anropar search_decisions(kommun="Uppsala", type="tillsyn")
2. Får lista med beslut
3. Presenterar för användaren
4. Om användaren vill läsa ett → anropar get_decision_content(url)
5. Visar fulltext i Markdown
```

### Teknisk implementation:

```typescript
// MCP Tool: get_decision_content
async function getDecisionContent(url: string): Promise<{
  markdown: string;
  metadata: DecisionMetadata;
}> {
  // 1. Kolla cache först
  const cached = await cache.get(url);
  if (cached) return cached;

  // 2. Hämta sidan on-demand
  const html = await fetch(`https://www.skolinspektionen.se${url}`);

  // 3. Parsa till Markdown
  const { markdown, metadata } = parseToMarkdown(html);

  // 4. Cacha resultatet (t.ex. 24h)
  await cache.set(url, { markdown, metadata }, { ttl: 86400 });

  return { markdown, metadata };
}
```

---

## Index-strategi (för sökning)

### Minimalt index (uppdateras nattligen)
Istället för att lagra alla filer, lagra bara ett **sökindex**:

```json
{
  "publications": [
    {
      "title": "Huvudmannens ansvarstagande...",
      "url": "/beslut-rapporter/publikationer/kvalitetsgranskning/2025/...",
      "published": "2025-11-20",
      "diarienummer": "2024:3781",
      "type": "kvalitetsgranskning",
      "themes": ["vuxenutbildning"],
      "summary": "Kort sammanfattning..."
    }
  ],
  "decisions": [
    {
      "school_id": "12345678",
      "school_name": "Exempelskolan",
      "kommun": "Uppsala",
      "type": "tillsyn",
      "date": "2025-10-15",
      "url": "/path/to/decision"
    }
  ]
}
```

**Storlek:** ~1-5 MB (hanteras enkelt)
**Fulltext:** Hämtas on-demand via `get_decision_content`

---

## Fas-plan

### Fas 1: Index + Basic MCP (2-3 dagar)
- [ ] Bygg index-scraper för publikationer
- [ ] Skapa MCP-server med `list_publications` och `search_decisions`
- [ ] Implementera `get_decision_content` (on-demand)
- [ ] Deploya på Render

### Fas 2: Skolverket-integration (1-2 dagar)
- [ ] Integrera Skolverket API för skolenheter
- [ ] Koppla beslut till skolor
- [ ] Lägg till `get_school_info` tool

### Fas 3: Utökad sökning (2-3 dagar)
- [ ] Scrapa Skolverkets sökportal för fler beslut
- [ ] Integrera jplusplus enkätdata
- [ ] Förbättra söklogik

### Fas 4: Statisk backup (valfritt)
- [ ] Generera Markdown-filer för arkivering
- [ ] GitHub Pages för direkt URL-access
- [ ] g0vse-liknande URL-mönster

---

## URL-mönster (om statisk backup)

```
skolinspektionen.se:
  /beslut-rapporter/publikationer/kvalitetsgranskning/2025/rapport-namn/

si-data.se (vårt):
  /publikationer/kvalitetsgranskning/2025/rapport-namn.md   (Markdown)
  /publikationer/kvalitetsgranskning/2025/rapport-namn.json (Metadata)
  /api/publications.json                                     (Index)
```

---

## Fördelar med Hybrid-modellen

| Aspekt | g0vse-modellen | Hybrid MCP |
|--------|----------------|------------|
| Lagring | Alla filer (~GB) | Bara index (~MB) |
| Aktualitet | Nattlig | Real-time |
| AI-integration | Via API | Native MCP |
| Hosting-kostnad | Gratis (GitHub Pages) | Låg (Render free tier) |
| Komplexitet | Låg | Medium |
| Flexibilitet | Låg | Hög |

---

## Sammanfattning

**Rekommendation:** Bygg en **MCP-server** som:
1. Har ett **minimalt sökindex** (uppdateras nattligen)
2. Hämtar **fulltext on-demand** (ingen förlagring)
3. Returnerar **Markdown** för enkel AI-läsning
4. Integrerar med **Skolverket API** för skoldata

Detta ger det bästa av båda världar: snabb sökning + aktuell data + AI-native!
