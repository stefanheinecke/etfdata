# 🚀 Deployment auf Railway

Railway ist ein modernes Platform-as-a-Service für schnelle Deployments.

## Schnellstart Railway Deployment

### 1. Railway CLI installieren

```bash
# Windows (PowerShell)
irm https://install.railway.app | iex

# Mac/Linux
curl -fsSL https://railway.app/install.sh | sh
```

### 2. Mit Railway anmelden

```bash
railway login
```

Öffnet Ihren Browser für GitHub Login.

### 3. Projekt initialisieren

```bash
cd c:\Users\Stefan Heinecke\projects\etfdata
railway init
```

Folgen Sie den Prompts:
- Project Name: `etf-analytics`
- Environment: Wählen Sie `production`

### 4. Services konfigurieren

#### PostgreSQL hinzufügen

```bash
railway add
# Wählen Sie: PostgreSQL
```

#### Environment Variables setzen

```bash
railway variables set DATABASE_URL=$DATABASE_URL
railway variables set LOG_LEVEL=INFO
railway variables set PORT=8000
```

### 5. Deploy

```bash
# Nur Backend (initial)
railway deploy backend/

# Oder Frontend
railway deploy frontend/

# Oder Worker
railway deploy worker/
```

### 6. Status überprüfen

```bash
railway status

# Logs anschauen
railway logs
```

---

## Railway Dashboard Konfiguration

### 1. Backend Service

**Settings:**
- **Builder:** Docker
- **Dockerfile:** `backend/Dockerfile`
- **Start Command:** `./start.sh`
- **Port:** 8000

**Environment Variables:**
```
DATABASE_URL=<auto-from-postgres>
LOG_LEVEL=INFO
PORT=8000
```

### 2. PostgreSQL Database

**Default Railway Postgres:**
- Wird automatisch erstellt
- DATABASE_URL wird als Env Var gesetzt
- Backups aktiviert

### 3. Frontend Service

**Settings:**
- **Builder:** Docker
- **Dockerfile:** `frontend/Dockerfile`
- **Start Command:** `./start.sh`
- **Port:** 3000

**Environment Variables:**
```
VITE_API_URL=<backend-url>
```

### 4. Worker Service

**Settings:**
- **Builder:** Docker
- **Dockerfile:** `worker/Dockerfile`
- **No Port needed** (Background Job)

---

## Manuelle Railway Setup (Alternative)

Falls CLI Probleme hat:

### 1. Öffnen Sie railway.app

https://railway.app/dashboard

### 2. Neues Projekt erstellen

- Click "New Project"
- Wählen Sie "GitHub"
- Authorize Railway mit GitHub

### 3. Repository verbinden

- Wählen Sie etfdata Repository
- Branch: `main`

### 4. Services hinzufügen

**Backend:**
- Wählen Sie Custom Domain
- Dockerfile: `backend/Dockerfile`
- Port: 8000

**Frontend:**
- Wählen Sie Custom Domain
- Dockerfile: `frontend/Dockerfile`
- Port: 3000

**PostgreSQL:**
- Add Service → PostgreSQL
- Standard Konfiguration

### 5. Deploy triggern

- Push zu main Branch triggert automatisch Deploy
- Oder manuell: Railway Dashboard → Deploy

---

## Überprüfung nach Deployment

### Health Check

```bash
curl https://your-app.railway.app/health \
  -H "X-API-Key: <your-api-key>"
```

### Frontend öffnen

```
https://your-frontend.railway.app
```

### Logs anschauen

Railway Dashboard → Service → Logs

---

## Problembehebung

### Problem: Build fehlt

**Lösung:**
- Prüfen Sie Dockerfiles existieren
- `start.sh` Skripte existieren und executable sind
- `requirements.txt` Dateien vollständig

### Problem: Database Connection Error

**Lösung:**
```bash
# Prüfen Sie DATABASE_URL
railway variables list

# Sollte zeigen:
# DATABASE_URL=postgresql://...
```

### Problem: Services nicht erreichbar

**Lösung:**
1. Railway Dashboard öffnen
2. Service wählen
3. Logs anschauen auf Fehler
4. Ports korrekt konfiguriert?

### Problem: Start Script funktioniert nicht

**Lösung:**
```bash
# start.sh muss executable sein
chmod +x backend/start.sh
chmod +x worker/start.sh
chmod +x frontend/start.sh

# Committen und pushen
git add .
git commit -m "Make start scripts executable"
git push
```

---

## Railway URLs

Nach Deployment erhalten Sie:

| Service | URL Format |
|---------|-----------|
| Backend | `https://<backend-name>-prod.railway.app` |
| Frontend | `https://<frontend-name>-prod.railway.app` |
| Postgres | `<auto-managed>` |

---

## Weitere Railway Features

- **Custom Domains:** Domain → Railway Settings
- **SSL Certificates:** Automatisch via Let's Encrypt
- **Auto-scaling:** Railway → Service → Scaling
- **Monitoring:** Logs, Metrics, Alerts
- **Rollback:** Frühere Deployments wiederherstellen

---

## Kostenschätzung

Railway nutzt **Pay as you go** Modell:

- **Compute:** ~$0.50/GB RAM pro Stunde
- **PostgreSQL:** ~$15-30/Monat je nach DB Size
- **Netzwerk:** Included
- **Free Tier:** $5/Monat Kreditstart

---

## Production Best Practices

### Environment Variables

```bash
# Setzen Sie in Railway Dashboard:
DATABASE_URL=<postgres>
LOG_LEVEL=WARN (statt INFO)
API_KEY_SECRET=<strong-secret>
```

### Database Backups

- Railway macht automatische tägliche Backups
- Prüfbar in PostgreSQL Settings

### Monitoring

- Health Checks alle 30s
- Railway notifiziert bei Ausfällen
- Logs bleiben 30 Tage erhalten

### Custom Domain

1. Railway Dashboard → Custom Domain
2. DNS Einträge bei Registrar setzen
3. SSL Certificate aktivieren (automatisch)

---

## Nächste Schritte

1. **Lokal testen:** `docker-compose up`
2. **Deploy zu Railway:** `railway deploy`
3. **Test Production:** `https://your-app.railway.app`
4. **Monitor:** Railway Dashboard

---

Viel Erfolg beim Deployment! 🚀
