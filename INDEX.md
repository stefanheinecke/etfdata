# 📑 Projekt Index - ETF Analytics API

## 🚀 Schnelleinstieg

**Wollen Sie sofort starten?** → Siehe [QUICK_START.md](QUICK_START.md)

**Installation mit Docker Compose:**
```bash
docker-compose up --build
```

**Browser öffnen:** http://localhost:3000 (Frontend) oder http://localhost:8000/docs (API)

---

## 📂 Projektstruktur

### Root Directory
| Datei | Zweck |
|-------|-------|
| `README.md` | 📖 Vollständige Dokumentation |
| `QUICK_START.md` | ⚡ 5-Minuten Quick Start |
| `IMPLEMENTATION_SUMMARY.md` | ✅ Was wurde implementiert |
| `docker-compose.yml` | 🐳 Docker Setup |
| `.env.example` | ⚙️ Umgebungsvariablen Template |

### Quick Start Scripts
| Datei | Zweck |
|-------|-------|
| `quickstart.sh` | 🚀 Automatischer Start (Mac/Linux) |
| `quickstart.bat` | 🚀 Automatischer Start (Windows) |
| `verify-setup.sh` | ✔️ Verifikation der Installation |
| `verify-setup.bat` | ✔️ Verifikation (Windows) |
| `test-api.sh` | 🧪 API Tests (Mac/Linux) |
| `test-api.bat` | 🧪 API Tests (Windows) |

### Backend (`./backend`)
| Datei | Beschreibung |
|-------|-------------|
| `app/main.py` | FastAPI Hauptprogramm |
| `app/schemas.py` | SQLAlchemy ORM Models |
| `app/models.py` | Pydantic Request/Response Models |
| `app/core/auth.py` | API-Key Authentication |
| `app/services/analytics_service.py` | Overlap/Exposure/Similarity Logic |
| `app/api/routes/etfs.py` | ETF Endpoints |
| `app/api/routes/analytics.py` | Analytics Endpoints |
| `app/db/database.py` | Database Connection |
| `Dockerfile` | Container Image |
| `requirements.txt` | Python Dependencies |

### Worker (`./worker`)
| Datei | Beschreibung |
|-------|-------------|
| `app/main.py` | Scheduler für ETL Jobs |
| `app/tasks/etl_pipeline.py` | ETL Pipeline Framework |
| `app/tasks/data_generator.py` | Sample Data Generator |
| `app/db/database.py` | Database Connection |
| `Dockerfile` | Container Image |
| `requirements.txt` | Python Dependencies |

### Frontend (`./frontend`)
| Datei | Beschreibung |
|-------|-------------|
| `src/App.vue` | Main Vue Component |
| `src/pages/ETFList.vue` | ETF-Übersicht Page |
| `src/pages/Analytics.vue` | Analytics Tools Page |
| `src/pages/Settings.vue` | Settings & Config Page |
| `src/services/api.js` | API Service (Axios) |
| `src/main.js` | Vue App Entry Point |
| `index.html` | HTML Template |
| `vite.config.js` | Vite Build Configuration |
| `package.json` | Node.js Dependencies |
| `Dockerfile` | Container Image |

### Database (`./db`)
| Datei | Beschreibung |
|-------|-------------|
| `migrations/001_initial_schema.sql` | Database Schema & Tables |

---

## 🎯 Use Cases & Zugehörige Endpoints

### Use Case 1: ETF Stammdaten abrufen
```bash
GET /etfs              # Alle ETFs
GET /etfs/{id}         # Einzelnes ETF
GET /etfs/{id}/holdings # Holdings eines ETF
```
**Frontend:** ETFList.vue → Holdings-Übersicht

---

### Use Case 2: Zwei ETFs vergleichen (Overlap)
```bash
POST /analytics/overlap
  Input: 2+ ETF IDs
  Output: Gemeinsame Holdings, Overlap Score
```
**Frontend:** Analytics.vue → Overlap Analysis Tab

---

### Use Case 3: Portfolio Exposure berechnen
```bash
POST /analytics/exposure
  Input: Portfolio mit Gewichtungen
  Output: Aggregierte Sektor-/Länder-/Währungs-Allokation
```
**Frontend:** Analytics.vue → Portfolio Exposure Tab

---

### Use Case 4: Ähnliche ETFs finden
```bash
GET /analytics/similar/{etf_id}
  Output: Top N ähnliche ETFs mit Similarity Score
```
**Frontend:** Analytics.vue → Find Similar Tab

---

## 🔄 Komponenten-Zusammenhang

```
Browser (http://localhost:3000)
    ↓
Vue 3 Frontend (port 3000)
    │
    ├─→ ETFList.vue (Daten abrufen)
    ├─→ Analytics.vue (Analysen)
    └─→ Settings.vue (Config)
        ↓
    API Service (axios)
        ↓
FastAPI Backend (http://localhost:8000)
    ├─→ /etfs Endpoints
    ├─→ /analytics Endpoints
    └─→ Authentication (X-API-Key)
        ↓
PostgreSQL Database
    ├─→ Tabelle: etfs
    ├─→ Tabelle: holdings
    ├─→ Tabelle: allocations
    └─→ Tabelle: performance
```

---

## 📊 Datenmodell

### ETF Tabelle
```
id, isin, ticker, name, provider, domicile, ter, fund_size, currency, ...
```

### Holdings Tabelle
```
id, etf_id, date, instrument_isin, instrument_name, weight, country, sector
```

### Allocations Tabelle
```
id, etf_id, date, type (sector|country|currency), bucket, weight
```

---

## 🔐 Authentication

**Header erforderlich für alle Requests:**
```
X-API-Key: test-key
```

**Beispiel:**
```bash
curl -H "X-API-Key: test-key" http://localhost:8000/etfs
```

---

## 📖 Dokumentation Übersicht

| Dokument | Zweck | Zielgruppe |
|----------|-------|-----------|
| `README.md` | Umfassende technische Doku | Entwickler |
| `QUICK_START.md` | Schnelleinstieg | Alle |
| `IMPLEMENTATION_SUMMARY.md` | Was wurde implementiert | Stakeholder |
| `http://localhost:8000/docs` | Interaktive API Doku (Swagger) | API Users |
| `http://localhost:8000/redoc` | Alternative API Doku | API Users |

---

## 🛠️ Troubleshooting

### Problem: Services starten nicht
**Lösung:** Siehe `README.md` → Troubleshooting Sektion

### Problem: Frontend kann API nicht erreichen
**Lösung:** 
1. Prüfen: `http://localhost:8000/health`
2. Docker logs: `docker-compose logs backend`

### Problem: Database Connection Error
**Lösung:**
1. `docker ps` - Prüfen ob etfdata-db läuft
2. `docker-compose down -v && docker-compose up --build`

---

## 🚀 Deployment

### Lokal (Entwicklung)
```bash
docker-compose up --build
```

### Production (Railway/Heroku)
1. DATABASE_URL Environment Variable setzen
2. Services deployen
3. Siehe Railway/Heroku Dokumentation

---

## 📝 Nützliche Commands

```bash
# Services starten
docker-compose up --build

# Services stoppen
docker-compose down

# Logs anschauen
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f db

# Database zu neu
docker-compose down -v
docker-compose up --build

# API testen
curl -H "X-API-Key: test-key" http://localhost:8000/health

# Frontend öffnen
open http://localhost:3000

# API Dokumentation
open http://localhost:8000/docs
```

---

## 📚 Weitere Ressourcen

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Vue 3 Docs:** https://vuejs.org/
- **SQLAlchemy:** https://www.sqlalchemy.org/
- **PostgreSQL:** https://www.postgresql.org/

---

## ✅ Checkliste für lokale Tests

- [ ] Docker Compose läuft: `docker ps | grep etfdata`
- [ ] Backend antwortet: `curl http://localhost:8000/health`
- [ ] Frontend lädt: http://localhost:3000
- [ ] ETFs sind geseeded: `curl http://localhost:8000/etfs`
- [ ] Overlap funktioniert: POST /analytics/overlap
- [ ] Exposure funktioniert: POST /analytics/exposure

---

## 🎯 Next Steps

1. **Jetzt:** Starten Sie Docker Compose mit `quickstart.bat` / `quickstart.sh`
2. **Dann:** Öffnen Sie http://localhost:3000 im Browser
3. **Danach:** Testen Sie die verschiedenen Analytics Tools
4. **Schließlich:** Nutzen Sie http://localhost:8000/docs für detaillierte API-Doku

---

**Viel Erfolg! 🚀**

Falls Fragen: Siehe `README.md` oder `QUICK_START.md`
