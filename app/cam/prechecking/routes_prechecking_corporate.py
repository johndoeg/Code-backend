from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
import base64, os, mimetypes, re
from datetime import datetime

from botocore.exceptions import BotoCoreError, ClientError

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import (
    _aws_upload, _aws_delete, _aws_presign, _validate_file,
)

from app.utils.helpers.base_format import (
    _username, _branch, _emp_id, _to_bit, _strip_non_digit, fmt_date, parse_date, as_of_date, can_edit, format_threshold, get_combo
)

prechecking_corporate_bp = Blueprint("prechecking_corporate", __name__, url_prefix="/CAM/Prechecking")

_MARITAL_MAP = {
    "BELUM KAWIN": "S", "KAWIN": "M", "KAWIN TERCATAT": "M",
    "KAWIN BELUM TERCATAT": "O", "PERJANJIAN PRANIKAH": "P",
    "CERAI HIDUP": "D", "CERAI MATI": "D",
}

def _normalize_marital(val):
    return _MARITAL_MAP.get((val or "").strip().upper(), val)

@prechecking_corporate_bp.route("/lessee-types", methods=["GET"])
@login_required
def get_lessee_types():
    try:
        rows = db.session.execute(
            text("""
                SELECT CUST_TYPE, [NAME]
                FROM MSTLESSEETYPE WITH(NOLOCK)
                WHERE LESSEE_TP = 'PT'
                ORDER BY [NAME]
            """)
        ).fetchall()
        return jsonify([{"value": r.CUST_TYPE, "label": r.NAME} for r in rows])
    except Exception:
        current_app.logger.exception("get_lessee_types error")
        return jsonify([])
    
@prechecking_corporate_bp.route("/submit-corporate", methods=["POST"])
@login_required
def submit_prechecking_corporate():

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
    check_for        = g("check_for", "C")
    corp_new_ro      = 0 if g("corp_new_ro", "New") == "New" else 1
    existing_apless  = g("existing_apless")
    nationality      = g("cust_nationality_type", "WNI")
    is_carro         = int(g("is_carro_type", "1"))
    note_pt          = g("note_prechecking_pt")

    corp_name        = g("corp_name")
    corp_address     = g("corp_address")
    corp_npwp_no     = g("corp_npwp_no")

    directors = body.get("directors") or []
    wna_board = body.get("wna_board") or []

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id is required"}), 400

    errors = {}
    if not lessee_type:
        errors["corp_lessee_type_error"] = "Company Type is required"
    if not corp_name:
        errors["corp_name_error"] = "Nama is required"
    if not corp_address:
        errors["corp_address_error"] = "Alamat is required"
    if not corp_npwp_no:
        errors["corp_npwp_no_error"] = "NPWP No is required"

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
                errors[f"corp_board_{key}_error_{i}"] = f"{label} is required"

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

        ocr_for = "P"

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

                marital = _normalize_marital(d.get("marital_status"))

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (OCR_For, Citizen, NIK, Nama, Tempat_Lahir, Tgl_Lahir,
                         Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW, Kelurahan,
                         Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                         Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan,
                         Prechecking_Id)
                    VALUES
                        (:ocr_for, :citizen, :nik, :nama, :pob, :dob,
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
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
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
                    INSERT INTO TEMP_CAFLESS_OCR (Prechecking_Id, OCR_For, Citizen, NIK, Nama)
                    VALUES (:pid, :ocr_for, 'WNA', :nik, :nama)
                """), {
                    "pid": prechecking_id, "ocr_for": ocr_for,
                    "nik": w.get("id_card_no"), "nama": w.get("name") or "",
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

                marital = _normalize_marital(d.get("marital_status"))

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        OCR_For=:ocr_for, Citizen=:citizen, Nama=:nama,
                        Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                        Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                        Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                        Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                        Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid AND NIK=:nik
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
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
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
                        WHERE Prechecking_Id=:pid AND NIK=:nik
                    """),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()

                if exists_row and exists_row.cnt == 0:
                    db.session.execute(text("""
                        INSERT INTO TEMP_CAFLESS_OCR (OCR_For, Citizen, Nama, Prechecking_Id, NIK)
                        VALUES (:ocr_for, 'WNA', :nama, :pid, :nik)
                    """), {"ocr_for": ocr_for, "nama": nama, "pid": prechecking_id, "nik": nik})
                else:
                    db.session.execute(text("""
                        UPDATE TEMP_CAFLESS_OCR SET
                            OCR_For=:ocr_for, Citizen='WNA', Nama=:nama, UpdatedDate=GETDATE()
                        WHERE Prechecking_Id=:pid AND NIK=:nik
                    """), {"ocr_for": ocr_for, "nama": nama, "pid": prechecking_id, "nik": nik})

            db.session.execute(text("""
                UPDATE TEMP_CUSTOMER_DOCUMENT
                SET OrganizationType = (SELECT LesseeType FROM TEMP_CAFLESS WHERE Prechecking_Id = :pid)
                WHERE Prechecking_Id = :pid
            """), {"pid": prechecking_id})

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
        return jsonify({"success": True, "prechecking_id": prechecking_id, "apless": apless})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_prechecking_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500
 
_CORP_DOC_META: dict = {
    "corp-npwp":              ("-CORP_NPWP-",             "DATA_DIRI/NPWP"),
    "corp-akta":              ("-CORP_AKTA-",             "DATA_DIRI/AKTA_PENDIRIAN"),
    "corp-sk-akta":           ("-CORP_SK_AKTA-",          "DATA_DIRI/SK_KEMENKUMHAM_PENDIRIAN"),
    "corp-akta-terakhir":     ("-CORP_AKTA_TERAKHIR-",    "DATA_DIRI/AKTA_PERUBAHAN"),
    "corp-sk-akta-terakhir":  ("-CORP_SK_AKTA_TERAKHIR-", "DATA_DIRI/SK_KEMENKUMHAM_PERUBAHAN"),
    "corp-ktp-akta-terakhir": ("-CORP_KTP_AKTA_TERAKHIR-","DATA_DIRI/KTP_PENGURUS"),
}

def _corp_doc_meta(document_type: str):
    if document_type in _CORP_DOC_META:
        return _CORP_DOC_META[document_type]

    m = re.match(r"^corp-ocr-ktp_([A-Za-z0-9]+)$", document_type)
    if m:
        token = m.group(1)
        return (f"-CORP_KTP-{token}", "DATA_DIRI/KTP_PENGURUS")

    m = re.match(r"^wna-corp-board_([A-Za-z0-9]+)$", document_type)
    if m:
        token = m.group(1)
        return (f"-WNA_CORP_BOARD-{token}", "DATA_DIRI/KTP_PENGURUS")

    return (f"-{document_type.upper().replace('-', '_')}-", document_type)

_ORG_TYPE_MAP = {
    "CO": "KOPERASI",
    "CV": "CV",
    "FD": "YAYASAN",
    "PT": "PT",
}

def _org_type_for(lessee_type: str) -> str:
    return _ORG_TYPE_MAP.get((lessee_type or "").upper(), "PT")

_OCR_DOC_TYPE_RE = re.compile(r"^(corp-ocr-ktp|wna-corp-board)_[A-Za-z0-9]+$")

def _is_ocr_doc_type(document_type: str) -> bool:
    return bool(_OCR_DOC_TYPE_RE.match(document_type or ""))

def _cleanup_ocr_for_nik(prechecking_id: str, nik: str) -> None:
   
    if not nik:
        return

    ocr_row = db.session.execute(
        text("""
            SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND NIK = :nik
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

@prechecking_corporate_bp.route("/upload-document-corporate", methods=["POST"])
@login_required
def upload_document_corporate():

    username       = _username()
    apless         = request.form.get("apless", "")
    prechecking_id = request.form.get("prechecking_id", "")
    document_type  = request.form.get("document_type", "")
    cust_type      = request.form.get("cust_type", "PT")
    lessee_type    = request.form.get("lessee_type", "")

    organization_type = _org_type_for(lessee_type)

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    f          = request.files["file"]
    original   = f.filename or "upload"
    file_bytes = f.read()

    err = _validate_file(file_bytes, original)
    if err:
        return jsonify({"success": False, "message": err}), 400

    name_prefix, doc_subfolder = _corp_doc_meta(document_type)

    doc_name = f"{prechecking_id}{name_prefix}{original}"
    aws_key  = f"upload_doc/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"

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
        current_app.logger.exception("upload_document_corporate S3 error")
        return jsonify({"success": False, "message": f"S3 upload failed: {exc}"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500
    
@prechecking_corporate_bp.route("/documents-corporate", methods=["GET"])
@login_required
def get_documents_corporate():

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
        current_app.logger.exception("get_documents_corporate error")
        return jsonify([])

@prechecking_corporate_bp.route("/view-document-corporate", methods=["GET"])
@login_required
def view_document_corporate():
   
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
        current_app.logger.exception("view_document_corporate error")
        return jsonify({"success": False, "message": "Could not generate view link"}), 500

@prechecking_corporate_bp.route("/delete-document-corporate", methods=["POST"])
@login_required
def delete_document_corporate():

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
        current_app.logger.exception("delete_document_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_corporate_bp.route("/delete-documents-by-type-corporate", methods=["POST"])
@login_required
def delete_documents_by_type_corporate():
   
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
        current_app.logger.exception("delete_documents_by_type_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_corporate_bp.route("/cancel-corporate", methods=["POST"])
@login_required
def cancel_prechecking_corporate():

    body           = request.get_json(force=True) or {}
    prechecking_id = (body.get("prechecking_id") or "").strip()

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id required"}), 400

    try:
        for tbl in (
            "TEMP_CAFLESS_OCR_Rate",
            "TEMP_CAFLESS_OCR",
            "TEMP_CUSTOMER_DOCUMENT",
            "TEMP_CAFLESS",
        ):
            if tbl == "TEMP_CAFLESS_OCR_Rate":
                db.session.execute(
                    text(f"""
                        DELETE r FROM {tbl} r
                        INNER JOIN TEMP_CAFLESS_OCR o ON r.Id = o.Id
                        WHERE o.Prechecking_Id = :pid
                    """),
                    {"pid": prechecking_id},
                )
            else:
                db.session.execute(
                    text(f"DELETE FROM {tbl} WHERE Prechecking_Id = :pid"),
                    {"pid": prechecking_id},
                )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("cancel_prechecking_corporate error")
        return jsonify({"success": False, "message": "Database error"}), 500

_MARITAL_DISPLAY_MAP = {
    "S": "SINGLE", "D": "DIVORCE", "M": "MARRIED", "O": "MARRIED WITHOUT CERTIFICATE",
}

def _marital_for_display(code: str) -> str:
    return _MARITAL_DISPLAY_MAP.get((code or "").strip().upper(), code)

def _ver_flag(val) -> str:
    if val is None:
        return ""
    try:
        ival = int(val)
    except (TypeError, ValueError):
        return ""
    if ival == 1:
        return "True"
    if ival == 0:
        return "False"
    return ""

@prechecking_corporate_bp.route("/edit-corporate", methods=["GET"])
@login_required
def get_edit_corporate():
    apless         = request.args.get("apless", "").strip()
    prechecking_id = request.args.get("prechecking_id", "").strip()

    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400

    try:
        header_row = db.session.execute(text("""
            SELECT Apless, CustomerType, LesseeName, LesseeType, IdCardNo, NPWP, MaritalStatus,
                   WorkAddress, Prechecking_Id, Check_For, Repeat_Order, Notes, Carro
            FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {"apless": apless, "pid": prechecking_id}).mappings().first()

        if not header_row:
            return jsonify({"success": False, "message": "Prechecking record not found"}), 404

        check_for    = header_row["Check_For"]
        customer_type = header_row["CustomerType"]
        is_corporate    = (check_for == "C" and customer_type == "PT")
        is_guarantor_pt = (check_for == "G" and customer_type == "PT")

        if not (is_corporate or is_guarantor_pt):
            return jsonify({"success": False, "message": "This prechecking record is not a corporate (PT) record"}), 400

        ocr_for = "P" if is_corporate else "G"

        last_checking_date = None
        row = db.session.execute(text("""
            SELECT MAX(sik.CreatedDate) AS LastCheckingDate
            FROM TEMP_SIK_CHECKING_DOCUMENT sik WITH(NOLOCK)
                INNER JOIN TEMP_CAFLESS tc WITH(NOLOCK) ON tc.Prechecking_Id = sik.Prechecking_Id
            WHERE tc.FINAL_APLESS = :apless
        """), {"apless": apless}).first()
        if row and row[0]:
            last_checking_date = row[0].strftime("%d-%m-%Y %H:%M:%S")

        last_disburse = 0.0
        row = db.session.execute(text("""
            SELECT SUM(b.OUTS_PRINC) as Net_Finance
            FROM V_DataKredit a WITH(NOLOCK)
                LEFT JOIN CLFPAY b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                    AND b.PERIOD = (SELECT ISNULL(MAX(period), 0)
                                    FROM CLFPAY
                                    WHERE DATE_PAY IS NOT NULL AND LEASE_NO = a.LEASE_NO)
            WHERE a.APLESS = :apless AND a.UPD_STAT = 'Y' AND a.EXECUTION IS NOT NULL
        """), {"apless": apless}).first()
        if row and row[0]:
            last_disburse += float(row[0])

        row = db.session.execute(text("""
            SELECT SUM(Net_Finance) FROM (
                SELECT SUM(d.Net_Finance) AS Net_Finance
                FROM CLFCONT_DATA a WITH(NOLOCK)
                    INNER JOIN MCMOCAMCOMPLETELIST b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                    INNER JOIN CAFLESS c WITH(NOLOCK) ON a.LESSEE_NO = c.lessee_no
                    INNER JOIN V_NetFinance d ON a.LEASE_NO = d.LEASE_NO
                WHERE EXECUTION IS NULL AND b.AdmSts = 1 AND apless = :apless
                
                UNION ALL
                
                SELECT SUM(d.Net_Finance) AS Net_Finance
                FROM MCMOCAMCOMPLETELIST a WITH(NOLOCK)
                    INNER JOIN cafcont b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                    INNER JOIN V_NetFinance d ON a.APPL_NO = d.APPL_NO
                WHERE b.DateTrans IS NULL AND a.AdmSts = 1 AND apless = :apless
            ) t
        """), {"apless": apless}).first()
        if row and row[0]:
            last_disburse += float(row[0])

        directors = []
        director_rows = db.session.execute(text("""
            SELECT Id, NIK, Nama, Tempat_Lahir,
                   FORMAT(Tgl_Lahir, 'dd-MM-yyyy') AS Tgl_Lahir,
                   Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                   Kota, Provinsi, Agama, Pekerjaan, Status_Perkawinan, Kewarnegaraan,
                   Foto, Tanda_Tangan
            FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for AND Citizen = 'WNI'
        """), {"pid": prechecking_id, "ocr_for": ocr_for}).mappings().all()

        rate_rows = {r["NIK"]: r for r in db.session.execute(text("""
            SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat,
                   RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                   Status_Perkawinan, Kewarnegaraan
            FROM TEMP_CAFLESS_OCR_Rate WITH(NOLOCK)
            WHERE Id IN (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for)
        """), {"pid": prechecking_id, "ocr_for": ocr_for}).mappings().all()}

        dukcapil_rows = list(db.session.execute(text("""
            SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin, Alamat, RT, RW,
                   Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan, Status_Perkawinan
            FROM TEMP_CAFLESS_OCR_Dukcapil WITH(NOLOCK)
            WHERE Id IN (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for)
        """), {"pid": prechecking_id, "ocr_for": ocr_for}).mappings().all())

        for idx, d in enumerate(director_rows):
            rate = rate_rows.get(d["NIK"], {})
            duk  = dukcapil_rows[idx] if idx < len(dukcapil_rows) else {}

            directors.append({
                "id":               d["Id"],
                "id_card_no":       d["NIK"] or "",
                "name":             d["Nama"] or "",
                "pob":              d["Tempat_Lahir"] or "",
                "dob":              d["Tgl_Lahir"] or "",
                "gender":           d["Jenis_Kelamin"] or "",
                "blood_type":       d["Golongan_Darah"] or "",
                "address":          d["Alamat"] or "",
                "rt":               d["RT"] or "",
                "rw":               d["RW"] or "",
                "subdistrict":      d["Kelurahan"] or "",
                "district":         d["Kecamatan"] or "",
                "city":             d["Kota"] or "",
                "province":         d["Provinsi"] or "",
                "religion":         d["Agama"] or "",
                "job":              d["Pekerjaan"] or "",
                "marital_status":   _marital_for_display(d["Status_Perkawinan"]),
                "citizen":          d["Kewarnegaraan"] or "",
                "photo_hidden":     d["Foto"] or "",
                "signature_hidden": d["Tanda_Tangan"] or "",
                "rate": {
                    "id_card_no":  f"{rate.get('NIK')}%" if rate.get("NIK") else "",
                    "name":        f"{rate.get('Nama')}%" if rate.get("Nama") else "",
                    "pob":         f"{rate.get('Tempat_Lahir')}%" if rate.get("Tempat_Lahir") else "",
                    "dob":         f"{rate.get('Tgl_Lahir')}%" if rate.get("Tgl_Lahir") else "",
                    "gender":      f"{rate.get('Jenis_Kelamin')}%" if rate.get("Jenis_Kelamin") else "",
                    "blood_type":  f"{rate.get('Golongan_Darah')}%" if rate.get("Golongan_Darah") else "",
                    "address":     f"{rate.get('Alamat')}%" if rate.get("Alamat") else "",
                    "rt":          f"{rate.get('RT')}%" if rate.get("RT") else "",
                    "rw":          f"{rate.get('RW')}%" if rate.get("RW") else "",
                    "subdistrict": f"{rate.get('Kelurahan')}%" if rate.get("Kelurahan") else "",
                    "district":    f"{rate.get('Kecamatan')}%" if rate.get("Kecamatan") else "",
                    "city":        f"{rate.get('Kota')}%" if rate.get("Kota") else "",
                    "province":    f"{rate.get('Provinsi')}%" if rate.get("Provinsi") else "",
                    "religion":    f"{rate.get('Agama')}%" if rate.get("Agama") else "",
                    "job":         f"{rate.get('Pekerjaan')}%" if rate.get("Pekerjaan") else "",
                    "marital_status": f"{rate.get('Status_Perkawinan')}%" if rate.get("Status_Perkawinan") else "",
                    "citizen":     f"{rate.get('Kewarnegaraan')}%" if rate.get("Kewarnegaraan") else "",
                },
                "verified": {
                    "id_card_no":     _ver_flag(duk.get("NIK")),
                    "name":           _ver_flag(duk.get("Nama")),
                    "pob":            _ver_flag(duk.get("Tempat_Lahir")),
                    "dob":            _ver_flag(duk.get("Tgl_Lahir")),
                    "gender":         _ver_flag(duk.get("Jenis_Kelamin")),
                    "address":        _ver_flag(duk.get("Alamat")),
                    "rt":             _ver_flag(duk.get("RT")),
                    "rw":             _ver_flag(duk.get("RW")),
                    "subdistrict":    _ver_flag(duk.get("Kelurahan")),
                    "district":       _ver_flag(duk.get("Kecamatan")),
                    "city":           _ver_flag(duk.get("Kota")),
                    "province":       _ver_flag(duk.get("Provinsi")),
                    "job":            _ver_flag(duk.get("Pekerjaan")),
                    "marital_status": _ver_flag(duk.get("Status_Perkawinan")),
                },
            })

        wna_rows = db.session.execute(text("""
            SELECT Id, NIK, Nama FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for AND Citizen = 'WNA'
        """), {"pid": prechecking_id, "ocr_for": ocr_for}).mappings().all()
        wna_board = [{"id": w["Id"], "id_card_no": w["NIK"] or "", "name": w["Nama"] or ""} for w in wna_rows]

        doc_rows = db.session.execute(text("""
            SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE Apless = :apless AND Prechecking_Id = :pid
            ORDER BY DocumentType, CreatedDate
        """), {"apless": apless, "pid": prechecking_id}).mappings().all()

        documents: dict = {}
        for r in doc_rows:
            if not r["DocumentName"]:
                continue
            documents.setdefault(r["DocumentType"], []).append({
                "id":       r["CustomerDocumentId"],
                "name":     r["DocumentName"],
                "view_url": _aws_presign(r["AWSKey"], r["DocumentName"]) if r["AWSKey"] else None,
            })

        sik_rows = db.session.execute(text("""
            SELECT Subject, Description, CreditBureau, RelatedParty, Status, Type, Score, Grade
            FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
            WHERE Prechecking_Id = :pid
        """), {"pid": prechecking_id}).mappings().all()

        subject_label = {"C": "Customer", "G": "Guarantor"}
        sik_summary = [{
            "subject":       subject_label.get(r["Subject"], "Pengurus"),
            "credit_bureau": r["CreditBureau"] or "",
            "status":        r["Status"] or "",
            "score":         r["Score"] or "",
            "grade":         r["Grade"] or "",
        } for r in sik_rows]

        sik_doc_rows = db.session.execute(text("""
            SELECT DISTINCT Subject, Description, CreditBureau, RelatedParty, Status, Type,
                   Score, Grade, Pefindo, AWSKey, DocumentType, Cabpefindo, CreatedDate
            FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
            WHERE Prechecking_Id = :pid
        """), {"pid": prechecking_id}).mappings().all()

        sik_documents = [{
            "subject":       r["Subject"] or "",
            "description":   r["Description"] or "",
            "credit_bureau": r["CreditBureau"] or "",
            "status":        r["Status"] or "",
            "score":         r["Score"] or "",
            "grade":         r["Grade"] or "",
            "pefindo":       r["Pefindo"] or "",
            "has_file":      bool(r["Pefindo"]),
        } for r in sik_doc_rows]

        repeat_order = bool(header_row["Repeat_Order"])

        return jsonify({
            "success": True,
            "apless": apless,
            "prechecking_id": prechecking_id,
            "check_for": check_for,
            "customer_type": customer_type,
            "is_corporate": is_corporate,
            "is_guarantor_pt": is_guarantor_pt,
            "lessee_type": header_row["LesseeType"] or "",
            "corp_name": header_row["LesseeName"] or "",
            "corp_address": header_row["WorkAddress"] or "",
            "corp_npwp_no": header_row["NPWP"] or "",
            "note_prechecking": header_row["Notes"] or "",
            "carro": header_row["Carro"],
            "repeat_order": repeat_order,
            "last_checking_date": last_checking_date,
            "last_disburse": last_disburse,
            "directors": directors,
            "wna_board": wna_board,
            "documents": documents,
            "sik_summary": sik_summary,
            "sik_documents": sik_documents,
        })

    except Exception:
        current_app.logger.exception("get_edit_corporate error")
        return jsonify({"success": False, "message": "Failed to load prechecking data"}), 500