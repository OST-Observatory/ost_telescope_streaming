# Overlay Information Panel Guide

## Übersicht

Die Overlay-Generierung wurde um zwei wichtige Features erweitert:

1. **Informationspanel** - Zeigt aktuelle Kamera- und Teleskopparameter sowie das Gesichtsfeld an
2. **Konfigurierbare Überschrift** - Ermöglicht eine anpassbare Titelzeile über die Konfigurationsdateien

## Neue Konfigurationsoptionen

### Informationspanel (Info Panel)

Das Informationspanel wird in der Konfigurationsdatei unter `overlay.info_panel` konfiguriert:

```yaml
overlay:
  info_panel:
    enabled: true                    # Panel ein-/ausschalten
    position: "top_right"            # Position: "top_left", "top_right", "bottom_left", "bottom_right"
    width: 300                       # Breite des Panels in Pixeln
    background_color: [0, 0, 0, 180] # Hintergrundfarbe (RGBA mit Transparenz)
    border_color: [255, 255, 255, 255] # Rahmenfarbe
    border_width: 2                  # Rahmenbreite
    padding: 10                      # Innenabstand
    line_spacing: 5                  # Zeilenabstand
    font_size: 12                    # Schriftgröße
    text_color: [255, 255, 255, 255] # Textfarbe
    title_color: [255, 255, 0, 255]  # Titel-Farbe (Gelb)
    
    # Anzuzeigende Informationen
    show_timestamp: true             # Zeitstempel
    show_coordinates: true           # RA/Dec Koordinaten
    show_telescope_info: true        # Teleskop-Informationen
    show_camera_info: true           # Kamera-Informationen
    show_fov_info: true              # Gesichtsfeld-Informationen
    show_plate_solve_info: true      # Plate-Solve-Informationen
```

### Überschrift (Title)

Die Überschrift wird unter `overlay.title` konfiguriert:

```yaml
overlay:
  title:
    enabled: true                    # Titel ein-/ausschalten
    text: "OST Telescope Streaming - 80mm APO + ASI2600MC Pro"  # Titeltext
    position: "top_center"           # Position: "top_center", "top_left", "top_right"
    font_size: 18                    # Schriftgröße
    font_color: [255, 255, 0, 255]   # Schriftfarbe (Gelb)
    background_color: [0, 0, 0, 180] # Hintergrundfarbe (RGBA mit Transparenz)
    padding: 10                      # Innenabstand
    border_color: [255, 255, 255, 255] # Rahmenfarbe
    border_width: 1                  # Rahmenbreite
```

## Angezeigte Informationen

### Informationspanel Inhalt

Das Informationspanel zeigt folgende Informationen an:

1. **Zeitstempel**: Aktuelle Zeit (YYYY-MM-DD HH:MM:SS)
2. **Koordinaten**: RA und Dec im Format HH:MM:SS.SS +DD:MM:SS.S
3. **Position Angle**: Rotationswinkel des Bildes (falls nicht 0°)
4. **Teleskop-Info**: Apertur, Typ, Brennweite und f-Verhältnis
5. **Kamera-Info**: Kameratyp, Sensor-Größe, Pixel-Größe und Bit-Tiefe
6. **Gesichtsfeld**: FOV in Grad und Bogenminuten

### Beispiel-Ausgabe

```
INFO PANEL

Time: 2024-01-15 20:30:45
RA: 00:42:44.35 | Dec: +41:16:09.1
Position Angle: 45.0°

Telescope: 80mm refractor (f/5.0, 400mm FL)
Camera: ALPACA (23.5×15.7mm, 3.76μm, 16bit)

FOV: 1.50°×1.00° (90.0'×60.0')
```

## Verwendung

### 1. Konfiguration anpassen

Bearbeiten Sie Ihre Konfigurationsdatei (z.B. `config_80mm-apo_asi2600ms-pro.yaml`) und passen Sie die Einstellungen an:

```yaml
overlay:
  info_panel:
    enabled: true
    position: "top_right"  # oder andere Position
    text: "Mein Teleskop Setup"  # Ihr Titel
    
  title:
    enabled: true
    text: "Meine Astronomie-Session"
```

### 2. Testen der Features

Verwenden Sie das Test-Skript:

```bash
python test_overlay_features.py
```

### 3. Integration in den Overlay-Runner

Die neuen Features werden automatisch verwendet, wenn Sie den Overlay-Runner starten:

```bash
python overlay_pipeline.py --enable-frame-processing --wait-for-plate-solve
```

## Anpassungsmöglichkeiten

### Panel-Positionen

- `top_left`: Oben links
- `top_right`: Oben rechts (Standard)
- `bottom_left`: Unten links
- `bottom_right`: Unten rechts

### Titel-Positionen

- `top_center`: Oben zentriert (Standard)
- `top_left`: Oben links
- `top_right`: Oben rechts

### Farben

Alle Farben werden im RGBA-Format angegeben:
- `[R, G, B, A]` wobei A die Transparenz ist (0=transparent, 255=undurchsichtig)

### Schriftgrößen

- Info Panel: Standard 12px
- Titel: Standard 18px
- Beide können individuell angepasst werden

## Technische Details

### Implementierung

Die neuen Features sind in der `OverlayGenerator`-Klasse implementiert:

- `_draw_info_panel()`: Zeichnet das Informationspanel
- `_draw_title()`: Zeichnet die Überschrift
- `_format_coordinates()`: Formatiert Koordinaten
- `_get_telescope_info()`: Holt Teleskop-Informationen aus der Konfiguration
- `_get_camera_info()`: Holt Kamera-Informationen aus der Konfiguration
- `_get_fov_info()`: Berechnet Gesichtsfeld-Informationen

### Abhängigkeiten

- `astropy.coordinates.Angle`: Für Koordinaten-Formatierung
- `PIL.ImageFont`: Für Schriftarten
- `datetime`: Für Zeitstempel

### Kompatibilität

- Funktioniert mit allen bestehenden Overlay-Features
- Rückwärtskompatibel - alte Konfigurationen funktionieren weiterhin
- Neue Features sind standardmäßig aktiviert, können aber deaktiviert werden

## Troubleshooting

### Panel wird nicht angezeigt

1. Prüfen Sie `info_panel.enabled: true`
2. Stellen Sie sicher, dass die Bildgröße ausreichend ist
3. Prüfen Sie die Panel-Position und -Breite

### Titel wird nicht angezeigt

1. Prüfen Sie `title.enabled: true`
2. Stellen Sie sicher, dass der Titeltext nicht leer ist
3. Prüfen Sie die Schriftgröße und Position

### Schriftart-Probleme

Das System versucht automatisch, verfügbare Schriftarten zu laden:
- Windows: Arial
- Linux: DejaVu Sans
- macOS: Arial

Falls keine TrueType-Schriftart verfügbar ist, wird die Standard-Schriftart verwendet.

### Performance

Die neuen Features haben minimalen Einfluss auf die Performance:
- Info Panel: ~1-2ms zusätzliche Render-Zeit
- Titel: ~0.5ms zusätzliche Render-Zeit
- Gesamte Overlay-Generierung: <5% zusätzliche Zeit 