from __future__ import annotations

from typing import Dict, Optional, Set, Tuple, List


def discover_simbad_dimension_fields(Simbad) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], bool]:
    """Discover available SIMBAD fields for galaxy dimensions and position angle.

    Returns (picked_maj, picked_min, picked_ang, picked_dims, pa_supported)
    """
    try:
        vot = Simbad.list_votable_fields()
        available: Set[str] = set()
        try:
            for row in vot:
                name = str(row['name']).strip()
                if name:
                    available.add(name.lower())
        except Exception:
            pass
    except Exception:
        available = set()

    maj_candidates: List[str] = ['dim_majaxis', 'majdiam', 'majdiameter', 'galdim_maj_axis', 'galdim_majaxis']
    min_candidates: List[str] = ['dim_minaxis', 'mindiam', 'mindiameter', 'galdim_min_axis', 'galdim_minaxis']
    ang_candidates: List[str] = ['dim_angle', 'pa', 'posang', 'galdim_pa']
    dims_candidates: List[str] = ['dimensions']

    def pick(cands: List[str]) -> Optional[str]:
        for c in cands:
            if c.lower() in available:
                return c
        return None

    picked_maj = pick(maj_candidates)
    picked_min = pick(min_candidates)
    picked_ang = pick(ang_candidates)
    picked_dims = pick(dims_candidates)
    pa_supported = picked_ang is not None and picked_ang.lower() in ['pa', 'dim_angle', 'posang', 'galdim_pa']

    return picked_maj, picked_min, picked_ang, picked_dims, pa_supported


