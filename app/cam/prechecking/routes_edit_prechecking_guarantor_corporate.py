from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
from datetime import datetime
import base64, os, mimetypes, re

from botocore.exceptions import BotoCoreError, ClientError

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import (
    _aws_upload, _aws_delete, _aws_presign, _validate_file, copy_object,
)

from app.utils.helpers.base_format import (
    _username, _branch, _emp_id, _to_bit, _strip_non_digit, fmt_date, parse_date, as_of_date, can_edit, format_threshold, get_combo
)

prechecking_guarantor_corporate_bp = Blueprint("prechecking_guarantor_corporate", __name__, url_prefix="/CAM/Prechecking")

_OCR_DOC_TYPE_RE = re.compile(r"^(corp-guarantor-ocr-ktp|wna-corp-guarantor-board)_[A-Za-z0-9]+$")

def _is_ocr_doc_type(document_type: str) -> bool:
    return bool(_OCR_DOC_TYPE_RE.match(document_type or ""))

def _cleanup_ocr_for_nik(prechecking_id: str, nik: str) -> None:
    if not nik:
        return

    ocr_row = db.session.execute(
        text("""
            SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND NIK = :nik AND ISNULL(OCR_For, '') <> 'H'
        """),
        {"pid": prechecking_id, "nik": nik},
    ).fetchone()
    if not ocr_row:
        return

    ocr_id = ocr_row.Id
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR_Rate WHERE Id = :id"),
        {"id": ocr_id},
    )
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR_Dukcapil WHERE Id = :id"),
        {"id": ocr_id},
    )
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR WHERE Id = :id"),
        {"id": ocr_id},
    )

_GUARANTOR_MARITAL_MAP = {
    "BELUM KAWIN": "S", "KAWIN": "M", "KAWIN TERCATAT": "M",
    "KAWIN BELUM TERCATAT": "O", "PERJANJIAN PRANIKAH": "P",
    "CERAI HIDUP": "D", "CERAI MATI": "D",
}

def _normalize_marital_guarantor(val):
    return _GUARANTOR_MARITAL_MAP.get((val or "").strip().upper(), val)

_SH_OCR_FOR = "H"
_SH_ID_TYPE = "NPWP"
_SH_PREFIX = "shareholder-npwp_"
_SH_NAME_MAX = 100
_SH_NPWP_MAX = 16

def _save_shareholders(prechecking_id: str, shareholders) -> None:
    db.session.execute(text("""
        DELETE FROM TEMP_CAFLESS_OCR
        WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for
    """), {"pid": prechecking_id, "ocr_for": _SH_OCR_FOR})

    for s in (shareholders or []):
        db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR
                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama)
            VALUES (:pid, :ocr_for, '', :id_type, :npwp, :nama)
        """), {
            "pid": prechecking_id, "ocr_for": _SH_OCR_FOR, "id_type": _SH_ID_TYPE,
            "npwp": s["npwp_no"], "nama": s["name"],
        })

_GUARANTOR_ORG_TYPE_MAP = {
    "CO": "KOPERASI",
    "CV": "CV",
    "FD": "YAYASAN",
    "PT": "PT",
}

def _guarantor_org_type_for(lessee_type: str) -> str:
    return _GUARANTOR_ORG_TYPE_MAP.get((lessee_type or "").upper(), "PT")

def _finalize_create_documents(prechecking_id, apless, username, directors, wna_board, carried, shareholders=None) -> list:
    carried = [c for c in (carried or []) if isinstance(c, dict) and c.get("customer_document_id")]
    keys: list = []
    for d in directors:
        nik = _token(d.get("id_card_no"))
        if not nik:
            continue
        target = f"{_DIR_PREFIX}{nik}"
        ids = [c["customer_document_id"] for c in carried if c.get("document_type") == target]
        keys += _finalize_member_docs(prechecking_id, apless, _DIR_PREFIX, nik,
                                      _token(d.get("doc_token")), [], ids, username)
    for w in wna_board:
        idno = _token(w.get("id_card_no"))
        if not idno:
            continue
        keys += _finalize_member_docs(prechecking_id, apless, _WNA_PREFIX, idno,
                                      _token(w.get("doc_token")), [], None, username)
    for s in (shareholders or []):
        npwp = _token(s.get("npwp_no"))
        if not npwp:
            continue
        target = f"{_SH_PREFIX}{npwp}"
        ids = [c["customer_document_id"] for c in carried if c.get("document_type") == target]
        keys += _finalize_member_docs(prechecking_id, apless, _SH_PREFIX, npwp,
                                      _token(s.get("doc_token")), [], ids, username)
    member_prefixes = (_DIR_PREFIX, _WNA_PREFIX, _SH_PREFIX)
    for c in carried:
        dtype = _s(c.get("document_type"))
        if not dtype or dtype.startswith(member_prefixes) or _docs_of_types(prechecking_id, [dtype]):
            continue
        _copy_doc_into(prechecking_id, apless, dtype, c["customer_document_id"], username)
    return keys

_CORP_GUARANTOR_DOC_META: dict = {
    "corp-guarantor-npwp":              ("-CORP_GUARANTOR_NPWP-",              "DATA_GUARANTOR/NPWP"),
    "corp-guarantor-akta":              ("-CORP_GUARANTOR_AKTA-",              "DATA_GUARANTOR/AKTA_PENDIRIAN"),
    "corp-guarantor-sk-akta":           ("-CORP_GUARANTOR_SK_AKTA-",           "DATA_GUARANTOR/SK_KEMENKUMHAM"),
    "corp-guarantor-akta-terakhir":     ("-CORP_GUARANTOR_AKTA_TERAKHIR-",     "DATA_GUARANTOR/AKTA_PERUBAHAN"),
    "corp-guarantor-sk-akta-terakhir":  ("-CORP_GUARANTOR_SK_AKTA_TERAKHIR-",  "DATA_GUARANTOR/SK_KEMENKUMHAM_PERUBAHAN"),
    "corp-guarantor-ktp-akta-terakhir": ("-CORP_GUARANTOR_KTP_AKTA_TERAKHIR-", "DATA_GUARANTOR/KTP_PENGURUS"),
}

def _corp_guarantor_doc_meta(document_type: str):
    if document_type in _CORP_GUARANTOR_DOC_META:
        return _CORP_GUARANTOR_DOC_META[document_type]

    m = re.match(r"^corp-guarantor-ocr-ktp_([A-Za-z0-9]+)$", document_type)
    if m:
        token = m.group(1)
        return (f"-CORP_GUARANTOR_KTP-{token}", "DATA_GUARANTOR/KTP_PENGURUS")

    m = re.match(r"^wna-corp-guarantor-board_([A-Za-z0-9]+)$", document_type)
    if m:
        token = m.group(1)
        return (f"-WNA_CORP_GUARANTOR-{token}", "DATA_GUARANTOR/KTP_PENGURUS")

    m = re.match(r"^shareholder-npwp_([A-Za-z0-9]+)$", document_type)
    if m:
        token = m.group(1)
        return (f"-GUARANTOR_SHAREHOLDER_NPWP-{token}-", "DATA_GUARANTOR/SHAREHOLDER_NPWP")

    return (f"-{document_type.upper().replace('-', '_')}-", document_type)

@prechecking_guarantor_corporate_bp.route("/submit-guarantor-corporate", methods=["POST"])
@login_required
def submit_prechecking_guarantor_corporate():

    username = _username()
    branch   = _branch()
    emp_id   = _emp_id()

    body = request.get_json(force=True) or {}

    def g(key, default=""):
        val = body.get(key, default)
        return val.strip() if isinstance(val, str) else (val if val is not None else default)

    prechecking_id   = g("prechecking_id")
    apless           = g("apless")
    cust_type        = g("cust_type", "PT")
    lessee_type      = g("lessee_type")
    check_for        = g("check_for", "G")
    corp_new_ro      = 0 if g("corp_new_ro", "New") == "New" else 1
    existing_apless  = g("existing_apless")
    is_carro         = int(g("is_carro_type", "1"))
    note_pt          = g("note_prechecking_pt")

    corp_name        = g("corp_guarantor_name")
    corp_address     = g("corp_guarantor_address")
    corp_npwp_no     = g("corp_guarantor_npwp_no")

    directors = body.get("directors") or []
    wna_board = body.get("wna_board") or []
    shareholders_raw = body.get("shareholders") or []

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id is required"}), 400

    errors = {}
    if not lessee_type:
        errors["corp_lessee_type_error"] = "Company Type is required"
    if not corp_name:
        errors["corp_guarantor_name_error"] = "Nama is required"
    if not corp_address:
        errors["corp_guarantor_address_error"] = "Alamat is required"
    if not corp_npwp_no:
        errors["corp_guarantor_npwp_no_error"] = "NPWP No is required"

    required_director = [
        ("id_card_no", "NIK"),
        ("name",       "Nama"),
        ("pob",        "Tempat Lahir"),
        ("dob",        "Tanggal Lahir"),
        ("gender",     "Jenis Kelamin"),
        ("address",    "Alamat"),
        ("rt",         "RT"),
        ("rw",         "RW"),
        ("subdistrict","Kelurahan/Desa"),
        ("district",   "Kecamatan"),
        ("city",       "Kota/Kabupaten"),
        ("province",   "Provinsi"),
        ("job",        "Pekerjaan"),
        ("marital_status", "Status Perkawinan"),
    ]
    
    for i, d in enumerate(directors):
        for key, label in required_director:
            if not (d.get(key) or "").strip() if isinstance(d.get(key), str) else not d.get(key):
                errors[f"corp_guarantor_board_{key}_error_{i}"] = f"{label} is required"

    shareholders = []
    seen_npwp: dict = {}
    for i, sh in enumerate(shareholders_raw):
        if not isinstance(sh, dict):
            continue
        sh_name = str(sh.get("name") or "").strip()
        sh_npwp = str(sh.get("npwp_no") or "").strip()
        if not sh_name and not sh_npwp:
            continue
        if not sh_name:
            errors[f"shareholder_{i}_name"] = f"Name is required (Shareholder #{i + 1})"
        elif len(sh_name) > _SH_NAME_MAX:
            errors[f"shareholder_{i}_name"] = f"Name must be at most {_SH_NAME_MAX} characters (Shareholder #{i + 1})"
        if not sh_npwp:
            errors[f"shareholder_{i}_npwp_no"] = f"NPWP No is required (Shareholder #{i + 1})"
        elif not sh_npwp.isdigit() or len(sh_npwp) > _SH_NPWP_MAX:
            errors[f"shareholder_{i}_npwp_no"] = f"NPWP No must be numbers only, max {_SH_NPWP_MAX} digits (Shareholder #{i + 1})"
        elif sh_npwp in seen_npwp:
            errors[f"shareholder_{i}_npwp_no"] = f"NPWP No is already used by Shareholder #{seen_npwp[sh_npwp]} (Shareholder #{i + 1})"
        else:
            seen_npwp[sh_npwp] = i + 1
        shareholders.append({"name": sh_name, "npwp_no": sh_npwp, "doc_token": sh.get("doc_token")})

    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    try:
        count_row = db.session.execute(
            text("""
                SELECT COUNT(1) AS cnt
                FROM TEMP_CAFLESS WITH(NOLOCK)
                WHERE Apless = :apless AND Prechecking_Id = :pid
            """),
            {"apless": apless, "pid": prechecking_id},
        ).fetchone()
        already_exists = (count_row.cnt > 0) if count_row else False

        approval_form_row = db.session.execute(
            text("SELECT Id FROM mstApprovalForm WHERE ApprovalFormKey = 'cam-request'"),
        ).fetchone()
        if not approval_form_row:
            return jsonify({"success": False, "message": "Approval Form Master is not completed. Please contact your administrator."}), 500
        approval_form_id = approval_form_row.Id

        ocr_for = "G"

        if not already_exists:
            db.session.execute(text("""
                INSERT INTO TEMP_CAFLESS
                    (Apless, CustomerType, LesseeType, LesseeName, NPWP, WorkAddress,
                     CreatedBy, CreatedDate, Prechecking_Id, Check_For, Repeat_Order,
                     Notes, Carro)
                VALUES
                    (:apless, :cust_type, :lessee_type, :corp_name, :npwp, :addr,
                     :username, GETDATE(), :pid, :check_for, :new_ro,
                     :note_pt, :is_carro)
            """), {
                "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                "corp_name": corp_name, "npwp": corp_npwp_no, "addr": corp_address,
                "username": username, "pid": prechecking_id, "check_for": check_for,
                "new_ro": corp_new_ro, "note_pt": note_pt, "is_carro": is_carro,
            })

            for d in directors:
                nik = (d.get("id_card_no") or "").strip()
                if not nik:
                    continue

                marital = _normalize_marital_guarantor(d.get("marital_status"))

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir, Tgl_Lahir,
                         Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW, Kelurahan,
                         Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                         Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan,
                         Prechecking_Id)
                    VALUES
                        (:ocr_for, :citizen, 'KTP', :nik, :nama, :pob, :dob,
                         :gender, :blood, :addr, :rt, :rw, :subdistrict,
                         :district, :city, :province, :religion, :job,
                         :marital, :citizen2, :photo, :sign,
                         :pid)
                """), {
                    "ocr_for": ocr_for,
                    "citizen": d.get("citizen") or "WNI",
                    "nik": nik,
                    "nama": d.get("name") or "",
                    "pob": d.get("pob") or "",
                    "dob": datetime.strptime(d.get("dob"), "%d-%m-%Y").strftime("%Y-%m-%d") if d.get("dob") else None,
                    "gender": d.get("gender") or "",
                    "blood": d.get("blood_type") or "",
                    "addr": d.get("address") or "",
                    "rt": d.get("rt") or "",
                    "rw": d.get("rw") or "",
                    "subdistrict": d.get("subdistrict") or "",
                    "district": d.get("district") or "",
                    "city": d.get("city") or "",
                    "province": d.get("province") or "",
                    "religion": d.get("religion") or "",
                    "job": d.get("job") or "",
                    "marital": marital,
                    "citizen2": d.get("citizen") or "WNI",
                    "photo": d.get("photo_hidden") or "",
                    "sign": d.get("signature_hidden") or "",
                    "pid": prechecking_id,
                })

            for d in directors:
                nik = (d.get("id_card_no") or "").strip()
                if not nik:
                    continue

                ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik AND ISNULL(OCR_For, '') <> 'H'"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                director_id = ocr_row.Id if ocr_row else 0

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Rate
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                         Kota, Provinsi, Agama, Pekerjaan, Status_Perkawinan, Kewarnegaraan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender,
                         :blood, :addr, :rt, :rw, :subdistrict, :district,
                         :city, :province, :religion, :job, :marital, :citizen)
                """), {
                    "id": director_id,
                    "nik":        _strip_non_digit(d.get("val_id_card_no")),
                    "nama":       _strip_non_digit(d.get("val_name")),
                    "pob":        _strip_non_digit(d.get("val_pob")),
                    "dob":        _strip_non_digit(d.get("val_dob")),
                    "gender":     _strip_non_digit(d.get("val_gender")),
                    "blood":      _strip_non_digit(d.get("val_blood_type")),
                    "addr":       _strip_non_digit(d.get("val_address")),
                    "rt":         _strip_non_digit(d.get("val_rt")),
                    "rw":         _strip_non_digit(d.get("val_rw")),
                    "subdistrict":_strip_non_digit(d.get("val_subdistrict")),
                    "district":   _strip_non_digit(d.get("val_district")),
                    "city":       _strip_non_digit(d.get("val_city")),
                    "province":   _strip_non_digit(d.get("val_province")),
                    "religion":   _strip_non_digit(d.get("val_religion")),
                    "job":        _strip_non_digit(d.get("val_job")),
                    "marital":    _strip_non_digit(d.get("val_marital_status")),
                    "citizen":    _strip_non_digit(d.get("val_citizen")),
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi,
                         Pekerjaan, Status_Perkawinan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender,
                         :addr, :rt, :rw, :subdistrict, :district, :city, :province,
                         :job, :marital)
                """), {
                    "id":        director_id,
                    "nik":       _to_bit(d.get("ver_id_card_no")),
                    "nama":      _to_bit(d.get("ver_name")),
                    "pob":       _to_bit(d.get("ver_pob")),
                    "dob":       _to_bit(d.get("ver_dob")),
                    "gender":    _to_bit(d.get("ver_gender")),
                    "addr":      _to_bit(d.get("ver_address")),
                    "rt":        _to_bit(d.get("ver_rt")),
                    "rw":        _to_bit(d.get("ver_rw")),
                    "subdistrict": _to_bit(d.get("ver_subdistrict")),
                    "district":  _to_bit(d.get("ver_district")),
                    "city":      _to_bit(d.get("ver_city")),
                    "province":  _to_bit(d.get("ver_province")),
                    "job":       _to_bit(d.get("ver_job")),
                    "marital":   _to_bit(d.get("ver_marital_status")),
                })

            wna_rows = [w for w in wna_board if (w.get("id_card_no") or "").strip()]
            for w in wna_rows:
                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (Prechecking_Id, OCR_For, Citizen, Kewarnegaraan, Id_Type, NIK, Nama)
                    VALUES (:pid, :ocr_for, 'WNA', 'WNA', :id_type, :nik, :nama)
                """), {
                    "pid": prechecking_id, "ocr_for": ocr_for,
                    "nik": w.get("id_card_no"), "nama": w.get("name") or "",
                    "id_type": _norm_wna_id_type(w.get("id_type")),
                })

            db.session.execute(text("""
                UPDATE TEMP_CUSTOMER_DOCUMENT
                SET OrganizationType = (SELECT LesseeType FROM TEMP_CAFLESS WHERE Prechecking_Id = :pid)
                WHERE Prechecking_Id = :pid
            """), {"pid": prechecking_id})

        else:
            db.session.execute(text("""
                UPDATE TEMP_CAFLESS SET
                    Apless=:apless, CustomerType=:cust_type, LesseeType=:lessee_type,
                    LesseeName=:corp_name, NPWP=:npwp, WorkAddress=:addr,
                    CreatedBy=:username, CreatedDate=GETDATE(),
                    Check_For=:check_for, Repeat_Order=:new_ro,
                    Notes=:note_pt, Carro=:is_carro
                WHERE Prechecking_Id=:pid
            """), {
                "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                "corp_name": corp_name, "npwp": corp_npwp_no, "addr": corp_address,
                "username": username, "check_for": check_for, "new_ro": corp_new_ro,
                "note_pt": note_pt, "is_carro": is_carro, "pid": prechecking_id,
            })

            for d in directors:
                nik = (d.get("id_card_no") or "").strip()
                if not nik:
                    continue

                marital = _normalize_marital_guarantor(d.get("marital_status"))

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        OCR_For=:ocr_for, Citizen=:citizen, Id_Type='KTP', Nama=:nama,
                        Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                        Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                        Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                        Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                        Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid AND NIK=:nik AND ISNULL(OCR_For, '') <> 'H'
                """), {
                    "ocr_for": ocr_for,
                    "citizen": d.get("citizen") or "WNI",
                    "nama": d.get("name") or "",
                    "pob": d.get("pob") or "",
                    "dob": datetime.strptime(d.get("dob"), "%d-%m-%Y").strftime("%Y-%m-%d") if d.get("dob") else None,
                    "gender": d.get("gender") or "",
                    "blood": d.get("blood_type") or "",
                    "addr": d.get("address") or "",
                    "rt": d.get("rt") or "",
                    "rw": d.get("rw") or "",
                    "subdistrict": d.get("subdistrict") or "",
                    "district": d.get("district") or "",
                    "city": d.get("city") or "",
                    "province": d.get("province") or "",
                    "religion": d.get("religion") or "",
                    "job": d.get("job") or "",
                    "marital": marital,
                    "citizen2": d.get("citizen") or "WNI",
                    "photo": d.get("photo_hidden") or "",
                    "sign": d.get("signature_hidden") or "",
                    "pid": prechecking_id,
                    "nik": nik,
                })

            director_ids = {}
            for d in directors:
                nik = (d.get("id_card_no") or "").strip()
                if not nik:
                    continue
                ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik AND ISNULL(OCR_For, '') <> 'H'"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                director_ids[nik] = ocr_row.Id if ocr_row else 0

            for d in directors:
                nik = (d.get("id_card_no") or "").strip()
                if not nik:
                    continue
                director_id = director_ids.get(nik, 0)

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Rate SET
                        NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                        RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                        Kota=:city, Provinsi=:province, Agama=:religion,
                        Pekerjaan=:job, Status_Perkawinan=:marital, Kewarnegaraan=:citizen
                    WHERE Id=:id
                """), {
                    "id": director_id,
                    "nik":        _strip_non_digit(d.get("val_id_card_no")),
                    "nama":       _strip_non_digit(d.get("val_name")),
                    "pob":        _strip_non_digit(d.get("val_pob")),
                    "dob":        _strip_non_digit(d.get("val_dob")),
                    "gender":     _strip_non_digit(d.get("val_gender")),
                    "blood":      _strip_non_digit(d.get("val_blood_type")),
                    "addr":       _strip_non_digit(d.get("val_address")),
                    "rt":         _strip_non_digit(d.get("val_rt")),
                    "rw":         _strip_non_digit(d.get("val_rw")),
                    "subdistrict":_strip_non_digit(d.get("val_subdistrict")),
                    "district":   _strip_non_digit(d.get("val_district")),
                    "city":       _strip_non_digit(d.get("val_city")),
                    "province":   _strip_non_digit(d.get("val_province")),
                    "religion":   _strip_non_digit(d.get("val_religion")),
                    "job":        _strip_non_digit(d.get("val_job")),
                    "marital":    _strip_non_digit(d.get("val_marital_status")),
                    "citizen":    _strip_non_digit(d.get("val_citizen")),
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                        NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Alamat=:addr, RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                        Provinsi=:province, Pekerjaan=:job, Status_Perkawinan=:marital
                    WHERE Id=:id
                """), {
                    "id":        director_id,
                    "nik":       _to_bit(d.get("ver_id_card_no")),
                    "nama":      _to_bit(d.get("ver_name")),
                    "pob":       _to_bit(d.get("ver_pob")),
                    "dob":       _to_bit(d.get("ver_dob")),
                    "gender":    _to_bit(d.get("ver_gender")),
                    "addr":      _to_bit(d.get("ver_address")),
                    "rt":        _to_bit(d.get("ver_rt")),
                    "rw":        _to_bit(d.get("ver_rw")),
                    "subdistrict": _to_bit(d.get("ver_subdistrict")),
                    "district":  _to_bit(d.get("ver_district")),
                    "city":      _to_bit(d.get("ver_city")),
                    "province":  _to_bit(d.get("ver_province")),
                    "job":       _to_bit(d.get("ver_job")),
                    "marital":   _to_bit(d.get("ver_marital_status")),
                })

            wna_rows = [w for w in wna_board if (w.get("id_card_no") or "").strip()]
            for w in wna_rows:
                nik = w.get("id_card_no")
                nama = w.get("name") or ""

                exists_row = db.session.execute(
                    text("""
                        SELECT COUNT(1) AS cnt FROM TEMP_CAFLESS_OCR
                        WHERE Prechecking_Id=:pid AND NIK=:nik AND ISNULL(OCR_For, '') <> 'H'
                    """),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()

                if exists_row and exists_row.cnt == 0:
                    db.session.execute(text("""
                        INSERT INTO TEMP_CAFLESS_OCR
                            (OCR_For, Citizen, Kewarnegaraan, Id_Type, Nama, Prechecking_Id, NIK)
                        VALUES (:ocr_for, 'WNA', 'WNA', :id_type, :nama, :pid, :nik)
                    """), {"ocr_for": ocr_for, "nama": nama, "pid": prechecking_id, "nik": nik,
                          "id_type": _norm_wna_id_type(w.get("id_type"))})
                else:
                    db.session.execute(text("""
                        UPDATE TEMP_CAFLESS_OCR SET
                            OCR_For=:ocr_for, Citizen='WNA', Kewarnegaraan='WNA', Id_Type=:id_type,
                            Nama=:nama, UpdatedDate=GETDATE()
                        WHERE Prechecking_Id=:pid AND NIK=:nik AND ISNULL(OCR_For, '') <> 'H'
                    """), {"ocr_for": ocr_for, "nama": nama, "pid": prechecking_id, "nik": nik,
                          "id_type": _norm_wna_id_type(w.get("id_type"))})

            db.session.execute(text("""
                UPDATE TEMP_CUSTOMER_DOCUMENT
                SET OrganizationType = (SELECT LesseeType FROM TEMP_CAFLESS WHERE Prechecking_Id = :pid)
                WHERE Prechecking_Id = :pid
            """), {"pid": prechecking_id})

        _save_shareholders(prechecking_id, shareholders)

        s3_to_delete = _finalize_create_documents(
            prechecking_id, apless, username, directors, wna_board, body.get("carried_documents"),
            shareholders,
        )

        existing_approval = db.session.execute(
            text("SELECT Id FROM DocumentApproval WITH(NOLOCK) WHERE DocumentNumber = :pid"),
            {"pid": prechecking_id},
        ).fetchone()

        if not existing_approval:
            db.session.execute(text("""
                INSERT INTO DocumentApproval
                    (ApprovalFormId, DocumentNumber, Title, Progress,
                     LastApprovalActionCode, LastActionBy, LastActionDate,
                     CurrentApprover, DocumentStatusCode, CreatedBy, CreatedDate)
                VALUES
                    (:form_id, :pid, :title, 50,
                     'draft', :username, GETDATE(),
                     :approver, 'draft', :username, GETDATE())
            """), {
                "form_id":  approval_form_id,
                "pid":      prechecking_id,
                "title":    f"CAM Request - {prechecking_id}",
                "username": username,
                "approver": f"({username})",
            })
            doc_appr_row = db.session.execute(
                text("SELECT Id FROM DocumentApproval WITH(NOLOCK) WHERE DocumentNumber=:pid"),
                {"pid": prechecking_id},
            ).fetchone()
            doc_appr_id = doc_appr_row.Id if doc_appr_row else 0
        else:
            doc_appr_id = existing_approval.Id
            db.session.execute(text("""
                UPDATE DocumentApproval SET
                    LastApprovalActionCode = 'draft',
                    LastActionBy = :username,
                    LastActionDate = GETDATE(),
                    DocumentStatusCode = 'draft'
                WHERE Id = :id
            """), {"username": username, "id": doc_appr_id})

        db.session.execute(text("""
            INSERT INTO DocumentApprovalHistory
                (DocumentApprovalId, ApprovalActionCode, Remarks, CreatedBy, CreatedDate)
            VALUES
                (:appr_id, 'draft', :remarks, :username, GETDATE())
        """), {
            "appr_id":  doc_appr_id,
            "remarks":  f"CMO {username} submitted Prechecking Request No. {prechecking_id}",
            "username": username,
        })

        db.session.commit()
        _delete_s3_keys(s3_to_delete)
        return jsonify({"success": True, "prechecking_id": prechecking_id, "apless": apless,
                        "documents_failed": []})

    except CorpCarryError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_prechecking_guarantor_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_guarantor_corporate_bp.route("/upload-document-guarantor-corporate", methods=["POST"])
@login_required
def upload_document_guarantor_corporate():

    username       = _username()
    apless         = request.form.get("apless", "")
    prechecking_id = request.form.get("prechecking_id", "")
    document_type  = request.form.get("document_type", "")
    cust_type      = request.form.get("cust_type", "PT")
    lessee_type    = request.form.get("lessee_type", "")

    organization_type = _guarantor_org_type_for(lessee_type)

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    f          = request.files["file"]
    original   = f.filename or "upload"
    file_bytes = f.read()

    err = _validate_file(file_bytes, original)
    if err:
        return jsonify({"success": False, "message": err}), 400

    name_prefix, doc_subfolder = _corp_guarantor_doc_meta(document_type)

    doc_name = f"{prechecking_id}{name_prefix}{original}"
    aws_key  = f"upload_doc/guarantor/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"

    content_type = mimetypes.guess_type(original)[0] or "application/octet-stream"

    try:
        existing = db.session.execute(
            text("""
                SELECT CustomerDocumentId, AWSKey, DocumentName
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid
                  AND DocumentType   = :dtype
                  AND Apless IS NOT NULL
            """),
            {"pid": prechecking_id, "dtype": document_type},
        ).fetchone()

        if existing:
            _aws_delete(existing.AWSKey)

            db.session.execute(
                text("""
                    DELETE FROM TEMP_CUSTOMER_DOCUMENT
                    WHERE CustomerDocumentId = :doc_id
                """),
                {"doc_id": existing.CustomerDocumentId},
            )

        _aws_upload(file_bytes, aws_key, content_type)

        db.session.execute(
            text("""
                INSERT INTO TEMP_CUSTOMER_DOCUMENT
                    (Apless, DocumentName, OrganizationType, NumberOfDocuments,
                     DocumentType, CreatedBy, CreatedDate, AWSKey, Prechecking_Id)
                VALUES
                    (:apless, :name, :org_type, :numb_doc,
                     :dtype, :user, GETDATE(), :aws_key, :pid)
            """),
            {
                "apless":    apless,
                "name":      doc_name,
                "org_type":  organization_type,
                "numb_doc":  "1",
                "dtype":     document_type,
                "user":      username,
                "aws_key":   aws_key,
                "pid":       prechecking_id,
            },
        )
        db.session.commit()

        b64_data = base64.b64encode(file_bytes).decode()
        orig_ext = os.path.splitext(original)[1].lower()
        return jsonify({
            "success":       True,
            "document_name": doc_name,
            "document_type": document_type,
            "aws_key":       aws_key,
            "b64": b64_data if orig_ext in (".png", ".jpg", ".jpeg") else None,
        })

    except (BotoCoreError, ClientError) as exc:
        db.session.rollback()
        current_app.logger.exception("upload_document_guarantor_corporate S3 error")
        return jsonify({"success": False, "message": f"S3 upload failed: {exc}"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document_guarantor_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_guarantor_corporate_bp.route("/documents-guarantor-corporate", methods=["GET"])
@login_required
def get_documents_guarantor_corporate():

    apless                  = request.args.get("apless", "")
    prechecking_id          = request.args.get("prechecking_id", "")
    previous_prechecking_id = request.args.get("previous_prechecking_id", "")

    prechecking_ids = [pid for pid in {prechecking_id, previous_prechecking_id} if pid]

    if not apless or not prechecking_ids:
        return jsonify([])

    try:
        placeholders = ", ".join(f":pid_{i}" for i in range(len(prechecking_ids)))
        params = {"apless": apless}
        params.update({f"pid_{i}": pid for i, pid in enumerate(prechecking_ids)})

        rows = db.session.execute(
            text(f"""
                SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Apless = :apless
                    AND Prechecking_Id IN ({placeholders})
                    AND Apless IS NOT NULL
                ORDER BY DocumentType, CreatedDate
            """),
            params,
        ).fetchall()

        docs = [
            {
                "id":       r.CustomerDocumentId,
                "name":     r.DocumentName,
                "type":     r.DocumentType,
                "key":      r.AWSKey,
                "view_url": _aws_presign(r.AWSKey, r.DocumentName) if r.AWSKey else None,
            }
            for r in rows
        ]
        return jsonify(docs)
    except Exception:
        current_app.logger.exception("get_documents_guarantor_corporate error")
        return jsonify([])

@prechecking_guarantor_corporate_bp.route("/view-document-guarantor-corporate", methods=["GET"])
@login_required
def view_document_guarantor_corporate():
   
    doc_id = request.args.get("customer_document_id")
    if not doc_id:
        return jsonify({"success": False, "message": "document id required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT AWSKey, DocumentName FROM TEMP_CUSTOMER_DOCUMENT
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if not row or not row.AWSKey:
            return jsonify({"success": False, "message": "Document not found"}), 404

        url = _aws_presign(row.AWSKey, row.DocumentName)
        return jsonify({"success": True, "view_url": url})
    except Exception:
        current_app.logger.exception("view_document_guarantor_corporate error")
        return jsonify({"success": False, "message": "Could not generate view link"}), 500

@prechecking_guarantor_corporate_bp.route("/delete-document-guarantor-corporate", methods=["POST"])
@login_required
def delete_document_guarantor_corporate():

    body   = request.get_json(force=True) or {}
    doc_id = body.get("customer_document_id")
    pid    = (body.get("prechecking_id") or "").strip()
    nik    = (body.get("nik") or "").strip()

    if not doc_id:
        return jsonify({"success": False, "message": "document id required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT AWSKey, DocumentType FROM TEMP_CUSTOMER_DOCUMENT
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if row and row.AWSKey:
            _aws_delete(row.AWSKey)

        db.session.execute(
            text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
            {"id": doc_id},
        )

        if row and pid and nik and _is_ocr_doc_type(row.DocumentType):
            _cleanup_ocr_for_nik(pid, nik)

        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_document_guarantor_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_guarantor_corporate_bp.route("/delete-documents-by-type-guarantor-corporate", methods=["POST"])
@login_required
def delete_documents_by_type_guarantor_corporate():
  
    body           = request.get_json(force=True) or {}
    prechecking_id = (body.get("prechecking_id") or "").strip()
    document_type  = (body.get("document_type") or "").strip()
    nik            = (body.get("nik") or "").strip()

    if not prechecking_id or not document_type:
        return jsonify({"success": False, "message": "prechecking_id and document_type are required"}), 400

    try:
        rows = db.session.execute(
            text("""
                SELECT CustomerDocumentId, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid AND DocumentType = :dtype
            """),
            {"pid": prechecking_id, "dtype": document_type},
        ).fetchall()

        for r in rows:
            if r.AWSKey:
                _aws_delete(r.AWSKey)

        db.session.execute(
            text("""
                DELETE FROM TEMP_CUSTOMER_DOCUMENT
                WHERE Prechecking_Id = :pid AND DocumentType = :dtype
            """),
            {"pid": prechecking_id, "dtype": document_type},
        )

        if nik and _is_ocr_doc_type(document_type):
            _cleanup_ocr_for_nik(prechecking_id, nik)

        db.session.commit()
        return jsonify({"success": True, "deleted_count": len(rows)})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_documents_by_type_guarantor_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

_WNA_ID_TYPES = ("KITAS", "KITAP")
_MARRIED_LABELS = {
    "S": "BELUM KAWIN", "M": "KAWIN", "O": "KAWIN BELUM TERCATAT",
    "D": "CERAI", "P": "PERJANJIAN PRANIKAH",
}
_NIK_RE = re.compile(r"^\d{16}$")
_RTRW_RE = re.compile(r"^\d{3}$")
_DOB_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")

_DIR_FIELDS = [
    ("id_card_no",     "NIK",               "NIK",               True),
    ("name",           "Nama",              "Nama",              True),
    ("pob",            "Tempat_Lahir",      "Tempat Lahir",      True),
    ("dob",            "Tgl_Lahir",         "Tanggal Lahir",     True),
    ("gender",         "Jenis_Kelamin",     "Jenis Kelamin",     True),
    ("blood_type",     "Golongan_Darah",    "Golongan Darah",    False),
    ("address",        "Alamat",            "Alamat",            True),
    ("rt",             "RT",                "RT",                True),
    ("rw",             "RW",                "RW",                True),
    ("subdistrict",    "Kelurahan",         "Kelurahan/Desa",    True),
    ("district",       "Kecamatan",         "Kecamatan",         True),
    ("city",           "Kota",              "Kota/Kabupaten",    True),
    ("province",       "Provinsi",          "Provinsi",          True),
    ("religion",       "Agama",             "Agama",             False),
    ("job",            "Pekerjaan",         "Pekerjaan",         True),
    ("marital_status", "Status_Perkawinan", "Status Perkawinan", True),
]
_DIR_COL = {f[0]: f[1] for f in _DIR_FIELDS}
_DIR_LABEL = {f[0]: f[2] for f in _DIR_FIELDS}
_DIR_DUK_KEYS = [f[0] for f in _DIR_FIELDS if f[3]]
_DIR_REQUIRED = [f[0] for f in _DIR_FIELDS if f[0] not in ("blood_type", "religion")]
_DIR_PREFIX = "corp-guarantor-ocr-ktp_"
_WNA_PREFIX = "wna-corp-guarantor-board_"

def _s(value) -> str:
    return "" if value is None else str(value).strip()

def _token(value) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", _s(value))

def _bit(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if _s(value) in ("True", "true", "1") else 0

def _carro(value) -> int:
    return 1 if _s(value) in ("1", "True", "true") else 0


def _marital_code(value) -> str:
    v = _s(value).upper()
    if v in _MARRIED_LABELS:
        return v
    return _GUARANTOR_MARITAL_MAP.get(v, "")

def _dob_to_sql(value):
    v = _s(value)
    if not _DOB_RE.match(v):
        return None
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def _norm_wna_id_type(value) -> str:
    v = _s(value).upper()
    return v if v in _WNA_ID_TYPES else "KITAS"

def _ocr_for_of(check_for: str) -> str:
    return "G"

def _fetch_board(prechecking_id: str, ocr_for: str) -> list:
    rate_cols = ", ".join(f"r.{c} AS r_{c}" for c in _DIR_COL.values())
    duk_cols = ", ".join(f"d.{_DIR_COL[k]} AS d_{_DIR_COL[k]}" for k in _DIR_DUK_KEYS)
    ocr_cols = ", ".join(f"o.{c}" for c in _DIR_COL.values() if c != "Tgl_Lahir")
    rows = db.session.execute(text(f"""
        SELECT o.Id, o.Citizen, o.Id_Type, o.Kewarnegaraan, o.Foto, o.Tanda_Tangan,
               FORMAT(o.Tgl_Lahir, 'dd-MM-yyyy') AS Tgl_Lahir, {ocr_cols},
               r.Id AS r_Id, r.Kewarnegaraan AS r_Kewarnegaraan, {rate_cols},
               d.Id AS d_Id, {duk_cols}
        FROM TEMP_CAFLESS_OCR o WITH(NOLOCK)
            LEFT JOIN TEMP_CAFLESS_OCR_Rate r WITH(NOLOCK) ON r.Id = o.Id
            LEFT JOIN TEMP_CAFLESS_OCR_Dukcapil d WITH(NOLOCK) ON d.Id = o.Id
        WHERE o.Prechecking_Id = :pid AND o.OCR_For = :ocr_for
        ORDER BY o.Id
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).mappings().all()
    return [dict(r) for r in rows]

def _fetch_shareholders(prechecking_id: str) -> list:
    rows = db.session.execute(text("""
        SELECT Id, NIK, Nama
        FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for
        ORDER BY Id
    """), {"pid": prechecking_id, "ocr_for": _SH_OCR_FOR}).mappings().all()
    return [dict(r) for r in rows]

def _is_wna(rec) -> bool:
    return _s(rec.get("Citizen")).upper() == "WNA"

def _rec_values(rec) -> dict:
    values = {k: _s(rec.get(c)) for k, c in _DIR_COL.items()}
    values["marital_status"] = _marital_code(rec.get("Status_Perkawinan"))
    return values

def _rec_conf(rec) -> dict:
    conf = {k: _strip_non_digit(_s(rec.get(f"r_{c}"))) for k, c in _DIR_COL.items()}
    conf["citizen"] = _strip_non_digit(_s(rec.get("r_Kewarnegaraan")))
    return conf

def _rec_ver(rec) -> dict:
    return {k: ("True" if _bit(rec.get(f"d_{_DIR_COL[k]}")) else "False") for k in _DIR_DUK_KEYS}

def _director_sig(values: dict, conf: dict, ver: dict, photo: str, sign: str) -> dict:
    sig = {k: _s(values.get(k)) for k in _DIR_COL}
    sig["marital_status"] = _marital_code(values.get("marital_status"))
    sig["conf"] = {k: _strip_non_digit(_s(conf.get(k))) for k in list(_DIR_COL) + ["citizen"]}
    sig["ver"] = {k: _bit(ver.get(k)) for k in _DIR_DUK_KEYS}
    sig["photo"] = photo
    sig["sign"] = sign
    return sig

def _db_director_sig(rec) -> dict:
    return _director_sig(_rec_values(rec), _rec_conf(rec), _rec_ver(rec),
                         _s(rec.get("Foto")), _s(rec.get("Tanda_Tangan")))

def _doc_types_like(prechecking_id: str, prefix: str) -> dict:
    rows = db.session.execute(text("""
        SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
        FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType LIKE :pfx
        ORDER BY CreatedDate
    """), {"pid": prechecking_id, "pfx": prefix.replace("_", "[_]") + "%"}).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r.DocumentType, []).append(r)
    return out

def _assign_doc_types(owner_tokens: list, prefix: str, available: dict):
    assigned = [[f"{prefix}{t}"] if t and f"{prefix}{t}" in available else [] for t in owner_tokens]
    used = {t for types in assigned for t in types}
    leftover = [t for t in available if t not in used]
    missing = [i for i, types in enumerate(assigned) if not types]
    if len(missing) == 1 and len(leftover) == 1:
        assigned[missing[0]] = [leftover[0]]
        leftover = []
    return assigned, leftover

@prechecking_guarantor_corporate_bp.route("/edit-guarantor-corporate", methods=["GET"])
@login_required
def get_edit_guarantor_corporate():
    apless = request.args.get("apless", "").strip()
    prechecking_id = request.args.get("prechecking_id", "").strip()

    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400

    try:
        header_row = db.session.execute(text("""
            SELECT Apless, CustomerType, LesseeName, LesseeType, NPWP, WorkAddress,
                   Check_For, Repeat_Order, Notes, Carro
            FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {"apless": apless, "pid": prechecking_id}).mappings().first()

        if not header_row:
            return jsonify({"success": False, "message": "Prechecking record not found"}), 404

        check_for = header_row["Check_For"] or ""
        if (header_row["CustomerType"] or "") != "PT":
            return jsonify({"success": False, "message": "This prechecking record is not a corporate (PT) record"}), 400
        if check_for != "G":
            return jsonify({"success": False, "message": "This endpoint only serves corporate guarantor (G) records"}), 400

        last_checking_date = ""
        row = db.session.execute(text("""
            SELECT MAX(sik.CreatedDate) AS LastCheckingDate
            FROM TEMP_SIK_CHECKING_DOCUMENT sik WITH(NOLOCK)
                INNER JOIN TEMP_CAFLESS tc WITH(NOLOCK) ON tc.Prechecking_Id = sik.Prechecking_Id
            WHERE tc.FINAL_APLESS = :apless
        """), {"apless": apless}).first()
        if row and row[0]:
            last_checking_date = row[0].strftime("%d-%m-%Y %H:%M:%S")

        outstanding = 0.0
        for sql in [
            """SELECT SUM(b.OUTS_PRINC) FROM V_DataKredit a WITH(NOLOCK)
                   LEFT JOIN CLFPAY b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                       AND b.PERIOD = (SELECT ISNULL(MAX(period), 0) FROM CLFPAY
                                       WHERE DATE_PAY IS NOT NULL AND LEASE_NO = a.LEASE_NO)
               WHERE a.APLESS = :apless AND a.UPD_STAT = 'Y' AND a.EXECUTION IS NOT NULL""",
            """SELECT SUM(Net_Finance) FROM (
                   SELECT SUM(d.Net_Finance) AS Net_Finance FROM CLFCONT_DATA a WITH(NOLOCK)
                       INNER JOIN MCMOCAMCOMPLETELIST b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                       INNER JOIN CAFLESS c WITH(NOLOCK) ON a.LESSEE_NO = c.lessee_no
                       INNER JOIN V_NetFinance d ON a.LEASE_NO = d.LEASE_NO
                   WHERE EXECUTION IS NULL AND b.AdmSts = 1 AND apless = :apless
                   UNION ALL
                   SELECT SUM(d.Net_Finance) AS Net_Finance FROM MCMOCAMCOMPLETELIST a WITH(NOLOCK)
                       INNER JOIN cafcont b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                       INNER JOIN V_NetFinance d ON a.APPL_NO = d.APPL_NO
                   WHERE b.DateTrans IS NULL AND a.AdmSts = 1 AND apless = :apless
               ) t""",
        ]:
            try:
                r = db.session.execute(text(sql), {"apless": apless}).first()
                if r and r[0]:
                    outstanding += float(r[0])
            except Exception:
                current_app.logger.exception("outstanding calc failed")

        board = _fetch_board(prechecking_id, _ocr_for_of(check_for))
        wni_recs = [r for r in board if not _is_wna(r)]
        wna_recs = [r for r in board if _is_wna(r)]

        dir_docs = _doc_types_like(prechecking_id, _DIR_PREFIX)
        wna_docs = _doc_types_like(prechecking_id, _WNA_PREFIX)
        dir_types, dir_left = _assign_doc_types([_token(r.get("NIK")) for r in wni_recs], _DIR_PREFIX, dir_docs)
        wna_types, wna_left = _assign_doc_types([_token(r.get("NIK")) for r in wna_recs], _WNA_PREFIX, wna_docs)

        directors = []
        for rec, types in zip(wni_recs, dir_types):
            ver = _rec_ver(rec)
            checked = rec.get("d_Id") is not None
            directors.append({
                "id": rec["Id"],
                "values": _rec_values(rec),
                "confidence": _rec_conf(rec),
                "verified": ver,
                "dukcapil": {
                    "checked": checked,
                    "status": all(v == "True" for v in ver.values()) if checked else None,
                    "reason": "",
                },
                "id_type": "KTP",
                "photo": _s(rec.get("Foto")),
                "signature": _s(rec.get("Tanda_Tangan")),
                "doc_types": types,
            })

        wna_board = [{
            "id": rec["Id"],
            "name": _s(rec.get("Nama")),
            "id_card_no": _s(rec.get("NIK")),
            "id_type": _norm_wna_id_type(rec.get("Id_Type")),
            "doc_types": types,
        } for rec, types in zip(wna_recs, wna_types)]

        unassigned = []
        for types_map, left in ((dir_docs, dir_left), (wna_docs, wna_left)):
            for t in left:
                for r in types_map[t]:
                    unassigned.append({"id": r.CustomerDocumentId, "name": r.DocumentName, "type": t, "key": r.AWSKey})

        shareholders = [{
            "id": r["Id"],
            "name": _s(r.get("Nama")),
            "npwp_no": _s(r.get("NIK")),
            "id_type": _SH_ID_TYPE,
            "doc_types": [f"{_SH_PREFIX}{_token(r.get('NIK'))}"] if _token(r.get("NIK")) else [],
        } for r in _fetch_shareholders(prechecking_id)]

        sik_rows = db.session.execute(text("""
            SELECT Subject, CreditBureau, Status, Score, Grade
            FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
            WHERE Prechecking_Id = :pid
        """), {"pid": prechecking_id}).mappings().all()
        subject_label = {"C": "Customer", "G": "Guarantor"}
        sik = [{
            "subject": subject_label.get(r["Subject"], "Pengurus"),
            "credit_bureau": r["CreditBureau"] or "",
            "status": r["Status"] or "",
            "score": str(r["Score"] or ""),
            "grade": r["Grade"] or "",
        } for r in sik_rows]

        return jsonify({
            "success": True,
            "apless": apless,
            "prechecking_id": prechecking_id,
            "check_for": check_for,
            "lessee_type": header_row["LesseeType"] or "",
            "corp_name": header_row["LesseeName"] or "",
            "corp_address": header_row["WorkAddress"] or "",
            "corp_npwp_no": header_row["NPWP"] or "",
            "note": header_row["Notes"] or "",
            "is_carro": str(_carro(header_row["Carro"])),
            "repeat_order": "1" if str(header_row["Repeat_Order"]) in ("1", "True") else "0",
            "last_checking_date": last_checking_date,
            "outstanding": outstanding,
            "directors": directors,
            "wna_board": wna_board,
            "shareholders": shareholders,
            "unassigned_documents": unassigned,
            "sik": sik,
        })

    except Exception:
        current_app.logger.exception("get_edit_guarantor_corporate error")
        return jsonify({"success": False, "message": "Failed to load prechecking data"}), 500

def _validate_director(i: int, d: dict, errors: dict) -> None:
    label = f"Pengurus #{i + 1}"
    for k in _DIR_REQUIRED:
        if not _s(d.get(k)):
            errors[f"director_{i}_{k}"] = f"{label}: {_DIR_LABEL[k]} is required"
    nik = _s(d.get("id_card_no"))
    if nik and not _NIK_RE.match(nik):
        errors[f"director_{i}_id_card_no"] = f"{label}: NIK must be 16 digits (numbers only)"
    dob = _s(d.get("dob"))
    if dob:
        parsed = _dob_to_sql(dob)
        if not parsed:
            errors[f"director_{i}_dob"] = f"{label}: Tanggal Lahir must be a valid date in dd-mm-yyyy format"
        elif parsed > datetime.now().strftime("%Y-%m-%d"):
            errors[f"director_{i}_dob"] = f"{label}: Tanggal Lahir cannot be in the future"
    for k in ("rt", "rw"):
        v = _s(d.get(k))
        if v and not _RTRW_RE.match(v):
            errors[f"director_{i}_{k}"] = f"{label}: {_DIR_LABEL[k]} must be a 3-digit number (e.g. 003)"
    if _s(d.get("marital_status")) and not _marital_code(d.get("marital_status")):
        errors[f"director_{i}_marital_status"] = f"{label}: Status Perkawinan is not valid"

def _delete_ocr_ids(ids) -> None:
    for ocr_id in ids:
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Dukcapil WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Rate WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR WHERE Id = :id"), {"id": ocr_id})

def _save_director(prechecking_id: str, ocr_for: str, ocr_id, d: dict) -> int:
    params = {k: _s(d.get(k)) for k in _DIR_COL}
    params["dob"] = _dob_to_sql(d.get("dob"))
    params["marital_status"] = _marital_code(d.get("marital_status"))
    params.update({"pid": prechecking_id, "ocr_for": ocr_for})

    photo = _s(d.get("photo")) or None
    sign = _s(d.get("signature")) or None
    params.update({"photo": photo, "sign": sign})

    if ocr_id:
        media_set = ("Foto = :photo, " if photo is not None else "") + \
                    ("Tanda_Tangan = :sign, " if sign is not None else "")
        db.session.execute(text(f"""
            UPDATE TEMP_CAFLESS_OCR SET
                Citizen = 'WNI', Id_Type = 'KTP', Kewarnegaraan = 'WNI',
                NIK = :id_card_no, Nama = :name, Tempat_Lahir = :pob, Tgl_Lahir = :dob,
                Jenis_Kelamin = :gender, Golongan_Darah = :blood_type, Alamat = :address,
                RT = :rt, RW = :rw, Kelurahan = :subdistrict, Kecamatan = :district,
                Kota = :city, Provinsi = :province, Agama = :religion, Pekerjaan = :job,
                Status_Perkawinan = :marital_status, {media_set}
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
                 :id_card_no, :name, :pob, :dob, :gender, :blood_type, :address,
                 :rt, :rw, :subdistrict, :district, :city, :province, :religion, :job,
                 :marital_status, :photo, :sign, GETDATE())
        """), params).fetchone().Id

    conf = d.get("conf") or {}
    rate = {k: _strip_non_digit(_s(conf.get(k))) for k in _DIR_COL}
    rate.update({"citizen": _strip_non_digit(_s(conf.get("citizen"))), "id": ocr_id})
    rate_set = """NIK = :id_card_no, Nama = :name, Tempat_Lahir = :pob, Tgl_Lahir = :dob,
                  Jenis_Kelamin = :gender, Golongan_Darah = :blood_type, Alamat = :address,
                  RT = :rt, RW = :rw, Kelurahan = :subdistrict, Kecamatan = :district,
                  Kota = :city, Provinsi = :province, Agama = :religion, Pekerjaan = :job,
                  Status_Perkawinan = :marital_status, Kewarnegaraan = :citizen"""
    if db.session.execute(text("SELECT 1 FROM TEMP_CAFLESS_OCR_Rate WITH(NOLOCK) WHERE Id = :id"), {"id": ocr_id}).fetchone():
        db.session.execute(text(f"UPDATE TEMP_CAFLESS_OCR_Rate SET {rate_set} WHERE Id = :id"), rate)
    else:
        db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR_Rate
                (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat,
                 RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                 Status_Perkawinan, Kewarnegaraan)
            VALUES
                (:id, :id_card_no, :name, :pob, :dob, :gender, :blood_type, :address,
                 :rt, :rw, :subdistrict, :district, :city, :province, :religion, :job,
                 :marital_status, :citizen)
        """), rate)

    ver = d.get("ver") or {}
    duk = {k: _bit(ver.get(k)) for k in _DIR_DUK_KEYS}
    duk["id"] = ocr_id
    duk_set = """NIK = :id_card_no, Nama = :name, Tempat_Lahir = :pob, Tgl_Lahir = :dob,
                 Jenis_Kelamin = :gender, Alamat = :address, RT = :rt, RW = :rw,
                 Kelurahan = :subdistrict, Kecamatan = :district, Kota = :city,
                 Provinsi = :province, Pekerjaan = :job, Status_Perkawinan = :marital_status"""
    if db.session.execute(text("SELECT 1 FROM TEMP_CAFLESS_OCR_Dukcapil WITH(NOLOCK) WHERE Id = :id"), {"id": ocr_id}).fetchone():
        db.session.execute(text(f"UPDATE TEMP_CAFLESS_OCR_Dukcapil SET {duk_set} WHERE Id = :id"), duk)
    else:
        db.session.execute(text("""
            INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Alamat, RT, RW,
                 Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan, Status_Perkawinan)
            VALUES
                (:id, :id_card_no, :name, :pob, :dob, :gender, :address, :rt, :rw,
                 :subdistrict, :district, :city, :province, :job, :marital_status)
        """), duk)
    return ocr_id

def _save_wna(prechecking_id: str, ocr_for: str, ocr_id, w: dict) -> int:
    params = {"pid": prechecking_id, "ocr_for": ocr_for, "name": _s(w.get("name")),
              "nik": _s(w.get("id_card_no")), "id_type": _norm_wna_id_type(w.get("id_type"))}
    if ocr_id:
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS_OCR SET
                Citizen = 'WNA', Kewarnegaraan = 'WNA', Id_Type = :id_type,
                Nama = :name, NIK = :nik, UpdatedDate = GETDATE()
            WHERE Id = :id
        """), {**params, "id": ocr_id})
        return ocr_id
    return db.session.execute(text("""
        INSERT INTO TEMP_CAFLESS_OCR
            (Prechecking_Id, OCR_For, Citizen, Kewarnegaraan, Id_Type, Nama, NIK, UpdatedDate)
        OUTPUT INSERTED.Id
        VALUES (:pid, :ocr_for, 'WNA', 'WNA', :id_type, :name, :nik, GETDATE())
    """), params).fetchone().Id


def _save_shareholder(prechecking_id: str, ocr_id, sh: dict) -> int:
    params = {"pid": prechecking_id, "ocr_for": _SH_OCR_FOR, "id_type": _SH_ID_TYPE,
              "name": _s(sh.get("name")), "npwp": _s(sh.get("npwp_no"))}
    if ocr_id:
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS_OCR SET
                Id_Type = :id_type, Nama = :name, NIK = :npwp, UpdatedDate = GETDATE()
            WHERE Id = :id AND Prechecking_Id = :pid AND OCR_For = :ocr_for
        """), {**params, "id": ocr_id})
        return ocr_id
    return db.session.execute(text("""
        INSERT INTO TEMP_CAFLESS_OCR
            (Prechecking_Id, OCR_For, Citizen, Id_Type, Nama, NIK, UpdatedDate)
        OUTPUT INSERTED.Id
        VALUES (:pid, :ocr_for, '', :id_type, :name, :npwp, GETDATE())
    """), params).fetchone().Id

def _docs_of_types(prechecking_id: str, types) -> list:
    types = [t for t in dict.fromkeys(types) if t]
    if not types:
        return []
    ph = ", ".join(f":t{i}" for i in range(len(types)))
    return db.session.execute(text(f"""
        SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey, OrganizationType
        FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType IN ({ph})
    """), {"pid": prechecking_id, **{f"t{i}": t for i, t in enumerate(types)}}).fetchall()

def _delete_doc_rows(rows) -> list:
    for r in rows:
        db.session.execute(text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
                           {"id": r.CustomerDocumentId})
    return [r.AWSKey for r in rows if r.AWSKey]

def _retype_docs(prechecking_id: str, old_type: str, new_type: str) -> None:
    if old_type and new_type and old_type != new_type:
        db.session.execute(text("""
            UPDATE TEMP_CUSTOMER_DOCUMENT SET DocumentType = :new
            WHERE Prechecking_Id = :pid AND DocumentType = :old
        """), {"pid": prechecking_id, "old": old_type, "new": new_type})
class CorpCarryError(Exception):
    pass

def _copy_doc_into(prechecking_id: str, apless: str, target_type: str, doc_id, username: str) -> str:
    src = db.session.execute(text("""
        SELECT DocumentName, AWSKey, OrganizationType, Prechecking_Id
        FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK) WHERE CustomerDocumentId = :id
    """), {"id": doc_id}).fetchone()
    if not src or not src.AWSKey:
        raise CorpCarryError("Source document not found")
    name_prefix, subfolder = _corp_guarantor_doc_meta(target_type)
    source_name = re.sub(r"^[^-]*-[A-Z0-9_]+-", "", src.DocumentName or "", count=1) or "document"
    doc_name = f"{prechecking_id}{name_prefix}{source_name}"
    aws_key = f"upload_doc/guarantor/{apless}/{prechecking_id}/{subfolder}/{doc_name}"
    try:
        copied = copy_object(src.AWSKey, aws_key)
    except (BotoCoreError, ClientError):
        current_app.logger.exception("corporate carry-over copy failed for %s", src.AWSKey)
        copied = False
    if not copied:
        raise CorpCarryError("Failed to copy a carried document. Please upload it manually.")
    db.session.execute(text("""
        INSERT INTO TEMP_CUSTOMER_DOCUMENT
            (Apless, DocumentName, OrganizationType, NumberOfDocuments,
             DocumentType, CreatedBy, CreatedDate, AWSKey, Prechecking_Id)
        VALUES (:apless, :name, :org, '1', :dt, :user, GETDATE(), :key, :pid)
    """), {"apless": apless, "name": doc_name, "org": src.OrganizationType or "PT",
           "dt": target_type, "user": username, "key": aws_key, "pid": prechecking_id})
    return aws_key

def _delete_s3_keys(keys) -> None:
    for key in dict.fromkeys(keys):
        try:
            _aws_delete(key)
        except Exception:
            current_app.logger.exception("S3 delete failed for %s", key)

def _finalize_member_docs(prechecking_id: str, apless: str, prefix: str, target_token: str,
                          staging_token: str, existing_types, carried_ids, username: str) -> list:
    
    target = f"{prefix}{target_token}"
    staging = f"{prefix}{staging_token}" if staging_token else ""
    existing = [t for t in (existing_types or []) if isinstance(t, str) and t.startswith(prefix)]
    old_types = [t for t in dict.fromkeys(existing + [target]) if t != staging]

    staging_rows = _docs_of_types(prechecking_id, [staging]) if staging and staging != target else []
    if staging_rows:
        stale = _delete_doc_rows(_docs_of_types(prechecking_id, old_types))
        _retype_docs(prechecking_id, staging, target)
        new_keys = {r.AWSKey for r in staging_rows}
        return [k for k in stale if k not in new_keys]

    carried = [c for c in (carried_ids or []) if c]
    if carried:
        old_rows = _docs_of_types(prechecking_id, old_types)
        new_key = _copy_doc_into(prechecking_id, apless, target, carried[0], username)
        stale = _delete_doc_rows(old_rows)
        return [k for k in stale if k != new_key]

    for t in existing:
        _retype_docs(prechecking_id, t, target)
    return []

@prechecking_guarantor_corporate_bp.route("/update-guarantor-corporate", methods=["POST"])
@login_required
def update_guarantor_corporate():
    username = _username()
    body = request.get_json(silent=True) or {}
    apless = _s(body.get("apless"))
    prechecking_id = _s(body.get("prechecking_id"))
    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400

    header = db.session.execute(text("""
        SELECT CustomerType, Check_For, LesseeName, WorkAddress, Notes, Carro
        FROM TEMP_CAFLESS WITH(NOLOCK)
        WHERE Apless = :apless AND Prechecking_Id = :pid
    """), {"apless": apless, "pid": prechecking_id}).mappings().first()
    if not header:
        return jsonify({"success": False, "message": "Prechecking record not found"}), 404
    if (header["CustomerType"] or "") != "PT":
        return jsonify({"success": False, "message": "This prechecking record is not a corporate (PT) record"}), 400
    if (header["Check_For"] or "") != "G":
        return jsonify({"success": False, "message": "This endpoint only handles corporate guarantor (G) records"}), 400

    ocr_for = _ocr_for_of(header["Check_For"] or "G")
    board = _fetch_board(prechecking_id, ocr_for)
    db_by_id = {r["Id"]: r for r in board}

    corp_name = _s(body.get("corp_name"))
    corp_address = _s(body.get("corp_address"))
    note = _s(body.get("note"))
    carro = _carro(body.get("is_carro"))
    directors = [d for d in (body.get("directors") or []) if isinstance(d, dict)]
    wna_board = [w for w in (body.get("wna_board") or []) if isinstance(w, dict)]
    shareholders = [x for x in (body.get("shareholders") or []) if isinstance(x, dict)]
    sh_board = _fetch_shareholders(prechecking_id)
    sh_by_id = {r["Id"]: r for r in sh_board}

    errors: dict = {}
    if not corp_name:
        errors["corp_name"] = "Nama is required"
    if not corp_address:
        errors["corp_address"] = "Alamat is required"
    if not directors:
        errors["directors"] = "At least one Pengurus (WNI) is required"

    seen_ids: dict = {}
    for i, d in enumerate(directors):
        _validate_director(i, d, errors)
        nik = _s(d.get("id_card_no"))
        rec = db_by_id.get(d.get("id"))
        if d.get("id") and (rec is None or _is_wna(rec)):
            errors[f"director_{i}_id"] = f"Pengurus #{i + 1} no longer exists. Reload the page."
            continue
        if rec is not None and nik != _s(rec.get("NIK")):
            errors[f"director_{i}_id_card_no"] = f"Pengurus #{i + 1}: NIK cannot be changed on edit"
        if nik:
            if nik in seen_ids:
                errors[f"director_{i}_id_card_no"] = f"Pengurus #{i + 1}: NIK is already used by {seen_ids[nik]}"
            seen_ids[nik] = f"Pengurus #{i + 1}"

        changed = rec is None or _db_director_sig(rec) != _director_sig(
            d, d.get("conf") or {}, d.get("ver") or {},
            _s(d.get("photo")) or _s(rec.get("Foto")), _s(d.get("signature")) or _s(rec.get("Tanda_Tangan")))
        staged = _token(d.get("doc_token"))
        has_staging = bool(staged and _docs_of_types(prechecking_id, [f"{_DIR_PREFIX}{staged}"]))
        has_carry = bool([c for c in (d.get("carried_document_ids") or []) if c])
        if changed or has_staging or has_carry:
            has_file = has_staging or has_carry or bool(_docs_of_types(
                prechecking_id,
                [t for t in (d.get("doc_types") or []) if _s(t).startswith(_DIR_PREFIX)]
                + ([f"{_DIR_PREFIX}{_token(nik)}"] if nik else []),
            ))
            if not has_file:
                errors[f"director_{i}_document"] = f"Pengurus #{i + 1}: KTP file is required"
            if not (d.get("dukcapil") or {}).get("checked"):
                errors[f"director_{i}_dukcapil"] = f"Pengurus #{i + 1}: verify the KTP data with Dukcapil before saving"

    for i, w in enumerate(wna_board):
        label = f"Pengurus WNA #{i + 1}"
        id_no = _s(w.get("id_card_no"))
        id_type = _s(w.get("id_type")).upper()
        rec = db_by_id.get(w.get("id"))
        if w.get("id") and (rec is None or not _is_wna(rec)):
            errors[f"wna_{i}_id"] = f"{label} no longer exists. Reload the page."
            continue
        if not _s(w.get("name")):
            errors[f"wna_{i}_name"] = f"{label}: Nama is required"
        if not id_no:
            errors[f"wna_{i}_id_card_no"] = f"{label}: ID Card No. is required"
        elif not _token(id_no):
            errors[f"wna_{i}_id_card_no"] = f"{label}: ID Card No. must contain letters or numbers"
        elif id_no in seen_ids:
            errors[f"wna_{i}_id_card_no"] = f"{label}: ID Card No. is already used by {seen_ids[id_no]}"
        else:
            seen_ids[id_no] = label
        if id_type not in _WNA_ID_TYPES:
            errors[f"wna_{i}_id_type"] = f"{label}: ID Type must be KITAS or KITAP"
        elif rec is not None and _norm_wna_id_type(rec.get("Id_Type")) != id_type:
            staged = _token(w.get("doc_token"))
            if not (staged and _docs_of_types(prechecking_id, [f"{_WNA_PREFIX}{staged}"])):
                errors[f"wna_{i}_document"] = f"{label}: upload the {id_type} file when changing ID Type"

    active_shareholders: list = []
    seen_npwp: dict = {}
    for i, sh in enumerate(shareholders):
        label = f"Shareholder #{i + 1}"
        sh_rec = sh_by_id.get(sh.get("id"))
        if sh.get("id") and sh_rec is None:
            errors[f"shareholder_{i}_id"] = f"{label} no longer exists. Reload the page."
            continue
        sh_name = _s(sh.get("name"))
        sh_npwp = _s(sh.get("npwp_no"))
        sh_staged = _token(sh.get("doc_token"))
        has_staged = bool(sh_staged and _docs_of_types(prechecking_id, [f"{_SH_PREFIX}{sh_staged}"]))
        if not sh.get("id") and not sh_name and not sh_npwp and not has_staged:
            continue
        if not sh_name:
            errors[f"shareholder_{i}_name"] = f"{label}: Name is required"
        elif len(sh_name) > _SH_NAME_MAX:
            errors[f"shareholder_{i}_name"] = f"{label}: Name must be at most {_SH_NAME_MAX} characters"
        if not sh_npwp:
            errors[f"shareholder_{i}_npwp_no"] = f"{label}: NPWP No is required"
        elif not sh_npwp.isdigit() or len(sh_npwp) > _SH_NPWP_MAX:
            errors[f"shareholder_{i}_npwp_no"] = f"{label}: NPWP No must be numbers only, max {_SH_NPWP_MAX} digits"
        elif sh_npwp in seen_npwp:
            errors[f"shareholder_{i}_npwp_no"] = f"{label}: NPWP No is already used by {seen_npwp[sh_npwp]}"
        else:
            seen_npwp[sh_npwp] = label
        active_shareholders.append(sh)

    if errors:
        return jsonify({"success": False, "errors": errors, "message": "\n".join(errors.values())}), 422

    kept_ids = {d.get("id") for d in directors if d.get("id")} | {w.get("id") for w in wna_board if w.get("id")}
    removed = [r for r in board if r["Id"] not in kept_ids]
    header_changed = (
        corp_name != _s(header["LesseeName"]) or corp_address != _s(header["WorkAddress"])
        or note != _s(header["Notes"]) or carro != _carro(header["Carro"])
    )

    def director_changed(d):
        rec = db_by_id.get(d.get("id"))
        if rec is None:
            return True
        if _token(d.get("doc_token")) and _docs_of_types(prechecking_id, [f"{_DIR_PREFIX}{_token(d.get('doc_token'))}"]):
            return True
        if [c for c in (d.get("carried_document_ids") or []) if c]:
            return True
        return _db_director_sig(rec) != _director_sig(
            d, d.get("conf") or {}, d.get("ver") or {},
            _s(d.get("photo")) or _s(rec.get("Foto")), _s(d.get("signature")) or _s(rec.get("Tanda_Tangan")))

    def wna_changed(w):
        rec = db_by_id.get(w.get("id"))
        if rec is None:
            return True
        if _token(w.get("doc_token")) and _docs_of_types(prechecking_id, [f"{_WNA_PREFIX}{_token(w.get('doc_token'))}"]):
            return True
        return (_s(w.get("name")), _s(w.get("id_card_no")), _norm_wna_id_type(w.get("id_type"))) != \
               (_s(rec.get("Nama")), _s(rec.get("NIK")), _norm_wna_id_type(rec.get("Id_Type")))

    kept_sh_ids = {x.get("id") for x in active_shareholders if x.get("id")}
    removed_sh = [r for r in sh_board if r["Id"] not in kept_sh_ids]

    def shareholder_changed(x):
        rec = sh_by_id.get(x.get("id"))
        if rec is None:
            return True
        staged = _token(x.get("doc_token"))
        if staged and _docs_of_types(prechecking_id, [f"{_SH_PREFIX}{staged}"]):
            return True
        return (_s(x.get("name")), _s(x.get("npwp_no"))) != (_s(rec.get("Nama")), _s(rec.get("NIK")))

    changed_dirs = [d for d in directors if director_changed(d)]
    changed_wna = [w for w in wna_board if wna_changed(w)]
    changed_sh = [x for x in active_shareholders if shareholder_changed(x)]
    if not (header_changed or removed or changed_dirs or changed_wna or removed_sh or changed_sh):
        return jsonify({"success": True, "no_changes": True, "message": "No data changes"})

    s3_to_delete: list = []
    try:
        db.session.execute(text("""
            UPDATE TEMP_CAFLESS
            SET LesseeName = :name, WorkAddress = :addr, Notes = :note, Carro = :carro
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {"name": corp_name, "addr": corp_address, "note": note, "carro": carro,
               "apless": apless, "pid": prechecking_id})

        for r in removed:
            prefix = _WNA_PREFIX if _is_wna(r) else _DIR_PREFIX
            s3_to_delete += _delete_doc_rows(_docs_of_types(prechecking_id, [f"{prefix}{_token(r.get('NIK'))}"]))
        _delete_ocr_ids([r["Id"] for r in removed])

        for d in changed_dirs:
            _save_director(prechecking_id, ocr_for, d.get("id"), d)
            s3_to_delete += _finalize_member_docs(
                prechecking_id, apless, _DIR_PREFIX, _token(d.get("id_card_no")),
                _token(d.get("doc_token")), d.get("doc_types"), d.get("carried_document_ids"), username)

        for w in changed_wna:
            _save_wna(prechecking_id, ocr_for, w.get("id"), w)
            rec = db_by_id.get(w.get("id"))
            existing = list(w.get("doc_types") or [])
            if rec is not None:
                existing.append(f"{_WNA_PREFIX}{_token(rec.get('NIK'))}")
            s3_to_delete += _finalize_member_docs(
                prechecking_id, apless, _WNA_PREFIX, _token(w.get("id_card_no")),
                _token(w.get("doc_token")), existing, None, username)

        for r in removed_sh:
            s3_to_delete += _delete_doc_rows(_docs_of_types(prechecking_id, [f"{_SH_PREFIX}{_token(r.get('NIK'))}"]))
        _delete_ocr_ids([r["Id"] for r in removed_sh])

        for x in changed_sh:
            _save_shareholder(prechecking_id, x.get("id"), x)
            rec = sh_by_id.get(x.get("id"))
            existing = list(x.get("doc_types") or [])
            if rec is not None:
                existing.append(f"{_SH_PREFIX}{_token(rec.get('NIK'))}")
            existing = list(dict.fromkeys(existing))
            s3_to_delete += _finalize_member_docs(
                prechecking_id, apless, _SH_PREFIX, _token(x.get("npwp_no")),
                _token(x.get("doc_token")), existing, None, username)

        db.session.commit()
    except CorpCarryError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("update_guarantor_corporate error")
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500

    _delete_s3_keys(s3_to_delete)
    return jsonify({"success": True, "no_changes": False, "message": "Data updated successfully"})