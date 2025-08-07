# Ellipse Overlay Guide

## Übersicht

Die Ellipsen-Overlay-Funktion erweitert die Overlay-Generierung um realistische Darstellungen von Deep-Sky-Objekten basierend auf ihren tatsächlichen Dimensionen. Anstatt alle Objekte als einfache Punkte zu markieren, werden Galaxien, Nebel und andere ausgedehnte Objekte als Ellipsen dargestellt, die ihre wahren Größen und Orientierungen widerspiegeln.

## Funktionsweise

### Automatische Objekterkennung

Das System erkennt automatisch, welche Objekte als Ellipsen dargestellt werden sollten:

- **Ellipsen-Objekte**: Galaxien, Nebel, Sternhaufen, etc.
- **Marker-Objekte**: Sterne, Doppelsterne, veränderliche Sterne, etc.

### Datenquellen

Die Ellipsen-Dimensionen werden aus der SIMBAD-Datenbank abgerufen:

- **DIM_MAJ**: Hauptachse in Bogenminuten
- **DIM_MIN**: Nebenachse in Bogenminuten  
- **PA**: Positionswinkel in Grad

### Fallback-Mechanismus

Falls keine Dimensionsdaten verfügbar sind, wird automatisch auf den Standard-Marker zurückgegriffen.

## Unterstützte Objekttypen

### Ellipsen-Objekte

```python
ellipse_types = [
    'G',      # Galaxy
    'GlC',    # Globular Cluster
    'OC',     # Open Cluster
    'Neb',    # Nebula
    'PN',     # Planetary Nebula
    'SNR',    # Supernova Remnant
    'HII',    # HII Region
    'Cl*',    # Cluster
    'Cld',    # Cloud
    'ISM',    # Interstellar Medium
    'MoC',    # Molecular Cloud
    'RNe',    # Reflection Nebula
    'DNe',    # Dark Nebula
    'EmO',    # Emission Object
    'Abs',    # Absorption
    'Rad',    # Radio Source
    'X',      # X-ray Source
    'gLSB',   # Low Surface Brightness Galaxy
    'AGN',    # Active Galactic Nucleus
    'QSO',    # Quasar
    'BLLac',  # BL Lacertae Object
    'Sy1',    # Seyfert 1 Galaxy
    'Sy2',    # Seyfert 2 Galaxy
    'LINER',  # LINER
    'H2G',    # HII Galaxy
    'SBG',    # Starburst Galaxy
    'LSB',    # Low Surface Brightness Galaxy
    'dSph',   # Dwarf Spheroidal Galaxy
    'dE',     # Dwarf Elliptical Galaxy
    'dI',     # Dwarf Irregular Galaxy
    'dS0',    # Dwarf S0 Galaxy
    'dS',     # Dwarf Spiral Galaxy
    'dSB',    # Dwarf Barred Spiral Galaxy
    # ... und weitere
]
```

### Marker-Objekte

Alle anderen Objekttypen werden als Standard-Marker dargestellt:
- Sterne (verschiedene Typen)
- Doppelsterne
- Veränderliche Sterne
- Pulsare
- Gamma-Ray Bursts
- etc.

## Technische Implementierung

### Ellipsen-Zeichnung

Die Ellipsen werden als Polygon-Approximation gezeichnet:

1. **Dimensionen-Parsing**: Auswertung der SIMBAD-Dimensionsdaten
2. **Skalierung**: Umrechnung von Bogenminuten in Pixel
3. **Rotation**: Anwendung des Positionswinkels
4. **Polygon-Generierung**: 32-Punkt-Approximation der Ellipse
5. **Clipping**: Begrenzung auf Bildgrenzen

### Koordinatentransformation

Die Ellipsen berücksichtigen:
- **Bildrotation** (Position Angle)
- **Bildspiegelung** (Flip)
- **Skalierung** (FOV zu Pixel)
- **Positionswinkel** des Objekts

### Fehlerbehandlung

- **Fehlende Daten**: Fallback auf Standard-Marker
- **Ungültige Werte**: Robustes Parsing mit Fehlerbehandlung
- **Zu kleine Ellipsen**: Automatische Konvertierung zu Markern
- **Bildgrenzen**: Clipping und Sichtbarkeitsprüfung

## Beispiele

### M31 - Andromeda-Galaxie

```
Objekttyp: G (Galaxy)
Dimensionen: 178.0 x 63.0 arcmin
Positionswinkel: 35°
Darstellung: Große Ellipse mit 35° Rotation
```

### M42 - Orion-Nebel

```
Objekttyp: Neb (Nebula)
Dimensionen: 85.0 x 60.0 arcmin
Positionswinkel: 0°
Darstellung: Ellipse mit 85' × 60' Dimensionen
```

### M57 - Ring-Nebel

```
Objekttyp: PN (Planetary Nebula)
Dimensionen: 1.4 x 1.0 arcmin
Positionswinkel: 90°
Darstellung: Kleine, hochkant stehende Ellipse
```

## Verwendung

### Automatische Aktivierung

Die Ellipsen-Funktion ist standardmäßig aktiviert und erfordert keine zusätzliche Konfiguration.

### Testen

Verwenden Sie das Test-Skript für verschiedene Objekttypen:

```bash
python test_ellipse_overlay.py
```

### Integration

Die Ellipsen werden automatisch in alle Overlays eingefügt, wenn entsprechende Objekte gefunden werden.

## Vorteile

### Realistische Darstellung

- **Wahre Dimensionen**: Objekte werden in ihrer tatsächlichen Größe dargestellt
- **Korrekte Orientierung**: Positionswinkel wird berücksichtigt
- **Visuelle Hierarchie**: Große Objekte sind prominenter dargestellt

### Verbesserte Planung

- **FOV-Vergleich**: Realistische Einschätzung der Objektgröße
- **Beobachtungsplanung**: Bessere Auswahl von Instrumenten und Vergrößerungen
- **Fotografie-Planung**: Abschätzung der erforderlichen Belichtungszeiten

### Wissenschaftliche Genauigkeit

- **Astronomische Daten**: Basierend auf professionellen Katalogen
- **Konsistente Darstellung**: Einheitliche Skalierung und Orientierung
- **Vollständige Information**: Integration aller verfügbaren Objektdaten

## Performance

### Optimierungen

- **Lazy Loading**: Dimensionsdaten werden nur bei Bedarf abgerufen
- **Caching**: SIMBAD-Abfragen werden zwischengespeichert
- **Effiziente Zeichnung**: Polygon-Approximation statt komplexer Ellipsen-Algorithmen
- **Clipping**: Nur sichtbare Ellipsen werden gezeichnet

### Auswirkungen

- **Minimale Verzögerung**: ~2-5ms zusätzliche Render-Zeit
- **Speicherverbrauch**: Unverändert
- **Netzwerk**: Zusätzliche SIMBAD-Abfragen für Dimensionsdaten

## Troubleshooting

### Ellipsen werden nicht angezeigt

1. **Prüfen Sie die Objekttypen**: Nur bestimmte Objekttypen werden als Ellipsen dargestellt
2. **Dimensionsdaten**: Nicht alle Objekte haben verfügbare Dimensionsdaten
3. **Größe**: Sehr kleine Objekte werden als Marker dargestellt

### Falsche Ellipsen-Größe

1. **FOV-Skalierung**: Stellen Sie sicher, dass das FOV korrekt ist
2. **Einheiten**: Dimensionsdaten sind in Bogenminuten
3. **Bildgröße**: Größere Bilder zeigen detailliertere Ellipsen

### Performance-Probleme

1. **Objektanzahl**: Reduzieren Sie die Magnitude-Grenze
2. **Bildgröße**: Kleinere Bilder sind schneller
3. **FOV**: Kleinere Gesichtsfelder enthalten weniger Objekte

### Fehlende Dimensionsdaten

1. **SIMBAD-Verfügbarkeit**: Nicht alle Objekte haben Dimensionsdaten
2. **Objekttyp**: Nur ausgedehnte Objekte haben Dimensionsdaten
3. **Fallback**: Standard-Marker werden automatisch verwendet

## Erweiterte Funktionen

### Konfigurierbare Schwellenwerte

```python
# Minimale Ellipsen-Größe (in Pixeln)
if major_axis_px < 3 or minor_axis_px < 3:
    return False  # Fallback to marker
```

### Intelligente Objekterkennung

```python
def _should_draw_ellipse(self, object_type: str) -> bool:
    """Determine if an object should be drawn as an ellipse."""
    return object_type in ellipse_types
```

### Robuste Datenverarbeitung

```python
# Parse dimensions string (format: "major_axis x minor_axis")
if 'x' in dimensions_str:
    parts = dimensions_str.split('x')
    dim_maj = float(parts[0].strip())
    dim_min = float(parts[1].strip())
else:
    # Single dimension (circular object)
    dim_maj = float(dimensions_str)
    dim_min = dim_maj
```

## Zukunftige Erweiterungen

### Mögliche Verbesserungen

1. **Mehrere Datenquellen**: Integration von NED, HyperLEDA, etc.
2. **Konfigurierbare Schwellenwerte**: Anpassbare Mindestgrößen
3. **Ellipsen-Styles**: Verschiedene Darstellungsarten
4. **Interaktive Overlays**: Klickbare Ellipsen mit Details
5. **3D-Darstellung**: Berücksichtigung der Entfernung

### Erweiterte Objekttypen

- **Kometen**: Elliptische Koma-Darstellung
- **Asteroiden**: Bewegungsbahnen
- **Satelliten**: Orbit-Darstellung
- **Meteore**: Radiant-Positionen 