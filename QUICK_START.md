# 🚀 QUICK START - ETF Analytics API

Folgen Sie dieser Anleitung für den schnellsten Start!

## ⚡ 5-Minuten Quick Start

### Schritt 1: Docker Compose starten

Öffnen Sie ein Terminal/PowerShell im Projekt-Verzeichnis:

```bash
cd c:\Users\Stefan Heinecke\projects\etfdata
docker-compose up --build
```

**Oder nutzen Sie das Quick-Start Skript:**
- **Windows:** Doppelklick auf `quickstart.bat`
- **Mac/Linux:** `bash quickstart.sh`

### Schritt 2: Warten auf Startup (ca. 30-60 Sekunden)

Sie sollten sehen:
```
✓ Generated 15 sample ETFs
✓ Database seeded successfully
✓ api_1 | Uvicorn running on 0.0.0.0:8000
```

### Schritt 3: Services überprüfen

```bash
# Health Check
curl -H "X-API-Key: test-key" http://localhost:8000/health

# ETFs abrufen
curl -H "X-API-Key: test-key" http://localhost:8000/etfs
```

### Schritt 4: Frontend öffnen

Öffnen Sie im Browser: **http://localhost:3000**

---

## 📍 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend Dashboard** | http://localhost:3000 | Web-Interface für ETF-Verwaltung |
| **API** | http://localhost:8000 | REST API Backend |
| **Swagger Docs** | http://localhost:8000/docs | Interaktive API-Dokumentation |
| **ReDoc** | http://localhost:8000/redoc | Alternative API-Dokumentation |
| **Database** | localhost:5432 | PostgreSQL (postgres/postgres) |

---

## 🧪 Erste Tests

### 1. Health Check durchführen

```bash
curl -X GET http://localhost:8000/health \
  -H "X-API-Key: test-key"
```

**Erwartete Antwort:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2024-05-22T10:30:45.123456"
}
```

### 2. ETFs abrufen

```bash
curl -X GET "http://localhost:8000/etfs?skip=0&limit=10" \
  -H "X-API-Key: test-key"
```

Sollte 15 Sample-ETFs zurückgeben mit Feldern wie `id`, `isin`, `ticker`, `name`, `provider`.

### 3. Holdings eines ETF abrufen

```bash
# 1. ETF-ID aus der Liste kopieren
ETF_ID="<copy-from-previous-response>"

# 2. Holdings abrufen
curl -X GET "http://localhost:8000/etfs/$ETF_ID/holdings" \
  -H "X-API-Key: test-key"
```

### 4. Overlap zwischen zwei ETFs berechnen

```bash
# ETF_ID_1 und ETF_ID_2 aus der ETF-Liste kopieren

curl -X POST http://localhost:8000/analytics/overlap \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "etf_ids": ["ETF_ID_1", "ETF_ID_2"]
  }'
```

### 5. Portfolio Exposure berechnen

```bash
curl -X POST http://localhost:8000/analytics/exposure \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio": [
      {"etf_id": "ETF_ID_1", "weight": 60},
      {"etf_id": "ETF_ID_2", "weight": 40}
    ]
  }'
```

---

## 🌐 Web Dashboard Testing

1. **ETFs Tab:**
   - [ ] Alle ETFs werden angezeigt
   - [ ] Filter nach Provider funktioniert
   - [ ] Klick auf "Details" zeigt Holdings

2. **Analytics Tab:**
   - [ ] Overlap Analysis zwischen 2+ ETFs
   - [ ] Portfolio Exposure mit Sektor-/Länder-Allokation
   - [ ] Find Similar ETFs

3. **Settings Tab:**
   - [ ] Health Check grün
   - [ ] API Key speichern funktioniert

---

## 🛠 Problembehebung

### Services starten nicht

```bash
# Logs prüfen
docker-compose logs backend
docker-compose logs worker
docker-compose logs db

# Alle Services neu bauen
docker-compose down -v
docker-compose up --build
```

### Database Connection Error

```bash
# Prüfen ob Postgres läuft
docker ps | grep etfdata-db

# Manuell verbinden
psql postgresql://postgres:postgres@localhost:5432/etfdata
```

### API antwortet nicht

```bash
# Health Check
curl http://localhost:8000/health

# Container logs
docker logs etfdata-api
```

### Port 8000/3000 bereits in Benutzung

```bash
# Andere Port in docker-compose.yml setzen
# Oder Prozess beenden:
# Windows: taskkill /PID <PID> /F
# Mac/Linux: kill <PID>
```

---

## 📚 Dokumentation

- **Vollständiges README:** `README.md`
- **API Dokumentation:** http://localhost:8000/docs
- **Postman Collection:** `ETF_Analytics_API.postman_collection.json`

---

## 🛑 Services stoppen

```bash
docker-compose down
```

Zu löschen inklusive Datenbank:
```bash
docker-compose down -v
```

---

## 💡 Tipps

1. **API-Key testen:** Benutzen Sie `test-key` für lokale Tests
2. **Sample-Daten:** 15 ETFs werden automatisch mit Provider (Vanguard, iShares, UBS) geseeded
3. **Interaktive API-Docs:** Nutzen Sie http://localhost:8000/docs um Endpoints auszuprobieren
4. **Real-time Logs:** `docker-compose logs -f` für Live-Logs aller Services

---

## ✅ Checklist - Alles funktioniert!

- [ ] Docker-Compose Startup abgeschlossen
- [ ] Health Check zeigt "healthy"
- [ ] Frontend lädt unter http://localhost:3000
- [ ] ETF-Liste zeigt 15 Sample-ETFs
- [ ] Overlap Analysis funktioniert
- [ ] Portfolio Exposure berechenbar
- [ ] Ähnliche ETFs können gesucht werden

**Wenn alle Punkte ✅, dann: Alles fertig! 🎉**

---

Fragen? Siehe `README.md` für ausführliche Dokumentation.
