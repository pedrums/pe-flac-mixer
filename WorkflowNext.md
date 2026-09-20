# Workflow-Plan: HiDrive + GitHub Actions für den `pe-flac-mixer`

Dieser Plan beschreibt, wie der Gitarrist Rohdaten auf HiDrive hochlädt, eine GitHub Action (Pipeline) getriggert wird, deine App (`pe-flac-mixer`) den Mix lokal in der Pipeline durchführt und das Ergebnis wieder auf HiDrive bereitstellt.

---

## 1. Voraussetzungen & Vorbereitung

- **HiDrive-Zugang:** 
  - Ein dedizierter HiDrive-Account oder Unterbenutzer mit Zugriff auf den Probenraum-Ordner.
  - Protokoll: **SFTP** (empfohlen für einfache Dateitransfers per CLI-Tools wie `sftp` oder `rsync`) oder **WebDAV**.
- **GitHub Repository:**
  - Das Repository ist zwischen dir (Drummer) und dem Gitarristen geteilt.
- **GitHub Secrets (Sicherheitskonfiguration):**
  - Unter `Settings -> Secrets and variables -> Actions` werden folgende Secrets hinterlegt:
    - `HIDRIVE_HOST` (z. B. `sftp.hidrive.ionos.com`)
    - `HIDRIVE_USER` (Benutzername)
    - `HIDRIVE_PASSWORD` (Passwort oder SSH-Key)

---

## 2. Struktur der GitHub Action (`.github/workflows/mix.yml`)

Die Pipeline wird manuell über das GitHub-Webinterface getriggert (`workflow_dispatch`), optional mit Eingabe des jeweiligen Proben-Datums bzw. Ordnernamens.

### Ablauf der Pipeline:
1. **Checkout:** Code des Repositories laden (inkl. `pe-flac-mixer`).
2. **Environment Setup:** Python/Node.js (je nachdem, worauf deine App basiert) einrichten und Abhängigkeiten installieren.
3. **Download von HiDrive:** 
   - Verbindung zu HiDrive aufbauen (z. B. via `lftp`, `rsync` oder einem kleinen Python-Skript).
   - Rohe FLAC-Spuren für das angegebene Datum herunterladen.
4. **Mix-Prozess ausführen:**
   - Aufrufen deiner App: `python main.py --input ./raw_tracks --output ./output` (Beispiel).
5. **Upload nach HiDrive:**
   - Die gemischten Ergebnisse (z. B. Stereo-Summe als MP3/FLAC) zurück in den entsprechenden HiDrive-Ordner hochladen.
6. **Cleanup:** Temporäre Dateien in der CI-Umgebung löschen.

---

## 3. Umsetzungsschritte für das Team

1. **Gitarrist** lädt Probenmitschnitte wie gewohnt in den HiDrive-Ordner (z. B. `/Proben/2026-03-25/`).
2. **Gitarrist oder Drummer** geht auf GitHub in den Reiter **Actions**, wählt den Workflow aus und klickt auf **Run workflow** (gibt ggf. das Datum/den Ordnernamen an).
3. **Pipeline** läuft automatisch durch (dauert je nach Dateigröße wenige Minuten).
4. **Band** findet die fertigen Mixe im HiDrive-Ordner (`/Proben/2026-03-25/Mix/`) und kann direkt mit dem Üben beginnen.
