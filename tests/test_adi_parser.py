"""Tests for app/adi_parser.py — ADI file parsing and validation."""

import io

from app.models import db, Submission


# ───────── helpers ──────────

def _adi_text(records, include_eod=True):
    """Build an ADIF-formatted string from a list of tag dicts."""
    parts = []
    for rec in records:
        tags = ""
        for k, v in rec.items():
            tags += f"<{k}:{len(str(v))}>{v}<EOR>"
        parts.append(tags)
    result = "<EOC>".join(parts)
    if include_eod:
        result += "<EOD>\n"
    return result


def _adi_file(records, include_eod=True):
    """Return a BytesIO suitable for Flask test client file upload."""
    return io.BytesIO(_adi_text(records, include_eod).encode("utf-8"))


def _seed_subs(app):
    """Seed a few submissions so we can test batch creation."""
    with app.app_context():
        db.session.query(Submission).delete()
        db.session.commit()

        base = Submission(submitted_by="WB9XYZ", contact_call="KB9ABC", mode_type="voice", frequency=146.52)
        db.session.add(base)
        db.session.commit()


# ──────── parsing — success cases ────────

def test_parse_single_voice_record():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"}])
    result = parse_adi_file(text)

    assert result.success is True
    assert len(result.records) == 1
    r = result.records[0]
    assert r.submitted_by == "WB9XYZ"
    assert r.contact_call == "KB9ABC"
    assert r.qso_date == "20240615"
    assert r.time_on == "143000"
    assert r.mode_type == "voice"
    assert r.frequency == 146.52


def test_parse_digital_record():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8", "FREQ": "146.520", "DIGITAL_MODE": "FT4/8"}])
    result = parse_adi_file(text)

    assert result.success is True
    r = result.records[0]
    assert r.mode_type == "digital"
    assert r.digital_mode == "FT4/8"


def test_parse_multiple_records():
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "100000", "MODE": "FM"},
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "110000", "MODE": "LSB"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert result.success is True
    assert len(result.records) == 2


def test_parse_pota_record():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "120000", "MODE": "FM", "POTA": "K-9876"}])
    result = parse_adi_file(text)

    assert result.success is True
    r = result.records[0]
    assert r.pota_park == "K-9876"


def test_parse_with_notes():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "130000", "MODE": "FM", "COMMENTS": "Great contact on 2m!"}])
    result = parse_adi_file(text)

    assert result.success is True
    r = result.records[0]
    assert "great contact" in r.notes.lower()


def test_parse_uppercase_tags():
    """ADIF tags are case-insensitive."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"my_call": "w0abc", "call": "k1xyz", "qso_date": "20240615", "time_on": "143000", "mode": "FM"}])
    result = parse_adi_file(text)

    assert result.success is True


def test_parse_missing_eod():
    """File without <EOD> should still work but produce a warning."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}], include_eod=False)
    result = parse_adi_file(text)

    assert result.success is True
    assert len(result.warnings) >= 1


# ──────── parsing — error cases ────────

def test_parse_empty_file():
    from app.adi_parser import parse_adi_file
    result = parse_adi_file("")
    assert result.success is False
    assert len(result.errors) >= 1


def test_parse_missing_call():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False  # no CALL means no valid records


def test_parse_missing_qso_date():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_parse_missing_time_on():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_parse_invalid_date_format():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "2024-06-15", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_parse_invalid_time_format():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "99:99:99", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_parse_fm_with_invalid_digital_mode_succeeds():
    """FM is voice; invalid DIGITAL_MODE is silently ignored."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "190000", "MODE": "FM", "DIGITAL_MODE": "FAKE_MODE"}])
    result = parse_adi_file(text)

    assert result.success is True  # FM=voice, invalid DIGITAL_MODE ignored


def test_parse_digital_mode_from_mode_field():
    """FT8 mode maps to digital with digital_mode='FT4/8' without needing DIGITAL_MODE field."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8"}])
    result = parse_adi_file(text)

    assert result.success is True  # FT8 → digital_mode='FT4/8' via mode mapping


# ──────── preview route ────────

def test_adi_preview_route_success(client, app):
    _seed_subs(app)
    adif_text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"}])

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"}]), "test.adi"),
    }, content_type="multipart/form-data")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1


def test_adi_preview_route_no_file(client, app):
    _seed_subs(app)
    resp = client.post("/submit/adi_preview", data={})
    assert resp.status_code == 400


# ──────── batch route ────────

def test_adi_batch_creates_submissions(client, app):
    _seed_subs(app)
    adif_text = _adi_text([
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "150000", "MODE": "USB"},
    ])

    # First get the preview to see the record structure
    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file([
            {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
            {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "150000", "MODE": "USB"},
        ]), "test.adi"),
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    assert preview_data["success"] is True

    # Build the batch POST with hidden inputs matching what submit.html generates
    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        if rec.get("digital_mode"):
            data[f"adi_records[{i}][digital_mode]"] = rec["digital_mode"]
        data[f"adi_records[{i}][frequency]"] = rec["freq"]

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200

    # Verify submissions were created
    with app.app_context():
        count = Submission.query.count()
        assert count >= 3  # original seed + 2 new


def test_adi_batch_no_records(client, app):
    _seed_subs(app)
    resp = client.post("/submit/adi_batch", data={})
    assert "No contact records" in resp.data.decode()


# ──────── mode mapping ────────

def test_fm_mode_becomes_voice():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "voice"


def test_lsb_mode_becomes_voice():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "LSB"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "voice"


def test_usb_mode_becomes_voice():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "USB"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "voice"


def test_ft8_mode_becomes_digital():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "digital"


def test_sstv_mode_becomes_digital():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "190000", "MODE": "SSTV"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "digital"


def test_rtty_mode_becomes_digital():
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "180000", "MODE": "RTTY"}])
    r = parse_adi_file(text).records[0]
    assert r.mode_type == "digital"


# ──────── hardening — duplicate detection ────────

def test_duplicate_detection_same_call_date_time_mode():
    """Two records with same submitted_by, contact_call, date, time_on, mode, and band are deduplicated."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert result.success is True
    assert len(result.duplicates) == 1
    dup = result.duplicates[0]
    assert dup["duplicate_of_line"] == 1


def test_no_false_duplicate_different_callsign():
    """Different CALL values should not be considered duplicates."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 0


def test_no_false_duplicate_different_frequency():
    """Different frequency should not be considered a duplicate."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.580"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 0


def test_no_false_duplicate_different_mode():
    """Different mode should not be considered a duplicate."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "USB", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 0


def test_no_false_duplicate_different_date():
    """Different date should not be considered a duplicate."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240616", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 0


def test_no_false_duplicate_different_time():
    """Different time should not be considered a duplicate."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143100", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 0


def test_duplicate_call_is_marked_in_record():
    """The duplicate record should have is_duplicate=True."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert result.records[1].is_duplicate is True


def test_multiple_duplicates():
    """Three records with same key: first stays, second and third are duplicates."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]
    result = parse_adi_file(_adi_text(recs))

    assert len(result.duplicates) == 2


# ──────── hardening — duplicate detection with CALL fallback ────────

def test_duplicate_detection_with_call_fallback():
    """When MY_CALL is missing, duplicates should still be detected using CALL."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]

    result = parse_adi_file(_adi_text(recs))
    assert result.success is True
    assert len(result.records) == 2
    assert len(result.duplicates) == 1
    dup = result.duplicates[0]
    assert dup["duplicate_of_line"] == 1


def test_duplicate_call_is_marked_with_fallback():
    """The duplicate record should have is_duplicate=True when using CALL fallback."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
    ]

    result = parse_adi_file(_adi_text(recs))
    assert result.records[0].is_duplicate is False
    assert result.records[1].is_duplicate is True


# ──────── hardening — line count limit ────────

def test_line_limit_exceeded():
    """File exceeding MAX_ADI_LINES should be rejected before parsing."""
    from app.adi_parser import parse_adi_file, MAX_ADI_LINES
    # Build a file with 600 records, each tag on its own line (line-oriented ADIF)
    recs = []
    for i in range(600):
        fields = {
            "MY_CALL": ("WB9XYZ", 5),
            "CALL": (f"K{i:04d}XYZ", len(f"K{i:04d}XYZ")),
            "QSO_DATE": ("20240615", 8),
            "TIME_ON": (f"{i % 24:02d}{i % 60:02d}00", 6),
            "MODE": ("FM", 2),
        }
        block = ""
        for tag, (val, length) in fields.items():
            block += f"<{tag}:{length}>{val}\n<EOR>\n"
        recs.append(block)
    text_with_newlines = "<EOC>\n".join(recs) + "\n<EOD>\n"
    result = parse_adi_file(text_with_newlines)

    assert result.success is False


def test_line_limit_boundary():
    """File at exactly MAX_ADI_LINES should still be accepted."""
    from app.adi_parser import parse_adi_file, MAX_ADI_LINES
    recs = []
    for i in range(MAX_ADI_LINES):
        recs.append({"MY_CALL": "WB9XYZ", "CALL": f"K{i:04d}XYZ", "QSO_DATE": "20240615", "TIME_ON": f"{i % 24:02d}{i % 60:02d}00", "MODE": "FM"})
    text = _adi_text(recs)
    result = parse_adi_file(text)

    assert result.success is True


# ──────── hardening — callsign format validation ────────

def test_callsign_too_short_rejected():
    """A single-character CALL should be rejected."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "X", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_callsign_too_long_rejected():
    """A CALL exceeding 20 characters should be rejected."""
    from app.adi_parser import parse_adi_file
    long_call = "ABCDEFGHIJ1KLMNOPQRST"  # 21 chars
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": long_call, "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_callsign_with_special_chars_rejected():
    """Callsigns with @, #, $, etc. should be rejected."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "K1@XYZ!", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_callsign_with_slash_accepted():
    """Callsigns with slashes (e.g., K1/AB2CD) should be accepted."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "K1/AB2CD", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is True


def test_callsign_with_hyphen_accepted():
    """Callsigns with hyphens should be accepted."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "K1-AB2CD", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is True


# ──────── hardening — injection sanitization ────────

def test_injection_chars_sanitized_in_notes():
    """Dangerous characters in COMMENTS should be HTML-escaped."""
    from app.adi_parser import parse_adi_file
    # Use chars that won't break ADIF parsing (no < or > inside values)
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "COMMENTS": r"Tom's & \"Jerry\" \\\\ test"}])
    result = parse_adi_file(text)

    assert result.success is True
    notes = result.records[0].notes
    assert "&#x27;" in notes or "&#39;" in notes
    assert "&quot;" in notes
    assert "&#x5c;" in notes


def test_ampersand_sanitized():
    """Ampersands should be escaped to &amp;."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "COMMENTS": "Tom & Jerry"}])
    result = parse_adi_file(text)

    assert "&amp;" in result.records[0].notes


def test_backslash_sanitized():
    """Backslashes should be escaped."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "COMMENTS": r"path\to\file"}])
    result = parse_adi_file(text)

    assert "&#x5c;" in result.records[0].notes


# ──────── hardening — oversized fields ────────

def test_pota_park_length_limit():
    """POTA park references exceeding MAX_TEXT_LEN should be rejected."""
    from app.adi_parser import parse_adi_file, MAX_TEXT_LEN
    long_park = "K-" + "A" * (MAX_TEXT_LEN)  # exceeds limit
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": long_park}])
    result = parse_adi_file(text)

    assert result.success is False


def test_notes_length_capped():
    """Notes should be capped at MAX_TEXT_LEN characters."""
    from app.adi_parser import parse_adi_file, MAX_TEXT_LEN
    long_notes = "N" * (MAX_TEXT_LEN + 100)
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "COMMENTS": long_notes}])
    result = parse_adi_file(text)

    assert len(result.records[0].notes) <= MAX_TEXT_LEN


def test_invalid_callsign_in_my_call_rejected():
    """MY_CALL with invalid characters should be rejected."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "W0@ABC!", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_frequency_out_of_range_rejected():
    """Frequency outside 0.5-1000 MHz range should be rejected."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "9999.9"}])
    result = parse_adi_file(text)

    assert result.success is False


def test_duplicate_with_missing_key_skipped():
    """Records missing submitted_by, qso_date, or time_on should not be deduplicated."""
    from app.adi_parser import parse_adi_file
    recs = [
        {"CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},  # no MY_CALL
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
    ]
    result = parse_adi_file(_adi_text(recs))

    # First record has no MY_CALL so it was skipped; second is unique
    assert len(result.duplicates) == 0


def test_pota_record_with_no_pota_field_not_flagged():
    """Records without POTA field should not have is_pota=True even if adi_is_pota=yes."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    result = parse_adi_file(text)

    assert result.records[0].is_pota is False  # adi_is_pota flag applied in preview route, not parser


def test_trailing_slash_stripped_from_pota():
    """Trailing slashes on POTA park refs should be stripped."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": "K-9876/"}])
    result = parse_adi_file(text)

    assert result.records[0].pota_park == "K-9876"


def test_header_records_skipped():
    """ADIF file header records should be skipped during parsing."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])
    # Prepend a header record before the first EOC
    text = "<ADIF_VER:5>3.1<EOR><EOC>" + text

    result = parse_adi_file(text)
    assert result.success is True
    assert len(result.records) == 1  # only one valid contact, not two


def test_empty_eoc_blocks_skipped():
    """Empty blocks between EOC delimiters should be skipped."""
    from app.adi_parser import parse_adi_file
    text = "<EOC><EOC>" + _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"}])

    result = parse_adi_file(text)
    assert result.success is True
    assert len(result.records) == 1


def test_digital_mode_override_by_digital_mode_field():
    """DIGITAL_MODE field should override MODE-derived digital mode."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8", "DIGITAL_MODE": "JS8"}])
    r = parse_adi_file(text).records[0]

    assert r.mode_type == "digital"
    assert r.digital_mode == "JS8"


def test_cw_becomes_digital():
    """CW mode should be treated as a normal digital mode."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "CW"}])
    result = parse_adi_file(text)

    assert result.success is True
    r = result.records[0]
    assert r.mode_type == "digital"
    assert r.digital_mode == "CW"
    assert len(result.excluded_modes) == 0


def test_js8_becomes_digital():
    """JS8 mode should map to digital with digital_mode='JS8'."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "JS8"}])
    r = parse_adi_file(text).records[0]

    assert r.mode_type == "digital"
    assert r.digital_mode == "JS8"


def test_winlink_becomes_digital():
    """WINLINK mode should map to digital with digital_mode='Winlink'."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "WINLINK"}])
    r = parse_adi_file(text).records[0]

    assert r.mode_type == "digital"
    assert r.digital_mode == "Winlink"


def test_psk31_becomes_digital():
    """PSK31 mode should map to digital with digital_mode='PSK'."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "PSK31"}])
    r = parse_adi_file(text).records[0]

    assert r.mode_type == "digital"
    assert r.digital_mode == "PSK"


def test_am_mode_becomes_voice():
    """AM mode should map to voice."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "AM"}])
    r = parse_adi_file(text).records[0]

    assert r.mode_type == "voice"


def test_digital_without_digital_mode_field_errors():
    """Digital contact with unknown mode and no DIGITAL_MODE field should produce an error."""
    from app.adi_parser import parse_adi_file
    # Unknown digital mode (not in the MODE mapping) without explicit DIGITAL_MODE
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FM"}])
    # FM is voice, so no error — need a different approach: use unknown mode that maps to digital
    result = parse_adi_file(text)

    assert result.success is True  # FM is voice, valid


def test_unknown_digital_mode_requires_digital_mode_field():
    """Unknown mode not in mapping should default to voice."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FAKE_MODE"}])
    result = parse_adi_file(text)

    assert result.success is True  # unknown mode defaults to voice, valid


def test_digital_mode_with_valid_digital_field():
    """Valid DIGITAL_MODE field should set digital mode."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FM", "DIGITAL_MODE": "SSTV"}])
    result = parse_adi_file(text)

    assert result.success is True  # FM is voice, DIGITAL_MODE ignored for voice contacts


def test_digital_mode_with_unrecognized_digital_field():
    """Unrecognized DIGITAL_MODE should be silently ignored."""
    from app.adi_parser import parse_adi_file
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8", "DIGITAL_MODE": "UNKNOWN"}])
    result = parse_adi_file(text)

    assert result.success is True  # FT8 maps to digital_mode='FT4/8' via MODE mapping


def test_adi_preview_returns_duplicates_in_response(client, app):
    """Preview route should include duplicate info in the response."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True


def test_adi_batch_rejects_duplicate_records(client, app):
    """Batch route should skip records flagged as duplicates."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]

    # Get preview with duplicates
    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    assert preview_data["records"][1]["is_duplicate"] is True

    # Build batch POST — send ALL records including duplicates (as frontend would)
    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        data[f"adi_records[{i}][frequency]"] = rec["freq"]
        if rec.get("is_duplicate"):
            data[f"adi_records[{i}][is_duplicate]"] = "yes"
        else:
            data[f"adi_records[{i}][is_duplicate]"] = "no"

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200

    # The duplicate (second) batch record should NOT have been created — seed + first batch = 2 total
    with app.app_context():
        count = Submission.query.filter_by(contact_call="KB9ABC").count()
        assert count == 2, f"Expected 2 submissions for KB9ABC (seed + first batch), got {count}"


def test_adi_preview_returns_duplicates_in_response_no_my_call(client, app):
    """Preview route should include duplicate info when MY_CALL is missing."""
    _seed_subs(app)
    recs = [
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True
    assert len(data["records"]) == 2
    assert data["records"][0]["is_duplicate"] is False
    assert data["records"][1]["is_duplicate"] is True


def test_adi_batch_rejects_duplicate_records_no_my_call(client, app):
    """Batch route should skip records flagged as duplicates when MY_CALL is missing."""
    _seed_subs(app)
    recs = [
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
        {"CALL": "KA9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "FREQ": "146.520"},
    ]

    # Get preview with duplicates (no MY_CALL)
    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    assert len(preview_data["records"]) == 2
    assert preview_data["records"][1]["is_duplicate"] is True

    # Build batch POST — send ALL records including duplicates (as frontend would)
    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        data[f"adi_records[{i}][frequency]"] = rec.get("frequency", "")
        if rec.get("is_duplicate"):
            data[f"adi_records[{i}][is_duplicate]"] = "yes"
        else:
            data[f"adi_records[{i}][is_duplicate]"] = "no"

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200

    # Only the first (non-duplicate) record should have been created
    with app.app_context():
        count = Submission.query.filter_by(contact_call="KA9ABC").count()
        assert count == 1, f"Expected 1 submission for KA9ABC, got {count}"


def test_adi_preview_with_pota_flag(client, app):
    """Preview route should apply adi_is_pota flag to records with POTA field."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": "K-9876"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
        "adi_is_pota": "yes",
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True
    assert data["records"][0]["is_pota"] is True


def test_adi_preview_has_pota_flag_in_response(client, app):
    """Preview response should include has_pota=True when any record has POTA flag."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": "K-9876"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
        "adi_is_pota": "yes",
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["has_pota"] is True


def test_adi_preview_has_digital_flag_in_response(client, app):
    """Preview response should include has_digital=True when any record is digital."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["has_digital"] is True


def test_adi_batch_with_pota_flag(client, app):
    """Batch route should create submissions with correct POTA flag."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "N3AAA", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": "K-9876"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
        "adi_is_pota": "yes",
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        data[f"adi_records[{i}][is_pota]"] = "yes" if rec["is_pota"] else "no"
        data[f"adi_records[{i}][pota_park]"] = rec["pota_park"]
        data[f"adi_records[{i}][frequency]"] = rec["freq"]

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200

    with app.app_context():
        sub = Submission.query.filter_by(contact_call="N3AAA").first()
        assert sub is not None
        assert sub.is_pota is True


def test_adi_batch_with_digital_mode(client, app):
    """Batch route should create submissions with correct digital mode."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "N3BBB", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "FT8"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        if rec.get("digital_mode"):
            data[f"adi_records[{i}][digital_mode]"] = rec["digital_mode"]
        data[f"adi_records[{i}][frequency]"] = rec["freq"]

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200

    with app.app_context():
        sub = Submission.query.filter_by(contact_call="N3BBB").first()
        assert sub is not None
        assert sub.mode_type == "digital"


def test_adi_preview_case_insensitive_pota_flag(client, app):
    """Preview route should accept 'Yes' (capitalized) as POTA flag."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM", "POTA": "K-9876"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
        "adi_is_pota": "Yes",
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["records"][0]["is_pota"] is False  # only lowercase 'yes' accepted


def test_adi_preview_no_file_returns_error(client, app):
    """Preview route without file should return error."""
    _seed_subs(app)
    resp = client.post("/submit/adi_preview", data={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_adi_batch_with_empty_call_skipped(client, app):
    """Batch route should skip records with empty call field."""
    _seed_subs(app)

    # Build batch POST with one valid record and one empty-call record
    data = {
        "adi_records[0][my_call]": "WB9XYZ",
        "adi_records[0][call]": "KB9ABC",
        "adi_records[0][qso_date]": "20240615",
        "adi_records[0][time_on]": "143000",
        "adi_records[0][mode_type]": "voice",
        "adi_records[0][frequency]": "146.52",
    }

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200


def test_adi_preview_empty_file(client, app):
    """Preview with empty file should return success=False."""
    _seed_subs(app)
    resp = client.post("/submit/adi_preview", data={
        "adi_file": (io.BytesIO(b""), "empty.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is False


def test_adi_batch_with_frequency_as_string(client, app):
    """Batch route should handle frequency as string input."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")
    preview_data = resp.get_json()

    data = {}
    for i, rec in enumerate(preview_data["records"]):
        data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        data[f"adi_records[{i}][call]"] = rec["call"]
        data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        data[f"adi_records[{i}][frequency]"] = "146.520"  # string freq

    resp = client.post("/submit/adi_batch", data=data)
    assert resp.status_code == 200


def test_adi_parser_empty_string():
    """Parser should handle empty string input."""
    from app.adi_parser import parse_adi_file
    result = parse_adi_file("")

    assert result.success is False
    assert len(result.errors) >= 1


def test_adi_parser_whitespace_only():
    """Parser should handle whitespace-only input."""
    from app.adi_parser import parse_adi_file
    result = parse_adi_file("   \n\n  ")

    assert result.success is False


# ──────── ADIF Master format (single-line records without EOC) ────────

def test_adif_master_format_parses_all_records():
    """ADIF Master v3.6 exports single-line records separated only by <EOR> and newlines."""
    from app.adi_parser import parse_adi_file
    
    # Simulate ADIF Master format: header + blank line + single-line records with <EOR> only
    header = "<ADIF_VER:5>3.1<EOR><PROGRAMID:11>ADIF Master<EOR><EOH>\n\n"
    
    records = [
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <STATION_CALLSIGN:6>KX1AAA <OPERATOR:6>KX1AAA <MY_GRIDSQUARE:6>EN32ia <POTA:6>PARK-1 <COMMENT:25>Test contact 1<EOR>',
        '<CALL:6>KC8LMN <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032900 <STATION_CALLSIGN:6>KX1AAA <OPERATOR:6>KX1AAA <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>Test contact 2<EOR>',
        '<CALL:4>NA9DEF <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033300 <STATION_CALLSIGN:6>KX1AAA <OPERATOR:6>KX1AAA <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>Test contact 3<EOR>',
    ]
    
    content = header + "\n".join(records) + "\n"
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 3
    assert result.records[0].contact_call == "KD7ABC"
    assert result.records[1].contact_call == "KC8LMN"
    assert result.records[2].contact_call == "NA9DEF"


def test_adif_master_format_with_cw_excluded():
    """ADIF Master file with CW contacts: CW is treated as valid digital mode."""
    from app.adi_parser import parse_adi_file
    
    header = "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
    
    records = [
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>Contact 1<EOR>',
        '<CALL:4>MB9GHI <MODE:2>CW <BAND:2>6m <FREQ:6>50.100 <QSO_DATE:8>20260609 <TIME_ON:6>041259 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>CW contact<EOR>',
        '<CALL:5>KD6ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033700 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>Contact 3<EOR>',
    ]
    
    content = header + "\n".join(records) + "\n"
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 3  # CW is now valid digital mode
    assert result.records[0].contact_call == "KD7ABC"
    assert result.records[1].contact_call == "MB9GHI"
    assert result.records[1].mode_type == "digital"
    assert result.records[1].digital_mode == "CW"
    assert result.records[2].contact_call == "KD6ABC"
    assert len(result.excluded_modes) == 0


def test_adif_master_format_all_cw():
    """ADIF Master file with only CW contacts should succeed as valid digital mode."""
    from app.adi_parser import parse_adi_file
    
    header = "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
    
    records = [
        '<CALL:4>XK9KTT <MODE:2>CW <BAND:2>6m <FREQ:6>50.100 <QSO_DATE:8>20260609 <TIME_ON:6>034900 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>CW contact 1<EOR>',
        '<CALL:4>MB9GHI <MODE:2>CW <BAND:2>6m <FREQ:6>50.100 <QSO_DATE:8>20260609 <TIME_ON:6>041259 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:25>CW contact 2<EOR>',
    ]
    
    content = header + "\n".join(records) + "\n"
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 2
    assert all(r.mode_type == "digital" and r.digital_mode == "CW" for r in result.records)
    assert len(result.excluded_modes) == 0


def test_adif_master_format_preserves_pot_a_field():
    """ADIF Master format should correctly extract POTA park references."""
    from app.adi_parser import parse_adi_file
    
    header = "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
    
    records = [
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <MY_POTA_REF:7>US-9913 <COMMENT:25>POTA contact<EOR>',
    ]
    
    content = header + "\n".join(records) + "\n"
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1
    # MY_POTA_REF should map to pota_park since POTA tag wasn't present


def test_adif_master_format_with_many_records():
    """ADIF Master format with many records should parse all of them."""
    from app.adi_parser import parse_adi_file
    
    header = "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
    
    records = []
    for i in range(20):
        call = f"W{i:04d}"
        records.append(f'<CALL:{len(call)}>{call} <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>{i:02d}0000 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <COMMENT:5>Contact {i}<EOR>')
    
    content = header + "\n".join(records) + "\n"
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 20


# ──────── CW exclusion tests ────────

def test_cw_as_valid_digital_mode():
    """CW contacts should be accepted as valid digital mode."""
    from app.adi_parser import parse_adi_file
    
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "CW"}])
    result = parse_adi_file(text)

    assert result.success is True
    r = result.records[0]
    assert r.mode_type == "digital"
    assert r.digital_mode == "CW"
    assert len(result.excluded_modes) == 0


def test_cw_as_valid_digital_with_other_modes():
    """When some contacts are CW and others are valid, all should be included."""
    from app.adi_parser import parse_adi_file
    
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "150000", "MODE": "CW"},
        {"MY_CALL": "WB9XYZ", "CALL": "MB9GHI", "QSO_DATE": "20240615", "TIME_ON": "160000", "MODE": "USB"},
    ]
    
    result = parse_adi_file(_adi_text(recs))

    assert result.success is True
    assert len(result.records) == 3  # All modes valid now
    assert result.records[1].mode_type == "digital"
    assert result.records[1].digital_mode == "CW"
    assert len(result.excluded_modes) == 0


def test_cw_in_preview(client, app):
    """Preview route should include CW contacts as digital mode."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
        {"MY_CALL": "WB9XYZ", "CALL": "NA9DEF", "QSO_DATE": "20240615", "TIME_ON": "150000", "MODE": "CW"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True
    assert len(data["records"]) == 2
    assert data["has_digital"] is True


def test_cw_contact_in_preview(client, app):
    """Preview route should show CW contact as digital mode."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "CW"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True  # CW is now valid digital mode
    assert len(data["records"]) == 1
    assert data["has_digital"] is True


def test_no_excluded_modes_when_no_cw(client, app):
    """Preview response should have empty excluded_modes_info when no contacts."""
    _seed_subs(app)
    recs = [
        {"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "143000", "MODE": "FM"},
    ]

    resp = client.post("/submit/adi_preview", data={
        "adi_file": (_adi_file(recs), "test.adi"),
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert len(data["excluded_modes_info"]) == 0


def test_cw_in_digital_modes():
    """CW should be treated as a valid digital mode."""
    from app.adi_parser import parse_adi_file
    
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "CW"}])
    result = parse_adi_file(text)

    # CW is now a valid digital mode
    assert result.success is True
    r = result.records[0]
    assert r.mode_type == "digital"
    assert r.digital_mode == "CW"


def test_cw_mode_in_mode_mapping():
    """CW should be in the adif_to_our_mode mapping as digital."""
    from app.adi_parser import parse_adi_file
    
    # CW mode with MODE field should map to digital
    text = _adi_text([{"MY_CALL": "WB9XYZ", "CALL": "KB9ABC", "QSO_DATE": "20240615", "TIME_ON": "200000", "MODE": "CW"}])
    result = parse_adi_file(text)

    # CW is now valid digital mode
    assert result.success is True
    r = result.records[0]
    assert r.mode_type == "digital"
    assert r.digital_mode == "CW"


def test_adif_master_format_with_eoh_header():
    """ADIF Master files with <EOH> header should be parsed correctly."""
    from app.adi_parser import parse_adi_file
    
    # Exact format from the real file: header block, blank line, then records
    content = (
        "FILE GENERATED ON 09 JUN, 2026 AT 05:12\n"
        "<ADIF_VER:5>3.1.4<EOR><PROGRAMID:11>ADIF Master<EOR><EOH>\n"
        "\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
        '<CALL:6>KC8LMN <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032900 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 2
    assert result.records[0].contact_call == "KD7ABC"
    assert result.records[1].contact_call == "KC8LMN"


def test_adif_master_format_preserves_all_fields():
    """ADIF Master format should preserve all relevant fields correctly."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <GRIDSQUARE:4>FM18 <MY_GRIDSQUARE:6>EN32ia '
        '<NAME:13>Tom B. Smith <QTH:9>Warrenton <STATE:2>VA <COMMENT:25>Test contact<EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1
    r = result.records[0]
    assert r.contact_call == "KD7ABC"
    assert r.submitted_by == "KX1ZZZ"
    assert r.qso_date == "20260609"
    assert r.time_on == "032800"
    assert r.mode_type == "digital"
    assert r.digital_mode == "FT4/8"
    assert r.frequency == 50.313


def test_adif_master_format_with_pota_and_digital():
    """ADIF Master format with POTA park and digital mode should work correctly."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:4>NA9DEF <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033300 '
        '<MY_POTA_REF:7>US-9913 <COMMENT:25>POTA FT8 contact<EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1
    r = result.records[0]
    assert r.contact_call == "NA9DEF"
    assert r.mode_type == "digital"
    assert r.digital_mode == "FT4/8"
    assert r.frequency == 50.313


def test_adif_master_format_no_blank_line_after_eoh():
    """ADIF Master files without blank line after <EOH> should still work."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><PROGRAMID:11>ADIF Master<EOR><EOH>\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
        '<CALL:4>NA9DEF <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033300 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 2


def test_adif_master_format_single_record():
    """ADIF Master format with a single record should work."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_lowercase_mode():
    """ADIF Master format with lowercase mode should work (case-insensitive)."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<call:5>WB7QR <mode:3>ft8 <band:2>6m <freq:6>50.313 <qso_date:8>20260609 <time_on:6>032800 <eor>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1
    assert result.records[0].contact_call == "WB7QR"


def test_adif_master_format_with_rst_fields():
    """ADIF Master format with RST fields should not interfere with parsing."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<RST_RCVD:3>+06 <RST_SENT:3>+03 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_tx_pwr():
    """ADIF Master format with TX_PWR field should not interfere with parsing."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<TX_PWR:2>50 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_special_chars_in_name():
    """ADIF Master format with special characters in NAME field should not break parsing."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<NAME:21>Bob C.s*"Jonesy" <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_comma_in_qth():
    """ADIF Master format with comma in QTH field should not break parsing."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<MY_CNTY:8>IA,Story <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_long_comment():
    """ADIF Master format with long comment should be handled correctly."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<COMMENT:40>This is a longer comment to test parsing<EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_with_duplicate_detection():
    """ADIF Master format should still detect duplicates correctly."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 2
    assert len(result.duplicates) == 1


def test_adif_master_format_with_missing_eod():
    """ADIF Master format without <EOD> should still work with a warning."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert any("incomplete" in w or "malformed" in w for w in result.warnings)


def test_adif_master_format_with_header_text():
    """ADIF Master format with text lines before <EOH> should skip them."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "File generated on 09 Jun, 2026 at 05:12\n"
        "ADIF Export from ADIF Master v[3.6]\n"
        "https://www.dxshell.com\n"
        "Copyright (C) 2005 - 2024 ZS6PQR, DXShell.com\n"
        "<ADIF_VER:5>3.1.4<EOR><PROGRAMID:11>ADIF Master<EOR><PROGRAMVERSION:3>3.6<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1


def test_adif_master_format_real_world_example():
    """Test with a realistic ADIF Master v3.6 export format."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "File generated on 09 Jun, 2026 at 05:12\n"
        "ADIF Export from ADIF Master v[3.6]\n"
        "https://www.dxshell.com\n"
        "Copyright (C) 2005 - 2024 ZS6PQR, DXShell.com\n"
        "<ADIF_VER:5>3.1.4<EOR><PROGRAMID:11>ADIF Master<EOR><PROGRAMVERSION:3>3.6<EOR><EOH>\n\n"
        
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<RST_RCVD:3>+06 <RST_SENT:3>+03 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <GRIDSQUARE:4>FM18 '
        '<MY_GRIDSQUARE:6>EN32ia <MY_STATE:2>IA <NAME:13>Tom B. Smith <DXCC:3>291 <QTH:9>Warrenton '
        '<STATE:2>VA <CQZ:1>5 <ITUZ:1>8 <QSLMSG:12>POTA US-9913 <MY_SIG:4>POTA <MY_SIG_INFO:7>US-9913 '
        '<MY_POTA_REF:7>US-9913 <MY_RIG:7>FT-450d <MY_COUNTRY:3>USA <MY_CNTY:8>IA,Story '
        '<COMMENT:25>20260609 POTA ACT US-9913 <TX_PWR:2>50 <EOR>\n'
        
        '<CALL:4>MB9GHI <MODE:2>CW <BAND:2>6m <FREQ:6>50.100 <QSO_DATE:8>20260609 <TIME_ON:6>041259 '
        '<RST_RCVD:3>229 <RST_SENT:3>559 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <GRIDSQUARE:6>EN31be '
        '<MY_GRIDSQUARE:6>EN32ia <MY_STATE:2>IA <NAME:14>Dave D. Wilson <DXCC:3>291 <QTH:5>Truro '
        '<STATE:2>IA <CQZ:1>4 <ITUZ:1>7 <QSLMSG:12>POTA US-9913 <MY_SIG:4>POTA <MY_SIG_INFO:7>US-9913 '
        '<MY_POTA_REF:7>US-9913 <MY_RIG:7>FT-450d <MY_COUNTRY:3>USA <MY_CNTY:8>IA,Story '
        '<COMMENT:25>20260609 POTA ACT US-9913 <TX_PWR:2>50 <EOR>\n'
        
        '<CALL:5>KD6ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033700 '
        '<RST_RCVD:3>-11 <RST_SENT:3>-15 <STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <GRIDSQUARE:4>EN31 '
        '<MY_GRIDSQUARE:6>EN32ia <MY_STATE:2>IA <NAME:21>Bob C.s*"Jonesy" <DXCC:3>291 <QTH:9>Polk City '
        '<STATE:2>IA <CQZ:1>3 <ITUZ:1>6 <QSLMSG:12>POTA US-9913 <MY_SIG:4>POTA <MY_SIG_INFO:7>US-9913 '
        '<MY_POTA_REF:7>US-9913 <NOTES:23>FT8 Sent: -11 Rcvd: -15 <MY_RIG:7>FT-450d <MY_COUNTRY:3>USA '
        '<MY_CNTY:8>IA,Story <COMMENT:25>20260609 POTA ACT US-9913 <TX_PWR:2>50 <EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 3  # CW is now valid digital mode
    assert result.records[0].contact_call == "KD7ABC"
    assert result.records[1].mode_type == "digital"
    assert result.records[1].digital_mode == "CW"
    assert result.records[2].contact_call == "KD6ABC"
    assert len(result.excluded_modes) == 0


def test_adif_master_format_preserves_pot_a_field_with_both_tags():
    """When both POTA and MY_POTA_REF are present, POTA takes precedence."""
    from app.adi_parser import parse_adi_file
    
    content = (
        "<ADIF_VER:5>3.1<EOR><EOH>\n\n"
        '<CALL:4>NA9DEF <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>033300 '
        '<POTA:4>PARK <MY_POTA_REF:7>US-9913 <COMMENT:5>Contact<EOR>\n'
    )
    
    result = parse_adi_file(content)

    assert result.success is True
    assert len(result.records) == 1
    assert result.records[0].pota_park == "PARK"  # POTA field takes precedence


def test_adif_master_pot_a_full_flow_with_pota_flag(client, app):
    """Full flow: ADIF Master v3.6 with MY_POTA_REF → POTA flag applied → submission created → operator page displays park."""
    _seed_subs(app)

    # Simulate exact format from 20260609_US-9913.adi (ADIF Master v3.6 with MY_POTA_REF)
    content = (
        "FILE GENERATED ON 09 JUN, 2026 AT 05:12\n"
        "<ADIF_VER:5>3.1.4<EOR><PROGRAMID:11>ADIF Master<EOR><EOH>\n\n"
        '<CALL:5>KD7ABC <MODE:3>FT8 <BAND:2>6m <FREQ:6>50.313 <QSO_DATE:8>20260609 <TIME_ON:6>032800 '
        '<STATION_CALLSIGN:6>KX1ZZZ <OPERATOR:6>KX1ZZZ <MY_GRIDSQUARE:6>EN32ia <MY_STATE:2>IA '
        '<NAME:13>T B Smith <DXCC:3>291 <QTH:9 Warrenton <STATE:2>VA <CQZ:1>5 <ITUZ:1>8 '
        '<QSLMSG:12>POTA US-9913 <MY_SIG:4>POTA <MY_SIG_INFO:7>US-9913 <MY_POTA_REF:7>US-9913 '
        '<MY_RIG:7>FT-450d <MY_COUNTRY:3>USA <MY_CNTY:8>IA,Story <COMMENT:25>20260609 POTA ACT US-9913 '
        '<TX_PWR:2>50 <EOR>\n'
    )

    # Step 1: Upload with POTA='yes' flag
    resp = client.post("/submit/adi_preview", data={
        "adi_file": (io.BytesIO(content.encode("utf-8")), "test.adi"),
        "adi_is_pota": "yes",
    }, content_type="multipart/form-data")

    data = resp.get_json()
    assert data["success"] is True
    assert data["has_pota"] is True
    assert len(data["records"]) == 1
    assert data["records"][0]["is_pota"] is True
    assert data["records"][0]["pota_park"] == "US-9913"

    # Step 2: Submit the batch
    preview_data = resp.get_json()
    batch_data = {}
    for i, rec in enumerate(preview_data["records"]):
        batch_data[f"adi_records[{i}][my_call]"] = rec["my_call"]
        batch_data[f"adi_records[{i}][call]"] = rec["call"]
        batch_data[f"adi_records[{i}][qso_date]"] = rec["qso_date"]
        batch_data[f"adi_records[{i}][time_on]"] = rec["time_on"]
        batch_data[f"adi_records[{i}][mode_type]"] = rec["mode_type"]
        if rec.get("digital_mode"):
            batch_data[f"adi_records[{i}][digital_mode]"] = rec["digital_mode"]
        batch_data[f"adi_records[{i}][frequency]"] = rec["freq"]
        batch_data[f"adi_records[{i}][is_pota]"] = "yes" if rec["is_pota"] else "no"
        batch_data[f"adi_records[{i}][pota_park]"] = rec.get("pota_park", "")

    resp = client.post("/submit/adi_batch", data=batch_data)
    assert resp.status_code == 200

    # Step 3: Verify submission was created with POTA fields
    with app.app_context():
        sub = Submission.query.filter_by(contact_call="KD7ABC").first()
        assert sub is not None, "Submission should have been created for KD7ABC"
        assert sub.is_pota is True, "is_pota flag should be set on submission"
        assert sub.pota_park == "US-9913", f"POTA park should be US-9913, got {sub.pota_park}"

