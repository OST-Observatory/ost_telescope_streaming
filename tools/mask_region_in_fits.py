import sys
import os
import numpy as np
from astropy.io import fits

def mask_region_in_fits(fits_file, x_center, y_center, radius):
    # FITS öffnen
    with fits.open(fits_file, mode='readonly') as hdul:
        data = hdul[0].data.copy()
        header = hdul[0].header.copy()

    # Koordinaten vorbereiten
    y, x = np.ogrid[:data.shape[0], :data.shape[1]]
    mask = (x - x_center)**2 + (y - y_center)**2 <= radius**2

    # Werte auf 0 setzen
    data[mask] = 0

    # Header anpassen
    header.add_history(f"Region masked around (x={x_center}, y={y_center}) with radius={radius} pixels.")

    # Neuen Dateinamen erzeugen
    base, ext = os.path.splitext(fits_file)
    new_filename = f"{base}_region_masked.fits"

    # Neues FITS speichern
    hdu = fits.PrimaryHDU(data=data, header=header)
    hdu.writeto(new_filename, overwrite=True)

    print(f"Neue Datei gespeichert: {new_filename}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python mask_fits.py <fits_file> <x_center> <y_center> <radius>")
        sys.exit(1)

    fits_file = sys.argv[1]
    x_center = int(sys.argv[2])
    y_center = int(sys.argv[3])
    radius = int(sys.argv[4])

    mask_region_in_fits(fits_file, x_center, y_center, radius)
