# ETF Analytics API

Eine moderne REST-API für strukturierte ETF-Datenanalyse, entwickelt mit FastAPI, PostgreSQL und Vue 3.

## Features

✅ **ETF Master Data Management** - Verwaltung von ETF-Stammdaten (ISIN, Ticker, Provider, etc.)  
✅ **Holdings & Allocations** - Detaillierte Informationen über ETF-Bestände und Allokationen  
✅ **Overlap Analysis** - Vergleich von Holdings zwischen mehreren ETFs  
✅ **Portfolio Exposure** - Aggregierte Sektor-, Länder- und Währungsallokation von Portfolios  
✅ **ETF Similarity Search** - Finde ETFs mit ähnlichen Holdings  
✅ **Web Dashboard** - Interaktive Vue 3 Frontend-Anwendung  
✅ **API Key Authentication** - Sichere API-Authentifizierung mit Rate Limiting  
✅ **Docker & Docker Compose** - Einfaches lokales Setup  

## Architektur

```
┌─────────────────┐
│  Vue 3 Frontend │ (Port 3000)
│  Web Dashboard  │
└────────┬────────┘
         │
         │ HTTP
         ↓
┌─────────────────┐        ┌──────────────────┐
│   FastAPI       │◄──────►│   PostgreSQL     │
│   Backend API   │        │   Database       │
│  (Port 8000)    │        │  (Port 5432)     │
└─────────────────┘        └──────────────────┘
         ▲
         │
         │ DB Access
         ↓
┌─────────────────┐
│  ETL Worker     │
│  (Background)   │
└─────────────────┘
```

## Technologie Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Frontend | Vue 3, Vite, Axios, Chart.js |
| Database | PostgreSQL 15 |
| ETL/Worker | APScheduler, Python |
| Containerization | Docker, Docker Compose |

## Local Setup & Testing

### Voraussetzungen

- Docker & Docker Compose (oder Python 3.11, Node.js 18+ für lokale Installation)
- Git

### Option 1: Docker Compose (Empfohlen für schnelle Einrichtung)

#### 1. Repository klonen

```bash
cd c:\Users\Stefan Heinecke\projects\etfdata
```

#### 2. Docker Compose starten

```bash
docker-compose up --build
```

Dies startet automatisch:
- **PostgreSQL Database** (Port 5432)
- **FastAPI Backend** (Port 8000)
- **Vue Frontend** (Port 3000)
- **ETL Worker** (Hintergrund)

**Wartezeit**: ~2-3 Minuten für Initial Setup, Dependency Installation und Database Initialization

#### 3. Datenbank mit Sample ETFs seeden

Der Worker seedet die Datenbank automatisch beim ersten Start mit 15 Sample-ETFs. Die Logs sollten zeigen:

```
✓ Generated 15 sample ETFs
✓ Generated holdings for 15 ETFs
✓ Generated allocations for 15 ETFs
✓ Generated performance data for 15 ETFs
✓ Database seeded successfully
```

#### 4. Services überprüfen

**Backend Health Check:**
```bash
curl -X GET http://localhost:8000/health
```

Erwartete Antwort:
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2024-05-22T10:30:00"
}
```

**Frontend öffnen:**
- Browser: http://localhost:3000

### Option 2: Lokale Installation (für Entwicklung)

#### Backend Setup

```bash
cd backend

# Python Venv erstellen
python -m venv venv
source venv/bin/activate  # oder `venv\Scripts\activate` auf Windows

# Dependencies installieren
pip install -r requirements.txt

# Database Connection String setzen
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/etfdata
# oder auf Linux: export DATABASE_URL=...

# FastAPI App starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
cd frontend

# Dependencies installieren
npm install

# Development Server starten (Hot Reload)
npm run dev
```

#### Worker Setup (optional)

```bash
cd worker

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/etfdata

python app/main.py
```

## API-Tests

### 1. API Key generieren (erforderlich für alle Requests)

```bash
curl -X POST http://localhost:8000/api/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "test-key"}'
```

Falls kein Endpoint vorhanden ist, nutze den Test-Key: `test-key`

### 2. GET /etfs - Alle ETFs abrufen

```bash
curl -X GET http://localhost:8000/etfs \
  -H "X-API-Key: test-key"
```

**Antwort:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "isin": "IE00B4L5Y983",
    "ticker": "ETF00",
    "name": "Test ETF 1 (Vanguard)",
    "provider": "Vanguard",
    "currency": "EUR",
    "ter": "0.03",
    ...
  }
]
```

### 3. GET /etfs/{id}/holdings - Holdings für ein ETF abrufen

```bash
curl -X GET "http://localhost:8000/etfs/550e8400-e29b-41d4-a716-446655440000/holdings" \
  -H "X-API-Key: test-key"
```

### 4. POST /analytics/overlap - Overlap zwischen ETFs berechnen

```bash
curl -X POST http://localhost:8000/analytics/overlap \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "etf_ids": [
      "550e8400-e29b-41d4-a716-446655440000",
      "550e8400-e29b-41d4-a716-446655440001"
    ]
  }'
```

### 5. POST /analytics/exposure - Portfolio Exposure berechnen

```bash
curl -X POST http://localhost:8000/analytics/exposure \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio": [
      {
        "etf_id": "550e8400-e29b-41d4-a716-446655440000",
        "weight": 60
      },
      {
        "etf_id": "550e8400-e29b-41d4-a716-446655440001",
        "weight": 40
      }
    ]
  }'
```

### 6. GET /analytics/similar/{etf_id} - Ähnliche ETFs finden

```bash
curl -X GET "http://localhost:8000/analytics/similar/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: test-key"
```

## Web Dashboard Testing

1. **Browser öffnen:** http://localhost:3000
2. **ETFs Tab:**
   - Liste aller 15 Sample-ETFs anzeigen
   - Auf "Details" klicken um Holdings und Allocations zu sehen
   - Filter nach Provider verwenden

3. **Analytics Tab:**
   - **Overlap Analysis:** 2+ ETF-IDs eingeben und Overlap berechnen
   - **Portfolio Exposure:** ETFs zum Portfolio hinzufügen, Exposure berechnen
   - **Find Similar:** ETF-ID eingeben und ähnliche ETFs finden

4. **Settings Tab:**
   - API Health Check durchführen
   - API Key konfigurieren

## API Endpoints Übersicht

### Public Endpoints (erfordern API-Key)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root/Status |
| GET | `/health` | Health Check |
| GET | `/etfs` | Liste aller ETFs |
| GET | `/etfs/{id}` | ETF Details |
| GET | `/etfs/{id}/holdings` | Holdings mit optionalem Datum |
| GET | `/etfs/{id}/allocations` | Allocations (Sektor/Land/Währung) |
| GET | `/etfs/{id}/performance` | Performance Data |

### Analytics Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analytics/overlap` | Overlap zwischen mehreren ETFs |
| GET | `/analytics/overlap/{etfA}/{etfB}` | Paarweiser Overlap |
| POST | `/analytics/exposure` | Portfolio Exposure berechnen |
| GET | `/analytics/similar/{etf_id}` | Ähnliche ETFs finden |

## Troubleshooting

### Port bereits in Benutzung

```bash
# Port finden und freigeben
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Mac/Linux

# Oder andere Ports in docker-compose.yml verwenden
```

### Database Connection Error

```
Prüfen Sie:
- Docker Container läuft: docker ps
- Database ist bereit: docker-compose logs db
- DATABASE_URL korrekt gesetzt
```

### Frontend kann API nicht erreichen

```
- CORS ist aktiviert in FastAPI
- Stelle sicher, dass Backend auf Port 8000 läuft
- Prüfe die VITE_API_URL in Frontend-Umgebung
```

### Service will nicht starten

```bash
# Logs prüfen
docker-compose logs backend
docker-compose logs worker
docker-compose logs frontend

# Container neu bauen
docker-compose down -v
docker-compose up --build
```

## Weitere Features (Future)

- [ ] Tracking Difference Analytics
- [ ] Factor Exposure (Risk Model)
- [ ] Backtesting Module
- [ ] Real-time Data Updates
- [ ] Webhooks für Data Changes
- [ ] Authentication (OAuth2)
- [ ] Advanced Charting (Plotly)
- [ ] Export zu CSV/PDF

## Production Deployment

Für Deployment auf **Railway**:

1. **railway.json** erstellen:
```json
{
  "buildCommand": "docker build -t api:latest ./backend",
  "startCommand": "docker run -p 8000:8000 api:latest"
}
```

2. **Environment Variables auf Railway setzen:**
   - `DATABASE_URL` (Railway Postgres URL)
   - `LOG_LEVEL` = INFO

3. **Deploy:**
```bash
railway up
```

## Lizenz & Disclaimer

**Nur öffentliche Daten. Keine Anlageberatung.**

Diese API stellt ausschließlich öffentliche, aggregierte ETF-Daten zur Verfügung. Sie ersetzt nicht die professionelle Finanzberatung.

## Support & Dokumentation

- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Alternative Docs:** http://localhost:8000/redoc (ReDoc)

---

**Happy ETF Analyzing! 📊**
