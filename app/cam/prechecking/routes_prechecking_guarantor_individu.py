from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
import base64, os, mimetypes
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

prechecking_guarantor_bp = Blueprint("prechecking_guarantor", __name__, url_prefix="/CAM/Prechecking")

_OCR_DOC_TYPES = {"guarantor-ktp", "guarantor-spouse-ktp", "guarantor-wna-spouse-ktp"}

_WNA_ID_TYPES = ("KITAS", "KITAP")

_DOC_TYPE_SIBLINGS: dict = {
    "guarantor-kitas":        ("guarantor-kitas", "guarantor-kitap"),
    "guarantor-kitap":        ("guarantor-kitas", "guarantor-kitap"),
    "guarantor-spouse-kitas": ("guarantor-spouse-kitas", "guarantor-spouse-kitap"),
    "guarantor-spouse-kitap": ("guarantor-spouse-kitas", "guarantor-spouse-kitap"),
}

def _norm_id_type(value, nationality: str) -> str:
    if (nationality or "").strip().upper() != "WNA":
        return "KTP"
    v = (value or "").strip().upper()
    return v if v in _WNA_ID_TYPES else "KITAS"

def _is_ocr_doc_type(document_type: str) -> bool:
    return (document_type or "") in _OCR_DOC_TYPES

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

@prechecking_guarantor_bp.route("/submit-guarantor", methods=["POST"])
@login_required
def submit_prechecking_guarantor():

    username = _username()
    branch   = _branch()
    emp_id   = _emp_id()

    body = request.form.to_dict() if request.form else (request.get_json(force=True) or {})

    def g(key, default=""):
        return (body.get(key) or default).strip() if isinstance(body.get(key), str) else (body.get(key) or default)

    prechecking_id  = g("prechecking_id")
    apless          = g("apless")
    cust_type       = g("cust_type", "PR")
    lessee_type     = g("lessee_type", "PR")
    check_for       = g("check_for", "G")
    cust_new_ro     = 0 if g("cust_new_ro", "New") == "New" else 1
    existing_apless = g("existing_apless")
    nationality     = g("guarantor_nationality_type", "WNI")
    marital         = g("marital_status")
    wna_marital     = g("wna_marital_status")
    is_carro        = int(g("is_carro_type", "1"))
    note_pr         = g("note_prechecking_pr")
    note_pt         = g("note_prechecking_pt")

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id is required"}), 400

    errors = {}
    required_guarantor = [
        ("guarantor_id_card_no", "NIK"),
        ("guarantor_name",       "Nama"),
        ("guarantor_pob",        "Tempat Lahir"),
        ("guarantor_dob",        "Tanggal Lahir"),
        ("guarantor_gender",     "Jenis Kelamin"),
        ("guarantor_address",    "Alamat"),
        ("guarantor_rt",         "RT"),
        ("guarantor_rw",         "RW"),
        ("guarantor_subdistrict","Kelurahan/Desa"),
        ("guarantor_district",   "Kecamatan"),
        ("guarantor_city",       "Kota/Kabupaten"),
        ("guarantor_province",   "Provinsi"),
        ("guarantor_religion",   "Agama"),
        ("guarantor_job",        "Pekerjaan"),
    ]
    if nationality == "WNI":
        for key, label in required_guarantor:
            if not g(key):
                errors[f"{key}_error"] = f"{label} is required"
    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    _marital_map = {
        "BELUM KAWIN": "S", "KAWIN": "M", "KAWIN TERCATAT": "M",
        "KAWIN BELUM TERCATAT": "O", "PERJANJIAN PRANIKAH": "P",
        "CERAI HIDUP": "D", "CERAI MATI": "D",
    }
    def nm(val):
        return _marital_map.get((val or "").strip().upper(), val)

    marital     = nm(marital)
    wna_marital = nm(wna_marital)

    nik          = g("guarantor_id_card_no")
    guarantor_name = g("guarantor_name")
    guarantor_dob  = g("guarantor_dob")
    guarantor_citizen = g("guarantor_citizen", "WNI")

    sp_nik       = g("guarantor_spouse_id_card_no")
    sp_citizen   = g("guarantor_spouse_citizen", "WNI")

    wna_name     = g("guarantor_wna_name")
    wna_idcard   = g("guarantor_wna_idcard_no")
    wna_sp_name  = g("guarantor_spouse_wna_name")
    wna_sp_id    = g("guarantor_spouse_wna_id_card_no")

    wna_sp_nik     = g("guarantor_wna_spouse_id_card_no")
    wna_sp_citizen = g("guarantor_wna_spouse_citizen", "WNI")

    guarantor_id_type  = _norm_id_type(g("guarantor_id_type"), nationality)
    wna_spouse_id_type = _norm_id_type(g("guarantor_spouse_id_type"), "WNA")

    is_married     = marital in ("M", "O")
    is_wna_married = wna_marital in ("M", "O")

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

        if not already_exists:

            if nationality == "WNI":

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS
                        (Apless, CustomerType, LesseeType, LesseeName, IdCardNo, NPWP,
                         MaritalStatus, CreatedBy, CreatedDate,
                         Prechecking_Id, Check_For, Repeat_Order, Notes, Carro)
                    VALUES
                        (:apless, :cust_type, :lessee_type, :guarantor_name, :nik, '',
                         :marital, :username, GETDATE(),
                         :pid, :check_for, :new_ro, :note_pr, :is_carro)
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "guarantor_name": guarantor_name, "nik": nik, "marital": marital,
                    "username": username, "pid": prechecking_id, "check_for": check_for,
                    "new_ro": cust_new_ro, "note_pr": note_pr, "is_carro": is_carro,
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                         Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                         Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                         Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                    VALUES
                        (:pid, :check_for, :citizen, 'KTP', :nik, :nama, :pob,
                         :dob, :gender, :blood, :addr, :rt, :rw,
                         :subdistrict, :district, :city, :province, :religion, :job,
                         :marital, :citizen2, :photo, :sign)
                """), {
                    "pid": prechecking_id, "check_for": check_for,
                    "citizen": guarantor_citizen, "nik": nik,
                    "nama": guarantor_name, "pob": g("guarantor_pob"),
                    "dob": datetime.strptime(g("guarantor_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                    "gender": g("guarantor_gender"),
                    "blood": g("guarantor_blood_type"), "addr": g("guarantor_address"),
                    "rt": g("guarantor_rt"), "rw": g("guarantor_rw"),
                    "subdistrict": g("guarantor_subdistrict"), "district": g("guarantor_district"),
                    "city": g("guarantor_city"), "province": g("guarantor_province"),
                    "religion": g("guarantor_religion"), "job": g("guarantor_job"),
                    "marital": marital, "citizen2": guarantor_citizen,
                    "photo": g("guarantor_photo_hidden"), "sign": g("guarantor_signature_hidden"),
                })

                guarantor_ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id = :pid AND NIK = :nik"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                guarantor_id = guarantor_ocr_row.Id if guarantor_ocr_row else 0

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Rate
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                         Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender,
                         :blood, :addr, :rt, :rw, :subdistrict, :district,
                         :city, :province, :religion, :job, :citizen)
                """), {
                    "id": guarantor_id,
                    "nik":        _strip_non_digit(g("val_guarantor_id_card_no")),
                    "nama":       _strip_non_digit(g("val_guarantor_name")),
                    "pob":        _strip_non_digit(g("val_guarantor_pob")),
                    "dob":        _strip_non_digit(g("val_guarantor_dob")),
                    "gender":     _strip_non_digit(g("val_guarantor_gender")),
                    "blood":      _strip_non_digit(g("val_guarantor_blood_type")),
                    "addr":       _strip_non_digit(g("val_guarantor_address")),
                    "rt":         _strip_non_digit(g("val_guarantor_rt")),
                    "rw":         _strip_non_digit(g("val_guarantor_rw")),
                    "subdistrict":_strip_non_digit(g("val_guarantor_subdistrict")),
                    "district":   _strip_non_digit(g("val_guarantor_district")),
                    "city":       _strip_non_digit(g("val_guarantor_city")),
                    "province":   _strip_non_digit(g("val_guarantor_province")),
                    "religion":   _strip_non_digit(g("val_guarantor_religion")),
                    "job":        _strip_non_digit(g("val_guarantor_job")),
                    "citizen":    _strip_non_digit(g("val_guarantor_citizen")),
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                         :rt, :rw, :subdistrict, :district, :city, :province, :job)
                """), {
                    "id":         guarantor_id,
                    "nik":        _to_bit(g("ver_guarantor_id_card_no")),
                    "nama":       _to_bit(g("ver_guarantor_name")),
                    "pob":        _to_bit(g("ver_guarantor_pob")),
                    "dob":        _to_bit(g("ver_guarantor_dob")),
                    "gender":     _to_bit(g("ver_guarantor_gender")),
                    "addr":       _to_bit(g("ver_guarantor_address")),
                    "rt":         _to_bit(g("ver_guarantor_rt")),
                    "rw":         _to_bit(g("ver_guarantor_rw")),
                    "subdistrict":_to_bit(g("ver_guarantor_subdistrict")),
                    "district":   _to_bit(g("ver_guarantor_district")),
                    "city":       _to_bit(g("ver_guarantor_city")),
                    "province":   _to_bit(g("ver_guarantor_province")),
                    "job":        _to_bit(g("ver_guarantor_job")),
                })

                if is_married:
                    if sp_citizen == "WNI":
                        sp_exists = db.session.execute(
                            text("SELECT COUNT(1) AS cnt FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id = :pid AND OCR_For = 'S'"),
                            {"pid": prechecking_id},
                        ).fetchone()

                        if sp_exists and sp_exists.cnt > 0:
                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR SET
                                    OCR_For='S', Citizen=:citizen, Id_Type='KTP', NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                    Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                    Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                    Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                    Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                                WHERE Prechecking_Id=:pid AND OCR_For='S'
                            """), {
                                "pid": prechecking_id, "citizen": sp_citizen,
                                "nik": sp_nik, "nama": g("guarantor_spouse_name"),
                                "pob": g("guarantor_spouse_pob"),
                                "dob": datetime.strptime(g("guarantor_spouse_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                                "gender": g("guarantor_spouse_gender"), "blood": g("guarantor_spouse_blood_type"),
                                "addr": g("guarantor_spouse_address"), "rt": g("guarantor_spouse_rt"),
                                "rw": g("guarantor_spouse_rw"), "subdistrict": g("guarantor_spouse_subdistrict"),
                                "district": g("guarantor_spouse_district"), "city": g("guarantor_spouse_city"),
                                "province": g("guarantor_spouse_province"), "religion": g("guarantor_spouse_religion"),
                                "job": g("guarantor_spouse_job"), "marital": marital,
                                "citizen2": sp_citizen,
                                "photo": g("guarantor_spouse_photo_hidden"), "sign": g("guarantor_spouse_signature_hidden"),
                            })

                            sp_ocr_row = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Rate SET
                                    NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                    RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province, Agama=:religion,
                                    Pekerjaan=:job, Kewarnegaraan=:citizen
                                WHERE Id=:id
                            """), {
                                "id": sp_id,
                                "nik":        _strip_non_digit(g("val_guarantor_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_guarantor_spouse_name")),
                                "pob":        _strip_non_digit(g("val_guarantor_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_guarantor_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_guarantor_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_guarantor_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_guarantor_spouse_address")),
                                "rt":         _strip_non_digit(g("val_guarantor_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_guarantor_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_guarantor_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_guarantor_spouse_district")),
                                "city":       _strip_non_digit(g("val_guarantor_spouse_city")),
                                "province":   _strip_non_digit(g("val_guarantor_spouse_province")),
                                "religion":   _strip_non_digit(g("val_guarantor_spouse_religion")),
                                "job":        _strip_non_digit(g("val_guarantor_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_guarantor_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                    NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Alamat=:addr,
                                    RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province,
                                    Pekerjaan=:job
                                WHERE Id=:id
                            """), {
                                "id": sp_id,
                                "nik": _to_bit(g("ver_guarantor_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_spouse_name")),
                                "pob": _to_bit(g("ver_guarantor_spouse_pob")), "dob": _to_bit(g("ver_guarantor_spouse_dob")),
                                "gender": _to_bit(g("ver_guarantor_spouse_gender")), "addr": _to_bit(g("ver_guarantor_spouse_address")),
                                "rt": _to_bit(g("ver_guarantor_spouse_rt")), "rw": _to_bit(g("ver_guarantor_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_guarantor_spouse_subdistrict")),
                                "district": _to_bit(g("ver_guarantor_spouse_district")),
                                "city": _to_bit(g("ver_guarantor_spouse_city")),
                                "province": _to_bit(g("ver_guarantor_spouse_province")),
                                "job": _to_bit(g("ver_guarantor_spouse_job")),
                            })

                        else:
                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR
                                    (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                                     Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                                     Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                                     Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                                VALUES
                                    (:pid,'S',:citizen,'KTP',:nik,:nama,:pob,
                                     :dob,:gender,:blood,:addr,:rt,:rw,
                                     :subdistrict,:district,:city,:province,:religion,:job,
                                     :marital,:citizen2,:photo,:sign)
                            """), {
                                "pid": prechecking_id, "citizen": sp_citizen,
                                "nik": sp_nik, "nama": g("guarantor_spouse_name"),
                                "pob": g("guarantor_spouse_pob"),
                                "dob": datetime.strptime(g("guarantor_spouse_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                                "gender": g("guarantor_spouse_gender"), "blood": g("guarantor_spouse_blood_type"),
                                "addr": g("guarantor_spouse_address"), "rt": g("guarantor_spouse_rt"),
                                "rw": g("guarantor_spouse_rw"), "subdistrict": g("guarantor_spouse_subdistrict"),
                                "district": g("guarantor_spouse_district"), "city": g("guarantor_spouse_city"),
                                "province": g("guarantor_spouse_province"), "religion": g("guarantor_spouse_religion"),
                                "job": g("guarantor_spouse_job"), "marital": marital,
                                "citizen2": sp_citizen,
                                "photo": g("guarantor_spouse_photo_hidden"), "sign": g("guarantor_spouse_signature_hidden"),
                            })

                            sp_ocr_row = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Rate
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                                     Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                                VALUES
                                    (:id,:nik,:nama,:pob,:dob,:gender,
                                     :blood,:addr,:rt,:rw,:subdistrict,:district,
                                     :city,:province,:religion,:job,:citizen)
                            """), {
                                "id": sp_id,
                                "nik":        _strip_non_digit(g("val_guarantor_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_guarantor_spouse_name")),
                                "pob":        _strip_non_digit(g("val_guarantor_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_guarantor_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_guarantor_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_guarantor_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_guarantor_spouse_address")),
                                "rt":         _strip_non_digit(g("val_guarantor_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_guarantor_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_guarantor_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_guarantor_spouse_district")),
                                "city":       _strip_non_digit(g("val_guarantor_spouse_city")),
                                "province":   _strip_non_digit(g("val_guarantor_spouse_province")),
                                "religion":   _strip_non_digit(g("val_guarantor_spouse_religion")),
                                "job":        _strip_non_digit(g("val_guarantor_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_guarantor_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                                VALUES
                                    (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                                     :rt, :rw, :subdistrict, :district, :city, :province, :job)
                            """), {
                                "id": sp_id,
                                "nik": _to_bit(g("ver_guarantor_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_spouse_name")),
                                "pob": _to_bit(g("ver_guarantor_spouse_pob")), "dob": _to_bit(g("ver_guarantor_spouse_dob")),
                                "gender": _to_bit(g("ver_guarantor_spouse_gender")), "addr": _to_bit(g("ver_guarantor_spouse_address")),
                                "rt": _to_bit(g("ver_guarantor_spouse_rt")), "rw": _to_bit(g("ver_guarantor_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_guarantor_spouse_subdistrict")),
                                "district": _to_bit(g("ver_guarantor_spouse_district")),
                                "city": _to_bit(g("ver_guarantor_spouse_city")),
                                "province": _to_bit(g("ver_guarantor_spouse_province")),
                                "job": _to_bit(g("ver_guarantor_spouse_job")),
                            })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Kewarnegaraan, Id_Type, NIK, Nama, UpdatedDate)
                            VALUES (:pid,'S','WNA','WNA',:id_type,:nik,:nama,GETDATE())
                        """), {"pid": prechecking_id, "nik": wna_sp_id, "nama": wna_sp_name,
                               "id_type": wna_spouse_id_type})

            else:
                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS
                        (Apless, CustomerType, LesseeType, LesseeName, IdCardNo, NPWP,
                         MaritalStatus, CreatedBy, CreatedDate,
                         Prechecking_Id, Check_For, Repeat_Order, Notes, Carro)
                    VALUES
                        (:apless,:cust_type,:lessee_type,:wna_name,:wna_idcard,'',
                         :wna_marital,:username,GETDATE(),
                         :pid,:check_for,:new_ro,:note_pr,:is_carro)
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "wna_name": wna_name, "wna_idcard": wna_idcard,
                    "wna_marital": wna_marital, "username": username,
                    "pid": prechecking_id, "check_for": check_for,
                    "new_ro": cust_new_ro, "note_pr": note_pr, "is_carro": is_carro,
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama,
                         Status_Perkawinan, Kewarnegaraan)
                    VALUES (:pid,:check_for,'WNA',:id_type,:nik,:nama,:wna_marital,'WNA')
                """), {
                    "pid": prechecking_id, "check_for": check_for,
                    "nik": wna_idcard, "nama": wna_name, "wna_marital": wna_marital,
                    "id_type": guarantor_id_type,
                })

                if is_wna_married:
                    if wna_sp_citizen == "WNI":
                        sp_exists = db.session.execute(
                            text("SELECT COUNT(1) AS cnt FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                            {"pid": prechecking_id},
                        ).fetchone()

                        if sp_exists and sp_exists.cnt > 0:
                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR SET
                                    OCR_For='S', Citizen=:citizen, Id_Type='KTP', NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                    Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                    Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                    Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                    Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                                WHERE Prechecking_Id=:pid AND OCR_For='S'
                            """), {
                                "pid": prechecking_id, "citizen": wna_sp_citizen,
                                "nik": wna_sp_nik, "nama": g("guarantor_wna_spouse_name"),
                                "pob": g("guarantor_wna_spouse_pob"), "dob": g("guarantor_wna_spouse_dob"),
                                "gender": g("guarantor_wna_spouse_gender"), "blood": g("guarantor_wna_spouse_blood_type"),
                                "addr": g("guarantor_wna_spouse_address"), "rt": g("guarantor_wna_spouse_rt"),
                                "rw": g("guarantor_wna_spouse_rw"), "subdistrict": g("guarantor_wna_spouse_subdistrict"),
                                "district": g("guarantor_wna_spouse_district"), "city": g("guarantor_wna_spouse_city"),
                                "province": g("guarantor_wna_spouse_province"), "religion": g("guarantor_wna_spouse_religion"),
                                "job": g("guarantor_wna_spouse_job"), "marital": wna_marital,
                                "citizen2": wna_sp_citizen,
                                "photo": g("guarantor_wna_spouse_photo_hidden"), "sign": g("guarantor_wna_spouse_signature_hidden"),
                            })

                            wna_sp_ocr = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Rate SET
                                    NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                    RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province, Agama=:religion,
                                    Pekerjaan=:job, Kewarnegaraan=:citizen
                                WHERE Id=:id
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik":        _strip_non_digit(g("val_guarantor_wna_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_guarantor_wna_spouse_name")),
                                "pob":        _strip_non_digit(g("val_guarantor_wna_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_guarantor_wna_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_guarantor_wna_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_guarantor_wna_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_guarantor_wna_spouse_address")),
                                "rt":         _strip_non_digit(g("val_guarantor_wna_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_guarantor_wna_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_guarantor_wna_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_guarantor_wna_spouse_district")),
                                "city":       _strip_non_digit(g("val_guarantor_wna_spouse_city")),
                                "province":   _strip_non_digit(g("val_guarantor_wna_spouse_province")),
                                "religion":   _strip_non_digit(g("val_guarantor_wna_spouse_religion")),
                                "job":        _strip_non_digit(g("val_guarantor_wna_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_guarantor_wna_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                    NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Alamat=:addr,
                                    RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province,
                                    Pekerjaan=:job
                                WHERE Id=:id
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik": _to_bit(g("ver_guarantor_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_wna_spouse_name")),
                                "pob": _to_bit(g("ver_guarantor_wna_spouse_pob")), "dob": _to_bit(g("ver_guarantor_wna_spouse_dob")),
                                "gender": _to_bit(g("ver_guarantor_wna_spouse_gender")), "addr": _to_bit(g("ver_guarantor_wna_spouse_address")),
                                "rt": _to_bit(g("ver_guarantor_wna_spouse_rt")), "rw": _to_bit(g("ver_guarantor_wna_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_guarantor_wna_spouse_subdistrict")),
                                "district": _to_bit(g("ver_guarantor_wna_spouse_district")),
                                "city": _to_bit(g("ver_guarantor_wna_spouse_city")),
                                "province": _to_bit(g("ver_guarantor_wna_spouse_province")),
                                "job": _to_bit(g("ver_guarantor_wna_spouse_job")),
                            })

                        else:
                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR
                                    (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                                     Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                                     Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                                     Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                                VALUES
                                    (:pid,'S',:citizen,'KTP',:nik,:nama,:pob,
                                     :dob,:gender,:blood,:addr,:rt,:rw,
                                     :subdistrict,:district,:city,:province,:religion,:job,
                                     :marital,:citizen2,:photo,:sign)
                            """), {
                                "pid": prechecking_id, "citizen": wna_sp_citizen,
                                "nik": wna_sp_nik, "nama": g("guarantor_wna_spouse_name"),
                                "pob": g("guarantor_wna_spouse_pob"),
                                "dob": datetime.strptime(g("guarantor_wna_spouse_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                                "gender": g("guarantor_wna_spouse_gender"), "blood": g("guarantor_wna_spouse_blood_type"),
                                "addr": g("guarantor_wna_spouse_address"), "rt": g("guarantor_wna_spouse_rt"),
                                "rw": g("guarantor_wna_spouse_rw"), "subdistrict": g("guarantor_wna_spouse_subdistrict"),
                                "district": g("guarantor_wna_spouse_district"), "city": g("guarantor_wna_spouse_city"),
                                "province": g("guarantor_wna_spouse_province"), "religion": g("guarantor_wna_spouse_religion"),
                                "job": g("guarantor_wna_spouse_job"), "marital": wna_marital,
                                "citizen2": wna_sp_citizen,
                                "photo": g("guarantor_wna_spouse_photo_hidden"), "sign": g("guarantor_wna_spouse_signature_hidden"),
                            })

                            wna_sp_ocr = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                                {"pid": prechecking_id, "nik": wna_sp_nik},
                            ).fetchone()
                            wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Rate
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                                     Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                                VALUES
                                    (:id,:nik,:nama,:pob,:dob,:gender,
                                     :blood,:addr,:rt,:rw,:subdistrict,:district,
                                     :city,:province,:religion,:job,:citizen)
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik":        _strip_non_digit(g("val_guarantor_wna_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_guarantor_wna_spouse_name")),
                                "pob":        _strip_non_digit(g("val_guarantor_wna_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_guarantor_wna_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_guarantor_wna_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_guarantor_wna_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_guarantor_wna_spouse_address")),
                                "rt":         _strip_non_digit(g("val_guarantor_wna_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_guarantor_wna_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_guarantor_wna_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_guarantor_wna_spouse_district")),
                                "city":       _strip_non_digit(g("val_guarantor_wna_spouse_city")),
                                "province":   _strip_non_digit(g("val_guarantor_wna_spouse_province")),
                                "religion":   _strip_non_digit(g("val_guarantor_wna_spouse_religion")),
                                "job":        _strip_non_digit(g("val_guarantor_wna_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_guarantor_wna_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                                VALUES
                                    (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                                     :rt, :rw, :subdistrict, :district, :city, :province, :job)
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik": _to_bit(g("ver_guarantor_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_wna_spouse_name")),
                                "pob": _to_bit(g("ver_guarantor_wna_spouse_pob")), "dob": _to_bit(g("ver_guarantor_wna_spouse_dob")),
                                "gender": _to_bit(g("ver_guarantor_wna_spouse_gender")), "addr": _to_bit(g("ver_guarantor_wna_spouse_address")),
                                "rt": _to_bit(g("ver_guarantor_wna_spouse_rt")), "rw": _to_bit(g("ver_guarantor_wna_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_guarantor_wna_spouse_subdistrict")),
                                "district": _to_bit(g("ver_guarantor_wna_spouse_district")),
                                "city": _to_bit(g("ver_guarantor_wna_spouse_city")),
                                "province": _to_bit(g("ver_guarantor_wna_spouse_province")),
                                "job": _to_bit(g("ver_guarantor_wna_spouse_job")),
                            })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA')
                        """), {"pid": prechecking_id, "nik": wna_sp_id, "nama": wna_sp_name,
                               "id_type": wna_spouse_id_type})

        else:
            if nationality == "WNI":
                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS SET
                        Apless=:apless, CustomerType=:cust_type, LesseeType=:lessee_type,
                        LesseeName=:guarantor_name, NPWP='', MaritalStatus=:marital,
                        CreatedBy=:username, CreatedDate=GETDATE(),
                        Check_For=:check_for, Repeat_Order=:new_ro,
                        Notes=:note_pr, Carro=:is_carro
                    WHERE IdCardNo=:nik AND Prechecking_Id=:pid
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "guarantor_name": guarantor_name, "marital": marital, "username": username,
                    "check_for": check_for, "new_ro": cust_new_ro, "note_pr": note_pr,
                    "is_carro": is_carro, "nik": nik, "pid": prechecking_id,
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        OCR_For=:check_for, Citizen=:citizen, Id_Type='KTP', Nama=:nama, Tempat_Lahir=:pob,
                        Tgl_Lahir=:dob, Jenis_Kelamin=:gender, Golongan_Darah=:blood,
                        Alamat=:addr, RT=:rt, RW=:rw, Kelurahan=:subdistrict,
                        Kecamatan=:district, Kota=:city, Provinsi=:province,
                        Agama=:religion, Pekerjaan=:job, Status_Perkawinan=:marital,
                        Kewarnegaraan=:citizen2, Foto=:photo, Tanda_Tangan=:sign,
                        UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid AND NIK=:nik
                """), {
                    "pid": prechecking_id, "check_for": check_for,
                    "citizen": guarantor_citizen, "nik": nik,
                    "nama": guarantor_name, "pob": g("guarantor_pob"), "dob": g("guarantor_dob"),
                    "gender": g("guarantor_gender"), "blood": g("guarantor_blood_type"),
                    "addr": g("guarantor_address"), "rt": g("guarantor_rt"), "rw": g("guarantor_rw"),
                    "subdistrict": g("guarantor_subdistrict"), "district": g("guarantor_district"),
                    "city": g("guarantor_city"), "province": g("guarantor_province"),
                    "religion": g("guarantor_religion"), "job": g("guarantor_job"),
                    "marital": marital, "citizen2": guarantor_citizen,
                    "photo": g("guarantor_photo_hidden"), "sign": g("guarantor_signature_hidden"),
                })

                guarantor_ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                guarantor_id = guarantor_ocr_row.Id if guarantor_ocr_row else 0

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Rate SET
                        NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                        RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                        Kota=:city, Provinsi=:province, Agama=:religion,
                        Pekerjaan=:job, Kewarnegaraan=:citizen
                    WHERE Id=:id
                """), {
                    "id": guarantor_id,
                    "nik":        _strip_non_digit(g("val_guarantor_id_card_no")),
                    "nama":       _strip_non_digit(g("val_guarantor_name")),
                    "pob":        _strip_non_digit(g("val_guarantor_pob")),
                    "dob":        _strip_non_digit(g("val_guarantor_dob")),
                    "gender":     _strip_non_digit(g("val_guarantor_gender")),
                    "blood":      _strip_non_digit(g("val_guarantor_blood_type")),
                    "addr":       _strip_non_digit(g("val_guarantor_address")),
                    "rt":         _strip_non_digit(g("val_guarantor_rt")),
                    "rw":         _strip_non_digit(g("val_guarantor_rw")),
                    "subdistrict":_strip_non_digit(g("val_guarantor_subdistrict")),
                    "district":   _strip_non_digit(g("val_guarantor_district")),
                    "city":       _strip_non_digit(g("val_guarantor_city")),
                    "province":   _strip_non_digit(g("val_guarantor_province")),
                    "religion":   _strip_non_digit(g("val_guarantor_religion")),
                    "job":        _strip_non_digit(g("val_guarantor_job")),
                    "citizen":    _strip_non_digit(g("val_guarantor_citizen")),
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                        NIK=:nik, Nama=:nama,
                        Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Alamat=:addr,
                        RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district,
                        Kota=:city, Provinsi=:province,
                        Pekerjaan=:job
                    WHERE Id=:id
                """), {
                    "id": guarantor_id,
                    "nik": _to_bit(g("ver_guarantor_id_card_no")), "nama": _to_bit(g("ver_guarantor_name")),
                    "pob": _to_bit(g("ver_guarantor_pob")), "dob": _to_bit(g("ver_guarantor_dob")),
                    "gender": _to_bit(g("ver_guarantor_gender")), "addr": _to_bit(g("ver_guarantor_address")),
                    "rt": _to_bit(g("ver_guarantor_rt")), "rw": _to_bit(g("ver_guarantor_rw")),
                    "subdistrict": _to_bit(g("ver_guarantor_subdistrict")), "district": _to_bit(g("ver_guarantor_district")),
                    "city": _to_bit(g("ver_guarantor_city")), "province": _to_bit(g("ver_guarantor_province")),
                    "job": _to_bit(g("ver_guarantor_job")),
                })

                if is_married:
                    if sp_citizen == "WNI":
                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR SET
                                OCR_For='S', Citizen=:citizen, Id_Type='KTP', Nama=:nama, Tempat_Lahir=:pob,
                                Tgl_Lahir=:dob, Jenis_Kelamin=:gender, Golongan_Darah=:blood,
                                Alamat=:addr, RT=:rt, RW=:rw, Kelurahan=:subdistrict,
                                Kecamatan=:district, Kota=:city, Provinsi=:province,
                                Agama=:religion, Pekerjaan=:job, Status_Perkawinan=:marital,
                                Kewarnegaraan=:citizen2, Foto=:photo, Tanda_Tangan=:sign,
                                UpdatedDate=GETDATE()
                            WHERE Prechecking_Id=:pid AND NIK=:nik
                        """), {
                            "pid": prechecking_id, "citizen": sp_citizen, "nik": sp_nik,
                            "nama": g("guarantor_spouse_name"), "pob": g("guarantor_spouse_pob"),
                            "dob": datetime.strptime(g("guarantor_spouse_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                            "gender": g("guarantor_spouse_gender"),
                            "blood": g("guarantor_spouse_blood_type"), "addr": g("guarantor_spouse_address"),
                            "rt": g("guarantor_spouse_rt"), "rw": g("guarantor_spouse_rw"),
                            "subdistrict": g("guarantor_spouse_subdistrict"), "district": g("guarantor_spouse_district"),
                            "city": g("guarantor_spouse_city"), "province": g("guarantor_spouse_province"),
                            "religion": g("guarantor_spouse_religion"), "job": g("guarantor_spouse_job"),
                            "marital": marital, "citizen2": sp_citizen,
                            "photo": g("guarantor_spouse_photo_hidden"), "sign": g("guarantor_spouse_signature_hidden"),
                        })

                        sp_ocr_row = db.session.execute(
                            text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                            {"pid": prechecking_id, "nik": sp_nik},
                        ).fetchone()
                        sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Rate SET
                                NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province, Agama=:religion,
                                Pekerjaan=:job, Kewarnegaraan=:citizen
                            WHERE Id=:id
                        """), {
                            "id": sp_id,
                            "nik":        _strip_non_digit(g("val_guarantor_spouse_id_card_no")),
                            "nama":       _strip_non_digit(g("val_guarantor_spouse_name")),
                            "pob":        _strip_non_digit(g("val_guarantor_spouse_pob")),
                            "dob":        _strip_non_digit(g("val_guarantor_spouse_dob")),
                            "gender":     _strip_non_digit(g("val_guarantor_spouse_gender")),
                            "blood":      _strip_non_digit(g("val_guarantor_spouse_blood_type")),
                            "addr":       _strip_non_digit(g("val_guarantor_spouse_address")),
                            "rt":         _strip_non_digit(g("val_guarantor_spouse_rt")),
                            "rw":         _strip_non_digit(g("val_guarantor_spouse_rw")),
                            "subdistrict":_strip_non_digit(g("val_guarantor_spouse_subdistrict")),
                            "district":   _strip_non_digit(g("val_guarantor_spouse_district")),
                            "city":       _strip_non_digit(g("val_guarantor_spouse_city")),
                            "province":   _strip_non_digit(g("val_guarantor_spouse_province")),
                            "religion":   _strip_non_digit(g("val_guarantor_spouse_religion")),
                            "job":        _strip_non_digit(g("val_guarantor_spouse_job")),
                            "citizen":    _strip_non_digit(g("val_guarantor_spouse_citizen")),
                        })

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                NIK=:nik, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Alamat=:addr,
                                RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province,
                                Pekerjaan=:job
                            WHERE Id=:id
                        """), {
                            "id": sp_id,
                            "nik": _to_bit(g("ver_guarantor_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_spouse_name")),
                            "pob": _to_bit(g("ver_guarantor_spouse_pob")), "dob": _to_bit(g("ver_guarantor_spouse_dob")),
                            "gender": _to_bit(g("ver_guarantor_spouse_gender")), "addr": _to_bit(g("ver_guarantor_spouse_address")),
                            "rt": _to_bit(g("ver_guarantor_spouse_rt")), "rw": _to_bit(g("ver_guarantor_spouse_rw")),
                            "subdistrict": _to_bit(g("ver_guarantor_spouse_subdistrict")),
                            "district": _to_bit(g("ver_guarantor_spouse_district")),
                            "city": _to_bit(g("ver_guarantor_spouse_city")),
                            "province": _to_bit(g("ver_guarantor_spouse_province")),
                            "job": _to_bit(g("ver_guarantor_spouse_job")),
                        })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan, UpdatedDate)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA',GETDATE())
                        """), {"pid": prechecking_id, "nik": wna_sp_id, "nama": wna_sp_name,
                               "id_type": wna_spouse_id_type})

                else:
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR_Dukcapil
                        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S')
                    """), {"pid": prechecking_id})
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR_Rate
                        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S')
                    """), {"pid": prechecking_id})
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S'
                    """), {"pid": prechecking_id})

            else:
                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS SET
                        CustomerType=:cust_type, LesseeType=:lessee_type,
                        LesseeName=:wna_name, IdCardNo=:wna_idcard,
                        MaritalStatus=:wna_marital, CreatedBy=:username,
                        CreatedDate=GETDATE(), Check_For=:check_for,
                        Repeat_Order=:new_ro, Notes=:note_pr, Carro=:is_carro
                    WHERE Apless=:apless AND Prechecking_Id=:pid
                """), {
                    "cust_type": cust_type, "lessee_type": lessee_type,
                    "wna_name": wna_name, "wna_idcard": wna_idcard,
                    "wna_marital": wna_marital, "username": username,
                    "check_for": check_for, "new_ro": cust_new_ro,
                    "note_pr": note_pr, "is_carro": is_carro,
                    "apless": apless, "pid": prechecking_id,
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        OCR_For=:check_for, Citizen='WNA', Id_Type=:id_type, NIK=:nik, Nama=:nama,
                        Status_Perkawinan=:wna_marital, Kewarnegaraan='WNA', UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid
                """), {
                    "check_for": check_for, "nik": wna_idcard, "nama": wna_name,
                    "wna_marital": wna_marital, "pid": prechecking_id,
                    "id_type": guarantor_id_type,
                })

                if is_wna_married:
                    if wna_sp_citizen == "WNI":
                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR SET
                                OCR_For='S', Citizen=:citizen, Id_Type='KTP', Nama=:nama, Tempat_Lahir=:pob,
                                Tgl_Lahir=:dob, Jenis_Kelamin=:gender, Golongan_Darah=:blood,
                                Alamat=:addr, RT=:rt, RW=:rw, Kelurahan=:subdistrict,
                                Kecamatan=:district, Kota=:city, Provinsi=:province,
                                Agama=:religion, Pekerjaan=:job, Status_Perkawinan=:marital,
                                Kewarnegaraan=:citizen2, Foto=:photo, Tanda_Tangan=:sign,
                                UpdatedDate=GETDATE()
                            WHERE Prechecking_Id=:pid AND NIK=:nik
                        """), {
                            "pid": prechecking_id, "citizen": wna_sp_citizen, "nik": wna_sp_nik,
                            "nama": g("guarantor_wna_spouse_name"), "pob": g("guarantor_wna_spouse_pob"),
                            "dob": datetime.strptime(g("guarantor_wna_spouse_dob"), "%d-%m-%Y").strftime("%Y-%m-%d"),
                            "gender": g("guarantor_wna_spouse_gender"),
                            "blood": g("guarantor_wna_spouse_blood_type"), "addr": g("guarantor_wna_spouse_address"),
                            "rt": g("guarantor_wna_spouse_rt"), "rw": g("guarantor_wna_spouse_rw"),
                            "subdistrict": g("guarantor_wna_spouse_subdistrict"),
                            "district": g("guarantor_wna_spouse_district"), "city": g("guarantor_wna_spouse_city"),
                            "province": g("guarantor_wna_spouse_province"), "religion": g("guarantor_wna_spouse_religion"),
                            "job": g("guarantor_wna_spouse_job"), "marital": wna_marital,
                            "citizen2": wna_sp_citizen,
                            "photo": g("guarantor_wna_spouse_photo_hidden"), "sign": g("guarantor_wna_spouse_signature_hidden"),
                        })

                        wna_sp_ocr = db.session.execute(
                            text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                            {"pid": prechecking_id, "nik": wna_sp_nik},
                        ).fetchone()
                        wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Rate SET
                                NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province, Agama=:religion,
                                Pekerjaan=:job, Kewarnegaraan=:citizen
                            WHERE Id=:id
                        """), {
                            "id": wna_sp_ocr_id,
                            "nik":        _strip_non_digit(g("val_guarantor_wna_spouse_id_card_no")),
                            "nama":       _strip_non_digit(g("val_guarantor_wna_spouse_name")),
                            "pob":        _strip_non_digit(g("val_guarantor_wna_spouse_pob")),
                            "dob":        _strip_non_digit(g("val_guarantor_wna_spouse_dob")),
                            "gender":     _strip_non_digit(g("val_guarantor_wna_spouse_gender")),
                            "blood":      _strip_non_digit(g("val_guarantor_wna_spouse_blood_type")),
                            "addr":       _strip_non_digit(g("val_guarantor_wna_spouse_address")),
                            "rt":         _strip_non_digit(g("val_guarantor_wna_spouse_rt")),
                            "rw":         _strip_non_digit(g("val_guarantor_wna_spouse_rw")),
                            "subdistrict":_strip_non_digit(g("val_guarantor_wna_spouse_subdistrict")),
                            "district":   _strip_non_digit(g("val_guarantor_wna_spouse_district")),
                            "city":       _strip_non_digit(g("val_guarantor_wna_spouse_city")),
                            "province":   _strip_non_digit(g("val_guarantor_wna_spouse_province")),
                            "religion":   _strip_non_digit(g("val_guarantor_wna_spouse_religion")),
                            "job":        _strip_non_digit(g("val_guarantor_wna_spouse_job")),
                            "citizen":    _strip_non_digit(g("val_guarantor_wna_spouse_citizen")),
                        })

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                NIK=:nik, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Alamat=:addr,
                                RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province,
                                Pekerjaan=:job
                            WHERE Id=:id
                        """), {
                            "id": wna_sp_ocr_id,
                            "nik": _to_bit(g("ver_guarantor_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_guarantor_wna_spouse_name")),
                            "pob": _to_bit(g("ver_guarantor_wna_spouse_pob")), "dob": _to_bit(g("ver_guarantor_wna_spouse_dob")),
                            "gender": _to_bit(g("ver_guarantor_wna_spouse_gender")), "addr": _to_bit(g("ver_guarantor_wna_spouse_address")),
                            "rt": _to_bit(g("ver_guarantor_wna_spouse_rt")), "rw": _to_bit(g("ver_guarantor_wna_spouse_rw")),
                            "subdistrict": _to_bit(g("ver_guarantor_wna_spouse_subdistrict")),
                            "district": _to_bit(g("ver_guarantor_wna_spouse_district")),
                            "city": _to_bit(g("ver_guarantor_wna_spouse_city")),
                            "province": _to_bit(g("ver_guarantor_wna_spouse_province")),
                            "job": _to_bit(g("ver_guarantor_wna_spouse_job")),
                        })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA')
                        """), {"pid": prechecking_id, "nik": wna_sp_id, "nama": wna_sp_name,
                               "id_type": wna_spouse_id_type})

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
        current_app.logger.exception("submit_prechecking_guarantor error")
        return jsonify({"success": False, "message": "Database error"}), 500

_GUARANTOR_DOC_META: dict = {
    "guarantor-ktp":                          ("-GUARANTOR_KTP-",                        "DATA_GUARANTOR/KTP"),
    "guarantor-spouse-ktp":                   ("-GUARANTOR_SPOUSE_KTP-",                 "DATA_GUARANTOR/KTP"),
    "guarantor-kk":                           ("-GUARANTOR_KK-",                         "DATA_GUARANTOR/KK"),
    "guarantor-npwp":                         ("-GUARANTOR_NPWP-",                       "DATA_GUARANTOR/NPWP"),
    "guarantor-marriage-or-death-statement":  ("-GUARNTOR-MARRIAGE_OR_DEATH_STATEMENT-", "DATA_GUARANTOR/AKTA_CERAI_MATI"),
    "guarantor-kitas":                        ("-GUARANTOR_KITAS-",                      "DATA_GUARANTOR/KITAS"),
    "guarantor-spouse-kitas":                 ("-GUARANTOR_SPOUSE_KITAS-",               "DATA_GUARANTOR/KITAS_PASANGAN"),
    "guarantor-kitap":                        ("-GUARANTOR_KITAP-",                      "DATA_GUARANTOR/KITAP"),
    "guarantor-spouse-kitap":                 ("-GUARANTOR_SPOUSE_KITAP-",               "DATA_GUARANTOR/KITAP_PASANGAN"),
    "guarantor-wna-spouse-ktp":               ("-GUARANTOR_WNA_SPOUSE_KTP-",             "DATA_GUARANTOR/KTP_PASANGAN"),
}

@prechecking_guarantor_bp.route("/upload-document-guarantor", methods=["POST"])
@login_required
def upload_document_guarantor():

    username          = _username()
    apless            = request.form.get("apless", "")
    prechecking_id    = request.form.get("prechecking_id", "")
    document_type     = request.form.get("document_type", "")
    cust_type         = request.form.get("cust_type", "PR")
    organization_type = request.form.get("organization_type", "GUARNPR")

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    f          = request.files["file"]
    original   = f.filename or "upload"
    file_bytes = f.read()

    err = _validate_file(file_bytes, original)
    if err:
        return jsonify({"success": False, "message": err}), 400

    name_prefix, doc_subfolder = _GUARANTOR_DOC_META.get(
        document_type, (f"-{document_type.upper().replace('-', '_')}-", document_type)
    )

    doc_name = f"{prechecking_id}{name_prefix}{original}"

    aws_prefix = "upload_doc/guarantor"
    aws_key    = f"{aws_prefix}/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"

    content_type = mimetypes.guess_type(original)[0] or "application/octet-stream"

    try:
        replaced_types = _DOC_TYPE_SIBLINGS.get(document_type, (document_type,))
        placeholders = ", ".join(f":dtype_{i}" for i in range(len(replaced_types)))
        existing_params = {"pid": prechecking_id}
        existing_params.update({f"dtype_{i}": t for i, t in enumerate(replaced_types)})

        existing = db.session.execute(
            text(f"""
                SELECT CustomerDocumentId, AWSKey, DocumentName
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid
                  AND DocumentType IN ({placeholders})
                  AND Apless IS NOT NULL
            """),
            existing_params,
        ).fetchall()

        for old_doc in existing:
            if old_doc.AWSKey:
                _aws_delete(old_doc.AWSKey)

            db.session.execute(
                text("""
                    DELETE FROM TEMP_CUSTOMER_DOCUMENT
                    WHERE CustomerDocumentId = :doc_id
                """),
                {"doc_id": old_doc.CustomerDocumentId},
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
        current_app.logger.exception("upload_document_guarantor S3 error")
        return jsonify({"success": False, "message": f"S3 upload failed: {exc}"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document_guarantor error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_guarantor_bp.route("/documents-guarantor", methods=["GET"])
@login_required
def get_documents_guarantor():

    apless         = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id", "")

    try:
        rows = db.session.execute(
            text("""
                SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Apless = :apless
                  AND Prechecking_Id = :pid
                  AND Apless IS NOT NULL
                ORDER BY DocumentType, CreatedDate
            """),
            {"apless": apless, "pid": prechecking_id},
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
        current_app.logger.exception("get_documents_guarantor error")
        return jsonify([])

@prechecking_guarantor_bp.route("/view-document-guarantor", methods=["GET"])
@login_required
def view_document_guarantor():
    
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
        current_app.logger.exception("view_document_guarantor error")
        return jsonify({"success": False, "message": "Could not generate view link"}), 500

@prechecking_guarantor_bp.route("/delete-document-guarantor", methods=["POST"])
@login_required
def delete_document_guarantor():

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
        current_app.logger.exception("delete_document_guarantor error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_guarantor_bp.route("/cancel-guarantor", methods=["POST"])
@login_required
def cancel_prechecking_guarantor():

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
        current_app.logger.exception("cancel_prechecking_guarantor error")
        return jsonify({"success": False, "message": "Database error"}), 500