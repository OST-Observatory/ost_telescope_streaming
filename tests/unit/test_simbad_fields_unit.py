def test_discover_simbad_dimension_fields_basic():
    from overlay.simbad_fields import discover_simbad_dimension_fields

    class _Simbad:
        @staticmethod
        def list_votable_fields():
            # Fake votable fields where names include common dimension fields
            rows = [
                {"name": "RA"},
                {"name": "DEC"},
                {"name": "dim_majaxis"},
                {"name": "dim_minaxis"},
                {"name": "pa"},
                {"name": "dimensions"},
            ]
            return rows

    maj, min_, ang, dims, pa_supported = discover_simbad_dimension_fields(_Simbad)
    assert maj and min_ and ang and dims
    assert pa_supported is True


def test_discover_simbad_dimension_fields_empty_list():
    from overlay.simbad_fields import discover_simbad_dimension_fields

    class _Simbad:
        @staticmethod
        def list_votable_fields():
            raise RuntimeError("no fields")

    maj, min_, ang, dims, pa_supported = discover_simbad_dimension_fields(_Simbad)
    assert maj is None and min_ is None and (ang is None or isinstance(ang, (str, type(None))))
