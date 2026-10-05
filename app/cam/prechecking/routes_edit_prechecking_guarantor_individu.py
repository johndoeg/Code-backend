import re
from datetime import date, datetime

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import _aws_presign, _aws_delete, copy_object
from app.utils.helpers.base_format import _username, _strip_non_digit
from app.utils.helpers.prechecking_documents import (
    DocumentError,
    save_prechecking_document,
    remove_prechecking_document,
)

prechecking_edit_guarantor_bp = Blueprint("prechecking_edit_guarantor", __name__, url_prefix="/Prechecking/EditGuarantor")

FALLBACK_MARITAL_CODES = {"S", "M", "D", "O", "P"}
MARRIED_CODES = ("M", "O")
WNA_ID_TYPES = ("KITAS", "KITAP")
SPOUSE_DOC_SUFFIXES = ("spouse-ktp", "wna-spouse-ktp", "spouse-kitas", "spouse-kitap")

_NIK_RE = re.compile(r"^\d{16}$")
_RTRW_RE = re.compile(r"^\d{3}$")
_DOB_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")

PERSON_FIELDS = [
    ("idCardNo",     "NIK",            "NIK",            True),
    ("name",         "Nama",           "Nama",           True),
    ("placeOfBirth", "Tempat_Lahir",   "Tempat Lahir",   True),
    ("dateOfBirth",  "Tgl_Lahir",      "Tanggal Lahir",  True),
    ("gender",       "Jenis_Kelamin",  "Jenis Kelamin",  True),
    ("bloodType",    "Golongan_Darah", "Golongan Darah", False),
    ("address",      "Alamat",         "Alamat",         True),
    ("rt",           "RT",             "RT",             True),
    ("rw",           "RW",             "RW",             True),
    ("subdistrict",  "Kelurahan",      "Kelurahan/Desa", True),
    ("district",     "Kecamatan",      "Kecamatan",      True),
    ("city",         "Kota",           "Kota/Kabupaten", True),
    ("province",     "Provinsi",       "Provinsi",       True),
    ("religion",     "Agama",          "Agama",          False),
    ("job",          "Pekerjaan",      "Pekerjaan",      True),
]
REQUIRED_PERSON_KEYS = [f[0] for f in PERSON_FIELDS if f[0] != "bloodType"]
DUKCAPIL_KEYS = [f[0] for f in PERSON_FIELDS if f[3]]
_COL = {f[0]: f[1] for f in PERSON_FIELDS}
_LABEL = {f[0]: f[2] for f in PERSON_FIELDS}

def _s(value) -> str:
    return "" if value is None else str(value).strip()

def _bit(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if _s(value) in ("True", "true", "1") else 0

def _carro(value) -> int:
    return 1 if _s(value) in ("1", "True", "true") else 0

def _dob_to_sql(value):
    v = _s(value)
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def _dob_to_display(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d-%m-%Y")
    v = _s(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v[:19] if fmt.endswith("%S") else v[:10], fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return v

def _norm_id_type(value, citizen: str) -> str:
    if citizen != "WNA":
        return "KTP"
    v = _s(value).upper()
    return v if v in WNA_ID_TYPES else "KITAS"

GUARANTOR_CHECK_FOR = "G"
GUARANTOR_DOC_PREFIX = "guarantor"
GUARANTOR_ORG_TYPE = "GUARNPR"
GUARANTOR_AWS_PREFIX = "upload_doc/guarantor"

def _has_document(prechecking_id: str, document_type: str) -> bool:
    row = db.session.execute(text("""
        SELECT TOP 1 CustomerDocumentId FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": document_type}).fetchone()
    return row is not None

def _marital_codes() -> set:
    try:
        rows = db.session.execute(text("SELECT Marital FROM MSTMARITAL WITH(NOLOCK)")).fetchall()
        codes = {_s(r.Marital).upper() for r in rows if _s(r.Marital)}
        return codes or FALLBACK_MARITAL_CODES
    except Exception:
        current_app.logger.exception("MSTMARITAL lookup failed")
        return FALLBACK_MARITAL_CODES

def _spouse_doc_to_keep(prefix: str, is_married: bool, customer_citizen: str,
                        spouse_citizen: str, spouse_id_type: str):

    if not is_married:
        return None
    if spouse_citizen == "WNI":
        return f"{prefix}-wna-spouse-ktp" if customer_citizen == "WNA" else f"{prefix}-spouse-ktp"
    if spouse_citizen == "WNA" and spouse_id_type in WNA_ID_TYPES:
        return f"{prefix}-spouse-{spouse_id_type.lower()}"
    return None

def _remove_stale_spouse_docs(prechecking_id: str, prefix: str, keep_type) -> list:
    
    stale = [f"{prefix}-{sfx}" for sfx in SPOUSE_DOC_SUFFIXES if f"{prefix}-{sfx}" != keep_type]
    placeholders = ", ".join(f":dt_{i}" for i in range(len(stale)))
    params = {"pid": prechecking_id, **{f"dt_{i}": t for i, t in enumerate(stale)}}
    rows = db.session.execute(text(f"""
        SELECT CustomerDocumentId, AWSKey FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType IN ({placeholders})
    """), params).fetchall()
    if rows:
        db.session.execute(text(f"""
            DELETE FROM TEMP_CUSTOMER_DOCUMENT
            WHERE Prechecking_Id = :pid AND DocumentType IN ({placeholders})
        """), params)
    return [r.AWSKey for r in rows if r.AWSKey]

_SPOUSE_KTP_META = {
    "guarantor-spouse-ktp":     ("-GUARANTOR_SPOUSE_KTP-",     "DATA_GUARANTOR/KTP"),
    "guarantor-wna-spouse-ktp": ("-GUARANTOR_WNA_SPOUSE_KTP-", "DATA_GUARANTOR/KTP_PASANGAN"),
}

class CarryOverError(Exception):
    pass

def _carry_source(carried):
    if not isinstance(carried, list):
        return None
    for item in carried:
        doc_id = item.get("customer_document_id") if isinstance(item, dict) else None
        if not doc_id:
            continue
        src = db.session.execute(text("""
            SELECT CustomerDocumentId, DocumentName, AWSKey, OrganizationType, Prechecking_Id
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE CustomerDocumentId = :id
        """), {"id": doc_id}).fetchone()
        if src and src.AWSKey:
            return src
    return None

def _carry_spouse_ktp(prechecking_id: str, apless: str, target_type: str, src) -> list:
    name_prefix, subfolder = _SPOUSE_KTP_META.get(
        target_type, (f"-{target_type.upper().replace('-', '_')}-", target_type)
    )
    source_name = re.sub(r"^[^-]*-[A-Z0-9_]+-", "", src.DocumentName or "", count=1) or "document"
    org_type = src.OrganizationType or GUARANTOR_ORG_TYPE
    doc_name = f"{prechecking_id}{name_prefix}{source_name}"
    aws_key = f"{GUARANTOR_AWS_PREFIX}/{apless}/{prechecking_id}/{subfolder}/{doc_name}"

    old_rows = db.session.execute(text("""
        SELECT CustomerDocumentId, AWSKey FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": target_type}).fetchall()

    try:
        copied = copy_object(src.AWSKey, aws_key)
    except Exception:
        current_app.logger.exception("spouse KTP copy failed for %s", src.AWSKey)
        copied = False
    if not copied:
        raise CarryOverError("Failed to copy the spouse KTP file. Please upload it manually.")

    db.session.execute(text("""
        DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": target_type})
    db.session.execute(text("""
        INSERT INTO TEMP_CUSTOMER_DOCUMENT
            (Apless, DocumentName, OrganizationType, NumberOfDocuments,
             DocumentType, CreatedBy, CreatedDate, AWSKey, Prechecking_Id)
        VALUES
            (:apless, :name, :org_type, '1', :dt, :user, GETDATE(), :aws_key, :pid)
    """), {
        "apless": apless, "name": doc_name, "org_type": org_type, "dt": target_type,
        "user": _username(), "aws_key": aws_key, "pid": prechecking_id,
    })
    return [r.AWSKey for r in old_rows if r.AWSKey and r.AWSKey != aws_key]

def _delete_s3_keys(keys) -> None:
    for key in keys:
        try:
            _aws_delete(key)
        except Exception:
            current_app.logger.exception("S3 delete failed for %s", key)

_RATE_SELECT = ", ".join(f"r.{f[1]} AS r_{f[1]}" for f in PERSON_FIELDS)
_DUK_SELECT = ", ".join(f"d.{f[1]} AS d_{f[1]}" for f in PERSON_FIELDS if f[3])
_OCR_SELECT = ", ".join(f"o.{f[1]}" for f in PERSON_FIELDS)

_FETCH_PERSON_SQL = f"""
    SELECT TOP 1
        o.Id, o.Citizen, o.Id_Type, o.Status_Perkawinan, o.Kewarnegaraan,
        o.Foto, o.Tanda_Tangan, {_OCR_SELECT},
        r.Id AS r_Id, r.Kewarnegaraan AS r_Kewarnegaraan, {_RATE_SELECT},
        d.Id AS d_Id, {_DUK_SELECT}
    FROM TEMP_CAFLESS_OCR o WITH(NOLOCK)
        LEFT JOIN TEMP_CAFLESS_OCR_Rate r WITH(NOLOCK) ON r.Id = o.Id
        LEFT JOIN TEMP_CAFLESS_OCR_Dukcapil d WITH(NOLOCK) ON d.Id = o.Id
    WHERE o.Prechecking_Id = :pid AND o.OCR_For = :ocr_for
    ORDER BY o.Id DESC
"""

def _fetch_person(prechecking_id: str, ocr_for: str):
    row = db.session.execute(text(_FETCH_PERSON_SQL), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchone()
    return dict(row._mapping) if row else None

def _citizen_of(rec) -> str:
    if not rec:
        return ""
    return "WNA" if _s(rec.get("Citizen")).upper() == "WNA" else "WNI"

def _record_values(rec) -> dict:
    values = {key: _s(rec.get(col)) for key, col in _COL.items()}
    values["dateOfBirth"] = _dob_to_display(rec.get("Tgl_Lahir"))
    return values

def _record_conf(rec) -> dict:
    conf = {key: _strip_non_digit(_s(rec.get(f"r_{col}"))) for key, col in _COL.items()}
    conf["citizen"] = _strip_non_digit(_s(rec.get("r_Kewarnegaraan")))
    return conf

def _record_ver(rec) -> dict:
    return {key: ("True" if _bit(rec.get(f"d_{_COL[key]}")) else "False") for key in DUKCAPIL_KEYS}

def _to_ocr_record(rec) -> dict:
    v = _record_values(rec)
    ver = _record_ver(rec)
    checked = rec.get("d_Id") is not None
    citizen = _citizen_of(rec)
    return {
        "id": rec["Id"],
        "nik": v["idCardNo"],
        "nama": v["name"],
        "tempatLahir": v["placeOfBirth"],
        "tglLahir": v["dateOfBirth"],
        "jenisKelamin": v["gender"],
        "golonganDarah": v["bloodType"],
        "alamat": v["address"],
        "rtRw": f'{v["rt"]}/{v["rw"]}' if (v["rt"] or v["rw"]) else "",
        "kelurahan": v["subdistrict"],
        "kecamatan": v["district"],
        "kota": v["city"],
        "provinsi": v["province"],
        "agama": v["religion"],
        "pekerjaan": v["job"],
        "status_perkawinan": _s(rec.get("Status_Perkawinan")),
        "kewarnegaraan": _s(rec.get("Kewarnegaraan")) or citizen,
        "idType": _norm_id_type(rec.get("Id_Type"), citizen),
        "foto": _s(rec.get("Foto")),
        "tandaTangan": _s(rec.get("Tanda_Tangan")),
        "confidence": _record_conf(rec),
        "verified": ver,
        "dukcapil": {
            "checked": checked,
            "status": all(x == "True" for x in ver.values()) if checked else None,
            "reason": "",
        },
    }

def _wni_signature(values: dict, conf: dict, ver: dict, photo: str, signature: str) -> dict:
    sig = {"citizen": "WNI", "id_type": "KTP"}
    for key in _COL:
        sig[key] = _dob_to_sql(values.get(key)) if key == "dateOfBirth" else _s(values.get(key))
    sig["conf"] = {k: _strip_non_digit(_s(conf.get(k))) for k in list(_COL) + ["citizen"]}
    sig["ver"] = {k: _bit(ver.get(k)) for k in DUKCAPIL_KEYS}
    sig["photo"] = photo
    sig["signature"] = signature
    return sig

def _wna_signature(name, id_no, id_type) -> dict:
    return {"citizen": "WNA", "id_type": id_type, "idCardNo": _s(id_no), "name": _s(name)}

def _db_signature(rec):
    if not rec:
        return None
    citizen = _citizen_of(rec)
    if citizen == "WNA":
        return _wna_signature(rec.get("Nama"), rec.get("NIK"), _norm_id_type(rec.get("Id_Type"), "WNA"))
    values = _record_values(rec)
    return _wni_signature(values, _record_conf(rec), _record_ver(rec),
                          _s(rec.get("Foto")), _s(rec.get("Tanda_Tangan")))

def _payload_wni_signature(block: dict, current_rec) -> dict:
    person = block.get("person") or {}
    photo = _s(person.get("photo")) or (_s(current_rec.get("Foto")) if current_rec else "")
    sign = _s(person.get("signature")) or (_s(current_rec.get("Tanda_Tangan")) if current_rec else "")
    return _wni_signature(person, block.get("conf") or {}, block.get("ver") or {}, photo, sign)

def _validate_person(prefix: str, label: str, person: dict) -> dict:
    errors = {}
    for key in REQUIRED_PERSON_KEYS:
        if not _s(person.get(key)):
            errors[f"{prefix}.{key}"] = f"{label} {_LABEL[key]} is required"

    nik = _s(person.get("idCardNo"))
    if nik and not _NIK_RE.match(nik):
        errors[f"{prefix}.idCardNo"] = f"{label} NIK must be 16 digits (numbers only)"

    dob = _s(person.get("dateOfBirth"))
    if dob:
        parsed = _dob_to_sql(dob) if _DOB_RE.match(dob) else None
        if not parsed:
            errors[f"{prefix}.dateOfBirth"] = f"{label} Tanggal Lahir must be a valid date in dd-mm-yyyy format"
        elif parsed > date.today().strftime("%Y-%m-%d"):
            errors[f"{prefix}.dateOfBirth"] = f"{label} Tanggal Lahir cannot be in the future"

    for key in ("rt", "rw"):
        value = _s(person.get(key))
        if value and not _RTRW_RE.match(value):
            errors[f"{prefix}.{key}"] = f"{label} {_LABEL[key]} must be a 3-digit number (e.g. 003)"
    return errors

def _delete_ocr_ids(ids) -> None:
    for ocr_id in ids:
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Dukcapil WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Rate WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR WHERE Id = :id"), {"id": ocr_id})

def _clear_person(prechecking_id: str, ocr_for: str, keep_id=None) -> None:
    rows = db.session.execute(text("""
        SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchall()
    _delete_ocr_ids([r.Id for r in rows if r.Id != keep_id])

def _save_wni_person(prechecking_id: str, ocr_for: str, ocr_id, block: dict, marital: str) -> None:
    person = block.get("person") or {}
    conf = block.get("conf") or {}
    ver = block.get("ver") or {}

    params = {key: _s(person.get(key)) for key in _COL}
    params["dateOfBirth"] = _dob_to_sql(person.get("dateOfBirth"))
    photo = _s(person.get("photo")) or None
    sign = _s(person.get("signature")) or None
    params.update({
        "pid": prechecking_id, "ocr_for": ocr_for, "marital": marital,
        "photo": photo, "sign": sign,
    })

    if ocr_id:
        media_set = ""
        if photo is not None:
            media_set += "Foto = :photo, "
        if sign is not None:
            media_set += "Tanda_Tangan = :sign, "
        db.session.execute(text(f"""
            UPDATE TEMP_CAFLESS_OCR SET
                Citizen = 'WNI', Id_Type = 'KTP', Kewarnegaraan = 'WNI',
                NIK = :idCardNo, Nama = :name, Tempat_Lahir = :placeOfBirth, Tgl_Lahir = :dateOfBirth,
                Jenis_Kelamin = :gender, Golongan_Darah = :bloodType, Alamat = :address,
                RT = :rt, RW = :rw, Kelurahan = :subdistrict, Kecamatan = :district,
                Kota = :city, Provinsi = :province, Agama = :religion, Pekerjaan = :job,
                Status_Perkawinan = :marital, {media_set}
                UpdatedDate = GETDATE()
            WHERE Id = :id
        """), {**params, "id": ocr_id})
    else:
        ocr_id = db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR
                (Prechecking_Id, OCR_For, Citizen, Id_Type, Kewarnegaraan,
                 NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat,
                 RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                 Status_Perkawinan, Foto, Tanda_Tangan, UpdatedDate)
            OUTPUT INSERTED.Id
            VALUES
                (:pid, :ocr_for, 'WNI', 'KTP', 'WNI',
                 :idCardNo, :name, :placeOfBirth, :dateOfBirth, :gender, :bloodType, :address,
                 :rt, :rw, :subdistrict, :district, :city, :province, :religion, :job,
                 :marital, :photo, :sign, GETDATE())
        """), params).fetchone().Id

    rate = {key: _strip_non_digit(_s(conf.get(key))) for key in _COL}
    rate.update({"citizen": _strip_non_digit(_s(conf.get("citizen"))), "id": ocr_id})
    if db.session.execute(text("SELECT 1 FROM TEMP_CAFLESS_OCR_Rate WITH(NOLOCK) WHERE Id = :id"), {"id": ocr_id}).fetchone():
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS_OCR_Rate SET
                NIK = :idCardNo, Nama = :name, Tempat_Lahir = :placeOfBirth, Tgl_Lahir = :dateOfBirth,
                Jenis_Kelamin = :gender, Golongan_Darah = :bloodType, Alamat = :address,
                RT = :rt, RW = :rw, Kelurahan = :subdistrict, Kecamatan = :district,
                Kota = :city, Provinsi = :province, Agama = :religion, Pekerjaan = :job,
                Kewarnegaraan = :citizen
            WHERE Id = :id
        """), rate)
    else:
        db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR_Rate
                (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat,
                 RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
            VALUES
                (:id, :idCardNo, :name, :placeOfBirth, :dateOfBirth, :gender, :bloodType, :address,
                 :rt, :rw, :subdistrict, :district, :city, :province, :religion, :job, :citizen)
        """), rate)

    duk = {key: _bit(ver.get(key)) for key in DUKCAPIL_KEYS}
    duk["id"] = ocr_id
    if db.session.execute(text("SELECT 1 FROM TEMP_CAFLESS_OCR_Dukcapil WITH(NOLOCK) WHERE Id = :id"), {"id": ocr_id}).fetchone():
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                NIK = :idCardNo, Nama = :name, Tempat_Lahir = :placeOfBirth, Tgl_Lahir = :dateOfBirth,
                Jenis_Kelamin = :gender, Alamat = :address, RT = :rt, RW = :rw,
                Kelurahan = :subdistrict, Kecamatan = :district, Kota = :city,
                Provinsi = :province, Pekerjaan = :job
            WHERE Id = :id
        """), duk)
    else:
        db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Alamat, RT, RW,
                 Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
            VALUES
                (:id, :idCardNo, :name, :placeOfBirth, :dateOfBirth, :gender, :address, :rt, :rw,
                 :subdistrict, :district, :city, :province, :job)
        """), duk)

    _clear_person(prechecking_id, ocr_for, keep_id=ocr_id)

def _save_wna_person(prechecking_id: str, ocr_for: str, ocr_id, name: str, id_no: str,
                     id_type: str, marital: str) -> None:
    params = {"pid": prechecking_id, "ocr_for": ocr_for, "name": name, "nik": id_no,
              "id_type": id_type, "marital": marital}
    if ocr_id:
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS_OCR SET
                Citizen = 'WNA', Kewarnegaraan = 'WNA', Id_Type = :id_type,
                Nama = :name, NIK = :nik, Status_Perkawinan = :marital, UpdatedDate = GETDATE()
            WHERE Id = :id
        """), {**params, "id": ocr_id})
    else:
        ocr_id = db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR
                (Prechecking_Id, OCR_For, Citizen, Kewarnegaraan, Id_Type, Nama, NIK,
                 Status_Perkawinan, UpdatedDate)
            OUTPUT INSERTED.Id
            VALUES (:pid, :ocr_for, 'WNA', 'WNA', :id_type, :name, :nik, :marital, GETDATE())
        """), params).fetchone().Id
    _clear_person(prechecking_id, ocr_for, keep_id=ocr_id)

@prechecking_edit_guarantor_bp.route("/get-data", methods=["GET"])
@login_required
def get_data():
    apless = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id", "")

    if not apless or not prechecking_id:
        return jsonify({"error": "apless and prechecking_id are required"}), 400

    row = db.session.execute(text("""
        SELECT Apless, CustomerType, Check_For, Repeat_Order, Notes, Carro, MaritalStatus
        FROM TEMP_CAFLESS WITH(NOLOCK)
        WHERE Apless = :apless AND Prechecking_Id = :pid
    """), {"apless": apless, "pid": prechecking_id}).fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404
    if (row.CustomerType or "") != "PR":
        return jsonify({"error": "This endpoint only serves individual (PR) prechecking records"}), 400
    if (row.Check_For or "") != GUARANTOR_CHECK_FOR:
        return jsonify({"error": "This endpoint only serves guarantor prechecking records"}), 400

    check_for = GUARANTOR_CHECK_FOR

    cust_rec = _fetch_person(prechecking_id, check_for)
    if cust_rec is None:
        return jsonify({"error": "OCR data not found for this prechecking"}), 404
    nationality = _citizen_of(cust_rec)

    marital = _s(row.MaritalStatus).upper()
    spouse = None
    if marital in MARRIED_CODES:
        sp_rec = _fetch_person(prechecking_id, "S")
        if sp_rec:
            sp_citizen = _citizen_of(sp_rec)
            spouse = {
                "nationality": sp_citizen,
                "idType": _norm_id_type(sp_rec.get("Id_Type"), sp_citizen),
                "record": _to_ocr_record(sp_rec),
            }

    last_checking_date = ""
    lc_row = db.session.execute(text("""
        SELECT MAX(sik.CreatedDate) AS LastCheckingDate
        FROM TEMP_SIK_CHECKING_DOCUMENT sik WITH(NOLOCK)
            INNER JOIN TEMP_CAFLESS tc WITH(NOLOCK) ON tc.Prechecking_Id = sik.Prechecking_Id
        WHERE tc.FINAL_APLESS = :apless
    """), {"apless": apless}).fetchone()
    if lc_row and lc_row.LastCheckingDate:
        last_checking_date = lc_row.LastCheckingDate.strftime("%d-%m-%Y %H:%M:%S")

    outstanding = 0.0
    for sql in [
        """SELECT SUM(b.OUTS_PRINC) AS v FROM V_DataKredit a WITH(NOLOCK)
               LEFT JOIN CLFPAY b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                   AND b.PERIOD = (SELECT ISNULL(MAX(period), 0) FROM CLFPAY
                                   WHERE DATE_PAY IS NOT NULL AND LEASE_NO = a.LEASE_NO)
           WHERE a.APLESS = :apless AND a.UPD_STAT = 'Y' AND a.EXECUTION IS NOT NULL""",
        """SELECT SUM(v) AS v FROM (
               SELECT SUM(d.Net_Finance) AS v FROM CLFCONT_DATA a WITH(NOLOCK)
                   INNER JOIN MCMOCAMCOMPLETELIST b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                   INNER JOIN CAFLESS c WITH(NOLOCK) ON a.LESSEE_NO = c.lessee_no
                   INNER JOIN V_NetFinance d ON a.LEASE_NO = d.LEASE_NO
               WHERE EXECUTION IS NULL AND b.AdmSts = 1 AND apless = :apless

               UNION ALL

               SELECT SUM(d.Net_Finance) AS v FROM MCMOCAMCOMPLETELIST a WITH(NOLOCK)
                   INNER JOIN cafcont b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                   INNER JOIN V_NetFinance d ON a.APPL_NO = d.APPL_NO
               WHERE b.DateTrans IS NULL AND a.AdmSts = 1 AND apless = :apless
           ) x""",
    ]:
        try:
            r = db.session.execute(text(sql), {"apless": apless}).fetchone()
            if r and r.v:
                outstanding += float(r.v)
        except Exception:
            current_app.logger.exception("outstanding calc failed")

    sik_rows = db.session.execute(text("""
        SELECT Subject, CreditBureau, Status, Score, Grade
        FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid
    """), {"pid": prechecking_id}).fetchall()
    sik = [{
        "subject": "Customer" if s.Subject == "C" else ("Guarantor" if s.Subject == "G" else "Pengurus"),
        "creditBureau": s.CreditBureau or "",
        "status": s.Status or "",
        "score": str(s.Score or ""),
        "grade": s.Grade or "",
    } for s in sik_rows]

    return jsonify({
        "apless": apless,
        "prechecking_id": prechecking_id,
        "check_for": check_for,
        "customer_type": "PR",
        "repeat_order": "1" if str(row.Repeat_Order) == "1" else "0",
        "is_carro": str(_carro(row.Carro)),
        "note": row.Notes or "",
        "last_checking_date": last_checking_date,
        "outstanding": outstanding,
        "marital_status": marital,
        "nationality": nationality,
        "cust_id_type": _norm_id_type(cust_rec.get("Id_Type"), nationality),
        "customer": _to_ocr_record(cust_rec),
        "spouse": spouse,
        "sik": sik,
    })

@prechecking_edit_guarantor_bp.route("/aws-download", methods=["GET"])
@login_required
def aws_download():
    aws_key = request.args.get("aws_key", "").strip()
    file_name = request.args.get("file_name", "download").strip()
    if not aws_key:
        return jsonify({"error": "aws_key required"}), 400
    try:
        url = _aws_presign(aws_key, file_name)
        return jsonify({"url": url, "file_name": file_name})
    except Exception as exc:
        current_app.logger.exception(exc)
        return jsonify({"error": str(exc)}), 500

@prechecking_edit_guarantor_bp.route("/upload-document", methods=["POST"])
@login_required
def upload_document():
    apless = request.form.get("apless", "")
    prechecking_id = request.form.get("prechecking_id", "")
    document_type = request.form.get("document_type", "")
    file = request.files.get("file")

    if not apless or not prechecking_id or not document_type:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    try:
        doc = save_prechecking_document(file, apless, prechecking_id, document_type, _username())
        return jsonify({"success": True, "document": doc})
    except DocumentError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        current_app.logger.exception("upload_document failed")
        return jsonify({"success": False, "message": "Upload failed"}), 500

@prechecking_edit_guarantor_bp.route("/delete-document", methods=["POST"])
@login_required
def delete_document():
    payload = request.get_json(silent=True) or {}
    prechecking_id = payload.get("prechecking_id", "")
    document_type = payload.get("document_type", "")
    customer_document_id = payload.get("customer_document_id")

    if not prechecking_id or not document_type:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    try:
        remove_prechecking_document(prechecking_id, document_type, customer_document_id)
        return jsonify({"success": True})
    except DocumentError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception:
        current_app.logger.exception("delete_document failed")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@prechecking_edit_guarantor_bp.route("/submit", methods=["POST"])
@login_required
def submit():
    payload = request.get_json(silent=True) or {}
    apless = _s(payload.get("apless"))
    prechecking_id = _s(payload.get("prechecking_id"))

    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400

    row = db.session.execute(text("""
        SELECT CustomerType, Check_For, MaritalStatus, Notes, Carro
        FROM TEMP_CAFLESS WITH(NOLOCK)
        WHERE Apless = :apless AND Prechecking_Id = :pid
    """), {"apless": apless, "pid": prechecking_id}).fetchone()
    if not row:
        return jsonify({"success": False, "message": "Prechecking record not found"}), 404
    if (row.CustomerType or "") != "PR":
        return jsonify({"success": False, "message": "This endpoint only handles individual (PR) records"}), 400
    if (row.Check_For or "") != GUARANTOR_CHECK_FOR:
        return jsonify({"success": False, "message": "This endpoint only handles guarantor records"}), 400

    check_for = GUARANTOR_CHECK_FOR
    prefix = GUARANTOR_DOC_PREFIX

    cur_cust = _fetch_person(prechecking_id, check_for)
    if not cur_cust:
        return jsonify({"success": False, "message": "Guarantor OCR data not found"}), 404
    cur_spouse = _fetch_person(prechecking_id, "S")
    nationality = _citizen_of(cur_cust)

    marital = _s(payload.get("marital_status")).upper()
    note = _s(payload.get("note"))
    carro = _carro(payload.get("is_carro"))
    is_married = marital in MARRIED_CODES

    errors: dict = {}
    if marital not in _marital_codes():
        errors["marital_status"] = "Please select a valid marital status"

    cust_block = payload.get("customer") or {}
    wna_block = payload.get("wna_customer") or {}
    cust_id_type = "KTP"
    if nationality == "WNI":
        cust_person = cust_block.get("person") or {}
        errors.update(_validate_person("customer", "Guarantor", cust_person))
        if _s(cust_person.get("idCardNo")) and _s(cust_person.get("idCardNo")) != _s(cur_cust.get("NIK")):
            errors["customer.idCardNo"] = "Guarantor NIK cannot be changed on edit"
        if not _has_document(prechecking_id, f"{prefix}-ktp"):
            errors["customer.document"] = "Guarantor KTP file is required"
        cust_name, cust_id_no = _s(cust_person.get("name")), _s(cur_cust.get("NIK"))
    else:
        cust_id_type = _s(payload.get("cust_id_type")).upper()
        cust_name, cust_id_no = _s(wna_block.get("name")), _s(wna_block.get("id_no"))
        if cust_id_type not in WNA_ID_TYPES:
            errors["customer.idType"] = "Guarantor ID Type must be KITAS or KITAP"
        if not cust_name:
            errors["customer.name"] = "Guarantor Nama is required"
        if not cust_id_no:
            errors["customer.idCardNo"] = f"Guarantor {cust_id_type or 'ID'} number is required"
        stored_type = _norm_id_type(cur_cust.get("Id_Type"), "WNA")
        if cust_id_type in WNA_ID_TYPES and cust_id_type != stored_type \
                and not _has_document(prechecking_id, f"{prefix}-{cust_id_type.lower()}"):
            errors["customer.document"] = f"Guarantor {cust_id_type} file is required when changing ID Type"

    sp_block = payload.get("spouse") or {}
    sp_nat = _s(sp_block.get("nationality")).upper()
    sp_id_type = "KTP"
    carry_src = None
    if is_married:
        if sp_nat not in ("WNI", "WNA"):
            errors["spouse.nationality"] = "Spouse Nationality is required"
        elif sp_nat == "WNI":
            sp_person = sp_block.get("person") or {}
            errors.update(_validate_person("spouse", "Spouse", sp_person))
            sp_nik = _s(sp_person.get("idCardNo"))
            if nationality == "WNI" and sp_nik and sp_nik == _s(cur_cust.get("NIK")):
                errors["spouse.idCardNo"] = "Spouse NIK cannot be the same as the guarantor NIK"
            sp_doc = f"{prefix}-wna-spouse-ktp" if nationality == "WNA" else f"{prefix}-spouse-ktp"
            carry_src = _carry_source(sp_block.get("carried_documents"))
            if carry_src is None and not _has_document(prechecking_id, sp_doc):
                errors["spouse.document"] = "Spouse KTP file is required"
            nik_changed = (
                not cur_spouse or _citizen_of(cur_spouse) != "WNI" or _s(cur_spouse.get("NIK")) != sp_nik
            )
            if nik_changed and not (sp_block.get("dukcapil") or {}).get("checked"):
                errors["spouse.dukcapil"] = "Please verify the Spouse KTP data with Dukcapil before saving"
        else:
            sp_id_type = _s(sp_block.get("id_type")).upper()
            if sp_id_type not in WNA_ID_TYPES:
                errors["spouse.idType"] = "Spouse ID Type must be KITAS or KITAP"
            if not _s(sp_block.get("name")):
                errors["spouse.name"] = "Spouse Name is required"
            if not _s(sp_block.get("id_no")):
                errors["spouse.idCardNo"] = f"Spouse {sp_id_type or 'ID'} number is required"
            type_changed = (
                not cur_spouse or _citizen_of(cur_spouse) != "WNA"
                or _norm_id_type(cur_spouse.get("Id_Type"), "WNA") != sp_id_type
            )
            if sp_id_type in WNA_ID_TYPES and type_changed \
                    and not _has_document(prechecking_id, f"{prefix}-spouse-{sp_id_type.lower()}"):
                errors["spouse.document"] = f"Spouse {sp_id_type} file is required"

    if errors:
        return jsonify({"success": False, "errors": errors, "message": "\n".join(errors.values())}), 422

    cur_married = _s(row.MaritalStatus).upper() in MARRIED_CODES
    current_sig = {
        "marital": _s(row.MaritalStatus).upper(),
        "note": _s(row.Notes),
        "carro": _carro(row.Carro),
        "customer": _db_signature(cur_cust),
        "spouse": _db_signature(cur_spouse) if cur_married else None,
    }
    if nationality == "WNI":
        new_cust_sig = _payload_wni_signature(cust_block, cur_cust)
    else:
        new_cust_sig = _wna_signature(cust_name, cust_id_no, cust_id_type)
    if not is_married:
        new_sp_sig = None
    elif sp_nat == "WNI":
        same_person = cur_spouse if _citizen_of(cur_spouse) == "WNI" else None
        new_sp_sig = _payload_wni_signature(sp_block, same_person)
    else:
        new_sp_sig = _wna_signature(sp_block.get("name"), sp_block.get("id_no"), sp_id_type)
    new_sig = {
        "marital": marital, "note": note, "carro": carro,
        "customer": new_cust_sig, "spouse": new_sp_sig,
    }
    if carry_src is not None:
        new_sig["spouse_file"] = carry_src.CustomerDocumentId

    keep_spouse_doc = _spouse_doc_to_keep(prefix, is_married, nationality, sp_nat, sp_id_type)

    if new_sig == current_sig:
        try:
            stale_keys = _remove_stale_spouse_docs(prechecking_id, prefix, keep_spouse_doc)
            db.session.commit()
            _delete_s3_keys(stale_keys)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("stale spouse document cleanup failed")
        return jsonify({"success": True, "no_changes": True, "message": "No data changes"})

    try:
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS
            SET MaritalStatus = :marital, Notes = :note, Carro = :carro,
                LesseeName = :name, IdCardNo = :id_no
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {
            "marital": marital, "note": note, "carro": carro,
            "name": cust_name, "id_no": cust_id_no,
            "apless": apless, "pid": prechecking_id,
        })

        if new_cust_sig != current_sig["customer"] or marital != current_sig["marital"]:
            if nationality == "WNI":
                _save_wni_person(prechecking_id, check_for, cur_cust["Id"], cust_block, marital)
            else:
                _save_wna_person(prechecking_id, check_for, cur_cust["Id"],
                                 cust_name, cust_id_no, cust_id_type, marital)

        if not is_married:
            _clear_person(prechecking_id, "S")
        elif new_sp_sig != current_sig["spouse"] or marital != current_sig["marital"]:
            same_citizen = cur_spouse and _citizen_of(cur_spouse) == sp_nat
            if cur_spouse and not same_citizen:
                _clear_person(prechecking_id, "S")
            sp_id = cur_spouse["Id"] if same_citizen else None
            if sp_nat == "WNI":
                _save_wni_person(prechecking_id, "S", sp_id, sp_block, marital)
            else:
                _save_wna_person(prechecking_id, "S", sp_id, _s(sp_block.get("name")),
                                 _s(sp_block.get("id_no")), sp_id_type, marital)

        replaced_keys = []
        if carry_src is not None and keep_spouse_doc:
            replaced_keys = _carry_spouse_ktp(prechecking_id, apless, keep_spouse_doc, carry_src)

        stale_keys = _remove_stale_spouse_docs(prechecking_id, prefix, keep_spouse_doc)

        db.session.commit()
        _delete_s3_keys(replaced_keys + stale_keys)
        return jsonify({"success": True, "no_changes": False, "message": "Data updated successfully"})
    except CarryOverError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("edit guarantor individu submit failed")
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500