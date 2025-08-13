# Secondary FOV Overlay Guide

## Übersicht

Die Secondary FOV (Field of View) Overlay-Funktion ermöglicht es, das Gesichtsfeld eines zweiten Teleskops in die Overlays einzuziechnen. Dies ist besonders nützlich für:

- **Vergleich verschiedener Teleskop-Setups**
- **Planung von Beobachtungen mit unterschiedlichen Instrumenten**
- **Visualisierung der FOV-Unterschiede zwischen Kamera und Okular**
- **Koordinierung von Multi-Teleskop-Beobachtungen**

## FOV-Typen

### 1. Kamera-basierte FOV (Rechteck)

Für Teleskope mit Kameras wird ein rechteckiges Gesichtsfeld angezeigt, das der tatsächlichen Sensor-Größe entspricht.

**Benötigte Parameter:**
- Brennweite des zweiten Teleskops
- Sensor-Größe der zweiten Kamera (Breite × Höhe)
- Pixel-Größe der zweiten Kamera (optional, für Berechnungen)

### 2. Okular-basierte FOV (Kreis)

Für Teleskope mit Okularen wird ein kreisförmiges Gesichtsfeld angezeigt, das dem wahren Gesichtsfeld des Okulars entspricht.

**Benötigte Parameter:**
- Brennweite des zweiten Teleskops
- Brennweite des Okulars
- Apparent Field of View (AFOV) des Okulars

## Konfiguration

### Grundkonfiguration

```yaml
overlay:
  secondary_fov:
    enabled: false  # Secondary FOV ein-/ausschalten
    type: "camera"  # "camera" oder "eyepiece"
```

### Teleskop-Parameter

```yaml
secondary_fov:
  telescope:
    focal_length: 2000  # Brennweite in mm
    aperture: 200       # Öffnung in mm
    type: "reflector"   # Teleskop-Typ
```

### Kamera-Parameter (für camera-type)

```yaml
secondary_fov:
  camera:
    sensor_width: 13.2   # Sensor-Breite in mm
    sensor_height: 8.8   # Sensor-Höhe in mm
    pixel_size: 5.4      # Pixel-Größe in Mikrometern
    type: "mono"         # Kamera-Typ (mono/color)
```

### Okular-Parameter (für eyepiece-type)

```yaml
secondary_fov:
  eyepiece:
    focal_length: 25     # Okular-Brennweite in mm
    afov: 68             # Apparent Field of View in Grad
```

### Darstellungsoptionen

```yaml
secondary_fov:
  display:
    color: [0, 255, 255, 255]  # Cyan-Farbe (RGBA)
    line_width: 2              # Linienbreite
    style: "dashed"            # "solid", "dashed", "dotted"
    opacity: 180               # Transparenz (0-255)
    show_label: true           # Beschriftung anzeigen
    label_color: [0, 255, 255, 255]  # Beschriftungsfarbe
    label_font_size: 10        # Schriftgröße
    label_offset: [5, 5]       # Versatz der Beschriftung
```

### Positionsversatz

```yaml
secondary_fov:
  position_offset:
    ra_offset_arcmin: 0.0   # RA-Versatz in Bogenminuten
    dec_offset_arcmin: 0.0  # Dec-Versatz in Bogenminuten
```

## Berechnungsformeln

### Kamera-basierte FOV

```
FOV_breite = (Sensor_Breite / Brennweite) × 57.2958°
FOV_höhe = (Sensor_Höhe / Brennweite) × 57.2958°
```

### Okular-basierte FOV

```
Vergrößerung = Teleskop_Brennweite / Okular_Brennweite
Wahres_Gesichtsfeld = AFOV / Vergrößerung
```

## Beispiele

### Beispiel 1: 8" Newton mit ASI1600MM

```yaml
secondary_fov:
  enabled: true
  type: "camera"
  telescope:
    focal_length: 1000
    aperture: 203
    type: "reflector"
  camera:
    sensor_width: 17.7
    sensor_height: 13.4
    pixel_size: 3.8
    type: "mono"
  display:
    color: [0, 255, 255, 255]  # Cyan
    style: "dashed"
    show_label: true
```

### Beispiel 2: 6" Refraktor mit 25mm Okular

```yaml
secondary_fov:
  enabled: true
  type: "eyepiece"
  telescope:
    focal_length: 1200
    aperture: 150
    type: "refractor"
  eyepiece:
    focal_length: 25
    afov: 68
  display:
    color: [255, 255, 0, 255]  # Gelb
    style: "solid"
    show_label: true
```

### Beispiel 3: Mit Positionsversatz

```yaml
secondary_fov:
  enabled: true
  type: "camera"
  # ... andere Parameter ...
  position_offset:
    ra_offset_arcmin: 30.0   # 30 Bogenminuten nach Osten
    dec_offset_arcmin: 15.0  # 15 Bogenminuten nach Norden
```

## Verwendung

### 1. Konfiguration aktivieren

Bearbeiten Sie Ihre Konfigurationsdatei und setzen Sie:

```yaml
overlay:
  secondary_fov:
    enabled: true
    type: "camera"  # oder "eyepiece"
```

### 2. Parameter anpassen

Passen Sie die Teleskop-, Kamera- oder Okular-Parameter an Ihr Setup an.

### 3. Testen

Verwenden Sie das Test-Skript:

```bash
python test_secondary_fov.py
```

### 4. Integration

Die Secondary FOV wird automatisch in alle Overlays eingefügt, wenn aktiviert.

## Anzeigeoptionen

### Linienstile

- **solid**: Durchgezogene Linie
- **dashed**: Gestrichelte Linie
- **dotted**: Gepunktete Linie

### Farben

Alle Farben im RGBA-Format:
- `[R, G, B, A]` wobei A die Transparenz ist
- Standard: Cyan `[0, 255, 255, 255]`

### Beschriftungen

Die Beschriftung zeigt automatisch:
- **Kamera**: "Secondary: 200mm reflector + 13.2×8.8mm sensor"
- **Okular**: "Secondary: 200mm reflector + 25mm (68° AFOV)"

## Praktische Anwendungen

### 1. FOV-Vergleich

Vergleichen Sie verschiedene Teleskop-Setups:
- Hauptteleskop: 80mm APO + ASI2600MC Pro
- Secondary: 8" Newton + ASI1600MM

### 2. Okular-Planung

Planen Sie Okular-Beobachtungen:
- Hauptteleskop: Kamera für Aufnahmen
- Secondary: Okular für visuelle Beobachtung

### 3. Multi-Teleskop-Koordination

Koordinieren Sie mehrere Teleskope:
- Hauptteleskop: Weitfeld-Aufnahmen
- Secondary: Detail-Aufnahmen

### 4. Finderscope-Simulation

Simulieren Sie Finderscope-Gesichtsfelder:
- Hauptteleskop: Hauptinstrument
- Secondary: Finderscope mit Okular

## Technische Details

### Implementierung

Die Secondary FOV-Funktion ist in der `OverlayGenerator`-Klasse implementiert:

- `_calculate_secondary_fov()`: Berechnet FOV-Dimensionen
- `_get_secondary_fov_label()`: Generiert Beschriftungstext
- `_draw_secondary_fov()`: Zeichnet FOV-Overlay

### Koordinatentransformation

Die Funktion berücksichtigt:
- Bildrotation (Position Angle)
- Bildspiegelung (Flip)
- Positionsversatz
- Skalierung

### Performance

- Minimale Auswirkung auf Overlay-Generierung
- ~1-3ms zusätzliche Render-Zeit
- Automatische Clipping bei Bildgrenzen

## Troubleshooting

### Secondary FOV wird nicht angezeigt

1. Prüfen Sie `secondary_fov.enabled: true`
2. Stellen Sie sicher, dass die Parameter korrekt sind
3. Prüfen Sie, ob das Secondary FOV im Bildbereich liegt

### Falsche FOV-Größe

1. Überprüfen Sie die Brennweite des Teleskops
2. Prüfen Sie die Sensor-Größe (Kamera) oder AFOV (Okular)
3. Verwenden Sie die korrekten Einheiten (mm für Längen, Grad für Winkel)

### Beschriftung wird nicht angezeigt

1. Prüfen Sie `display.show_label: true`
2. Stellen Sie sicher, dass die Beschriftung im Bildbereich liegt
3. Prüfen Sie die Schriftgröße und Position

### Performance-Probleme

1. Reduzieren Sie die Linienbreite
2. Verwenden Sie einfachere Linienstile
3. Deaktivieren Sie die Beschriftung bei Bedarf
