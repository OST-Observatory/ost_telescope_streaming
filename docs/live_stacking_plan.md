## Live-Stacking: Architektur- und Implementierungsplan

Ziele:
- Aufnahme (Producer) von Solve/Overlay (Consumer) entkoppeln
- Live-Stacking als separaten Dienst mit Median/Mean und optionalem Sigma-Clipping
- Solve/Overlay auf Stack-Basis nur für Deep-Sky; bei SS-Objekten Einzel-Frame nutzen
- Stack-Rollover bei signifikanter Bewegung, umbenannt mit Zeit/Koordinaten
- Ausgabe sowohl als PNG (8-bit) als auch FITS (16-bit)

Konfiguration (`processing.stacking`):
- `enabled: bool` – aktiviert Stacking
- `method: "median"|"mean"` – Standard: "median"
- `sigma_clip:
    enabled: bool
    sigma: float` – Standard: enabled true, sigma 3.0
- `max_frames: int` – 0 = unendlich; Default: 100
- `max_integration_s: int` – optional zeitbasiert (0 = ignorieren)
- `align: "astroalign"|"none"` – Default: "astroalign"
- `movement_reset_arcmin: float` – Default: 10.0
- `write_interval_s: int` – z.B. 10
- `min_frames_for_stack_solve: int` – z.B. 3
- `output_format: ["png", "fits"]` – beide aktiv standardmäßig

Komponenten:
- FrameStacker (neue Klasse):
  - Puffert Einzelframes und Metadaten
  - Alignment via `astroalign` (Rotation/Skalierung robust); Fallback none
  - Accumulator:
    - Mean: Float32 Sum + Count
    - Median: Rolling-Puffer (begrenzte Größe)
    - Sigma-Clipping: optional (auf aligned Stack oder pro-Frame residual)
  - Snapshot schreibt: `stacks/stack_YYYYmmdd_HHMMSS_RAxxxx_DECyyyy_nN.(png|fits)`
  - Thread-sicher; atomare Snapshot-Schreibvorgänge

- VideoProcessor:
  - Capture-Thread produziert Einzelframes kontinuierlich
  - Stacker-Service empfängt Frames
  - Solver/Overlay wählen Quelle:
    - SS-Objekt im FOV? → letzter Einzel-Frame
    - sonst → aktueller Stack-Snapshot (wenn `min_frames_for_stack_solve` erfüllt)
  - Bewegungserkennung → Stack finalize+rollover

SS-Objekterkennung:
- Nutzung Astropy (bereits eingeführt): erkennt Moon/Planeten im FOV
- Nur bei Deep-Sky wird Stack verwendet

Bewegungserkennung/Reset:
- Trigger: Slew-Flag oder Δ_sep ≥ `movement_reset_arcmin`
- Rollover: finalisiert aktuellen Stack, benennt nach Schema um, und startet neu

Tests:
- Unit: Accumulator, Median, Sigma-Clipping, Alignment (mit kontrollierten Shifts/Rotationen), Auswahl-Logik, Reset
- Integration: simulierte Frames, Rollover, Mehrformat-Output

Schritte v1 (Status):
1) Config-Sektion + Abhängigkeit `astroalign` (fertig)
2) Klasse `FrameStacker` mit Median/Mean, Sigma-Clipping, Alignment, Persistenz (fertig)
3) Producer/Consumer-Trennung im `VideoProcessor` inkl. Stacking (fertig)
4) Auswahl-Logik (SS-Objekt) + Rollover bei Bewegung (fertig)
5) Overlay-Komposition in `OverlayRunner` Hauptschleife (fertig)
6) Tests (Unit + Integration) und Doku (dieses Dokument) (in Arbeit)
