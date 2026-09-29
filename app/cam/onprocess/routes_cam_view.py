import re

from app import db
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote
from html import unescape

from flask import Blueprint, jsonify, request, current_app, session, redirect
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import _aws_presign
from sqlalchemy import text

cam_view_bp = Blueprint("cam_view", __name__, url_prefix="/CAM/View")

INDO_MONTHS = {
    "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
    "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
    "09": "September", "10": "Oktober", "11": "November", "12": "Desember",
}

def bulan(mm: str) -> str:
    return INDO_MONTHS.get(str(mm).zfill(2), str(mm))

def _fmt_date(value, fmt="%d-%m-%Y"):
    if not value:
        return ""
    try:
        return value.strftime(fmt)
    except Exception:
        return ""

def _fmt_validity(value):
    if value:
        formatted = _fmt_date(value)
        if formatted:
            return formatted
    return "No Expire date"

def _dash(v):
    return v if v not in (None, "") else "-"

def _npwp_format(npwp):
    if not npwp:
        return "-"
    n = str(npwp)
    try:
        return f"{n[0:2]}.{n[2:5]}.{n[5:8]}.{n[8:9]}-{n[9:12]}.{n[12:16]}"
    except Exception:
        return n

def _fax_suffix(fax):
    return f" - (F) {fax}" if fax else ""

def _build_download_url(aws_key, file_name):
    if not aws_key:
        return None
    return f"/CAM/View/files/download?key={quote(str(aws_key), safe='')}&name={quote(str(file_name or ''), safe='')}"

def _lookup_combo(cat_value, value):
    if not value:
        return value
    row = db.session.execute(
        text("SELECT DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE=:cat AND VALUE=:val"),
        {"cat": cat_value, "val": value}
    ).mappings().first()
    return row["DESC_VALUE"] if row else value

CUSTOMER_DETAIL_SQL = """
SELECT
    a.LESSEE_NM, a.ADDRESS1, a.ADDRESS4, a.CITY4, a.PHONE4, a.ZipCode4, a.Fax4, a.ADDRESS3, a.CITY3,
    a.PHONE3, a.ZipCode3, a.Fax3, a.ADDRESS5, a.CITY5, a.PHONE5, a.ZipCode5, a.Fax5, a.CITY1, a.ZipCode1, a.PHONE1, a.PHONE2,
    a.Mobile_phone1, a.Mobile_phone2, a.Mobile_phone3, a.EMAIL1, a.EMAIL2, a.NPWP, a.Fax1, a.Spouse, a.Mother, a.PLACEBIRTH, a.TGLBIRTH,
    a.Citizen, m.Name as Nationality, a.ID_CARD, a.Id_Card_Valid, a.FAM_CARD, a.OTHER_PHONE1, a.OTHER_PHONE2, a.OTHER_PHONENOTES1,
    a.OTHER_PHONENOTES2, b.name AS homestatus, c.NAME AS custtype, case when d.FLGDEL = '1' then '-' else d.GrpName end as GrpName,
    case when a.GENDER='M' then 'Male' else 'Female' end as gender, f.name AS marital, g.name AS religion, i.MLCI_Desc, mi.Descrip,
    j.CONFIRM_STS, a.ALIAS_NAME,
    L.Fullname_Without_Title, L.BUSINESS_ENTITY, L.GO_PUBLIC, L.RELATIONSHIP,
    L.PASSPORTNO, q.DESC_VALUE as LAST_EDUCATION, L.CAREER_FIELD, L.SPOUSE_PLACEBIRTH, L.SPOUSE_TGLBIRTH, L.SPOUSE_CITIZEN,
    n.Name as SPOUSE_NATIONALITY, L.SPOUSE_ID_CARD, L.SPOUSE_Id_CARD_VALID, L.SPOUSE_PASSPORTNO, L.SPOUSE_MARRIAGE, L.SPOUSE_DEPENDENT,
    o.EMERGENCY_NAME, o.EMERGENCY_ADDRESS, o.EMERGENCY_PHONE, o.EMERGENCY_RELATION, o.Address_NPWP, p.KABUPATEN as Area_CD_NPWP, o.Zipcode_NPWP, L.SPOUSE_Fullname_Without_Title, r.Desc_Name as Kecamatan, s.Desc_Name as Kelurahan,
    t.Desc_Name as Kecamatan_NPWP, u.Desc_Name as Kelurahan_NPWP, o.RT, o.RW, L.Live_since AS years_live, L.SPOUSE_MobilePhone, L.SPOUSE_Email
FROM
    CAFLESS a WITH (NOLOCK)
    LEFT JOIN MSTADDRESSSTATUS b WITH (NOLOCK) ON a.Address_Status=b.AddressStatus
    LEFT JOIN MSTLESSEETYPE c WITH (NOLOCK) ON a.Lessee_Cat=c.CUST_TYPE AND c.LESSEE_TP='PR'
    LEFT JOIN CLFGROUP d WITH (NOLOCK) ON a.GrpCode=d.GrpCode
    LEFT JOIN MSTMARITAL f WITH (NOLOCK) ON a.MARITAL=f.Marital
    LEFT JOIN MSTRELIGION g WITH (NOLOCK) ON a.RELIGION=g.Religion
    LEFT JOIN MstIndustry_lbpp mi WITH (NOLOCK) ON a.INDUS_CODE=mi.MLCI_CODE AND a.INDUS_CODE<>''
    LEFT JOIN UMFBITYP_LBPP i WITH (NOLOCK) ON a.Cust_Type=i.OJK_Code
    LEFT JOIN MCMOCRSURVEY j WITH (NOLOCK) ON a.APLESS=j.APLESS
    LEFT JOIN CAFLESS_DETAIL L WITH (NOLOCK) ON L.APLESS=a.APLESS
    LEFT JOIN Mst_Country m WITH (NOLOCK) ON m.ID2digit=a.Nationality
    LEFT JOIN Mst_Country n WITH (NOLOCK) ON n.ID2digit=L.SPOUSE_NATIONALITY
    LEFT JOIN CAFLESS_DETAIL_ADDRESS o WITH (NOLOCK) ON a.apless=o.apless
    LEFT JOIN UMFAREA p WITH (NOLOCK) ON p.Area_CD=o.Area_CD_NPWP
    LEFT JOIN MSTCOMBO q WITH (NOLOCK) ON L.LAST_EDUCATION=q.VALUE AND q.CAT_VALUE='LAST_EDU'
    LEFT JOIN Mst_Kecamatan r WITH (NOLOCK) ON o.KECAMATAN = r.Kecamatan_CD
    LEFT JOIN Mst_Kelurahan s WITH (NOLOCK) ON o.KELURAHAN = s.Kelurahan_CD
    LEFT JOIN Mst_Kecamatan t WITH (NOLOCK) ON o.Kecamatan_NPWP=t.Kecamatan_CD
    LEFT JOIN Mst_Kelurahan u WITH (NOLOCK) ON o.Kelurahan_NPWP=u.Kelurahan_CD
WHERE a.APLESS=:apless
"""

def _customer_documents(apless, applno):
    rows = db.session.execute(
        text("""
            SELECT id_customer_document, AWSKey, a.file_document, DocumentType
            FROM CUSTOMER_DOCUMENT a WITH (NOLOCK)
                LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.appl_no = b.APPL_NO
            WHERE a.doc_type='non' AND a.APPL_NO=:applno AND a.APLESS=:apless AND a.APLESS IS NOT NULL
            ORDER BY DocumentType, Upload_Dt DESC
        """),
        {"applno": applno, "apless": apless}
    ).mappings().all()

    buckets = {}
    for r in rows:
        name = r["file_document"]
        if not name or name == "-":
            continue
        buckets.setdefault(r["DocumentType"], []).append({
            "id": r["id_customer_document"],
            "name": name,
            "download_url": _build_download_url(r["AWSKey"], name),
        })
    return buckets

def _build_document_groups(buckets, citizen, spouse_citizen):
    def files_for(key):
        return buckets.get(key, [])

    groups = []

    if citizen == "WNI":
        groups.append({"header": "WNI", "rows": [
            {"key": "cust-spouse-kk", "label": "Customer's Spouse Family Card", "files": files_for("cust-spouse-kk")},
        ]})
    elif citizen == "WNA":
        groups.append({"header": "WNA", "rows": [
            {"key": "cust-kitas", "label": "KITAS/KITAP a/n Pelanggan", "files": files_for("cust-kitas")},
            {"key": "cust-spouse-kitas", "label": "KITAS/KITAP a/n Suami/Istri Pelanggan", "files": files_for("cust-spouse-kitas")},
            {"key": "cust-family-tree", "label": "SK. Susunan Keluarga Pendatang (SKSP) WNA", "files": files_for("cust-family-tree")},
            {"key": "cust-reference", "label": "Surat Referensi Kerja dari Perusahaan WNA Bekerja", "files": files_for("cust-reference")},
        ]})

    groups.append({"header": "Dokumen Tambahan", "rows": [
        {"key": "cust-salary-receipt", "label": "Salary Receipt", "files": files_for("cust-salary-receipt")},
    ]})

    groups.append({"header": "BPKB Document", "rows": [
        {"key": "cust-ktp-bpkb", "label": "BPKB ID", "files": files_for("cust-ktp-bpkb")},
        {"key": "cust-kk-bpkb", "label": "BPKB Family Card", "files": files_for("cust-kk-bpkb")},
    ]})

    groups.append({"header": None, "rows": [
        {"key": "cust-other", "label": "Other", "files": files_for("cust-other")},
    ]})

    if spouse_citizen == "WNA":
        spouse_bucket_key, spouse_bucket_label = "cust-spouse-kitas", "Spouse ID Card"
    elif citizen == "WNA":
        spouse_bucket_key, spouse_bucket_label = "cust-wna-spouse-ktp", "Spouse ID Card"
    else:
        spouse_bucket_key, spouse_bucket_label = "cust-spouse-ktp", "Spouse ID Card"

    groups.append({"header": "Individual Document", "rows": [
        {"key": "cust-ktp", "label": "ID Card", "files": files_for("cust-ktp")},
        {"key": spouse_bucket_key, "label": spouse_bucket_label, "files": files_for(spouse_bucket_key)},
        {"key": "cust-kk", "label": "KK", "files": files_for("cust-kk")},
        {"key": "cust-npwp", "label": "NPWP", "files": files_for("cust-npwp")},
        {"key": "cust-spk", "label": "SPK", "files": files_for("cust-spk")},
        {"key": "marriage-or-death-statement", "label": "Marriage/ Death/ Divorce/ Prenuptial Statement",
         "files": files_for("marriage-or-death-statement")},
    ]})

    show_section = any(row["files"] for g in groups for row in g["rows"])
    return groups, show_section

@cam_view_bp.route("/customer-detail")
@login_required
def get_customer_detail():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless:
        return jsonify({"error": "Missing apless"}), 400

    try:
        row = db.session.execute(text(CUSTOMER_DETAIL_SQL), {"apless": apless}).mappings().first()
        if not row:
            return jsonify({"error": "Not found"}), 404

        citizen = row["Citizen"] or ""
        spouse_citizen = row["SPOUSE_CITIZEN"] or ""

        kecamatan = (row["Kecamatan"] or "").upper()
        kelurahan = (row["Kelurahan"] or "").upper()

        id_card_address = None
        if row["ADDRESS1"]:
            id_card_address = {
                "address_line": f"{row['ADDRESS1']}, RT. {row['RT'] or ''}/{row['RW'] or ''}, "
                                 f"{kelurahan}, {kecamatan}, {row['CITY1'] or ''} {row['ZipCode1'] or ''}",
                "contact_line": f"(P) {row['PHONE2'] or ''}{_fax_suffix(row['Fax1'])}",
            }

        correspondence = None
        if row["ADDRESS3"]:
            correspondence = {
                "address_line": f"{row['ADDRESS3']}, {row['CITY3'] or ''} {row['ZipCode3'] or ''}",
                "contact_line": f"(P) {row['PHONE3'] or ''}{_fax_suffix(row['Fax3'])}",
            }

        additional1 = None
        if row["ADDRESS4"]:
            additional1 = {
                "address_line": f"{row['ADDRESS4']}, {row['CITY4'] or ''} {row['ZipCode4'] or ''}",
                "contact_line": f"(P) {row['PHONE4'] or ''}{_fax_suffix(row['Fax4'])}",
            }

        additional2 = None
        if row["ADDRESS5"]:
            additional2 = {
                "address_line": f"{row['ADDRESS5']}, {row['CITY5'] or ''} {row['ZipCode5'] or ''}",
                "contact_line": f"(P) {row['PHONE5'] or ''}{_fax_suffix(row['Fax5'])}",
            }

        npwp_address_line = "-"
        if row["Address_NPWP"]:
            npwp_address_line = (
                f"{row['Address_NPWP']}, {row['Kelurahan_NPWP'] or ''}, {row['Kecamatan_NPWP'] or ''}, "
                f"{row['Area_CD_NPWP'] or ''} {row['Zipcode_NPWP'] or ''}"
            )

        mobile = ", ".join(p for p in [row["Mobile_phone1"], row["Mobile_phone2"], row["Mobile_phone3"]] if p) or "-"
        email = ", ".join(p for p in [row["EMAIL1"], row["EMAIL2"]] if p) or "-"

        years_live = row["years_live"]
        total_year = None
        if years_live not in (None, ""):
            try:
                total_year = datetime.now().year - int(years_live)
            except (ValueError, TypeError):
                total_year = None

        ref_rows = db.session.execute(
            text("SELECT REF_NAME, REF_PHONE, REMARK FROM CAFREF WITH (NOLOCK) WHERE APLESS=:apless"),
            {"apless": apless}
        ).mappings().all()
        references = [
            {"no": i + 1, "name": r["REF_NAME"] or "", "phone": r["REF_PHONE"] or "", "remark": r["REMARK"] or ""}
            for i, r in enumerate(ref_rows)
        ]

        buckets = _customer_documents(apless, applno)
        document_groups, show_documents = _build_document_groups(buckets, citizen, spouse_citizen)

        return jsonify({
            "lessee_nm": row["LESSEE_NM"] or "",
            "alias_nm": row["ALIAS_NAME"] or "",
            "idcard_name": row["Fullname_Without_Title"] or "",
            "cust_type": _dash(row["custtype"]),
            "id_card_address": id_card_address,
            "years_lived": total_year,
            "whatsapp": row["Mobile_phone1"] or "",
            "mobile": mobile,
            "email": email,
            "npwp_formatted": _npwp_format(row["NPWP"]),
            "correspondence": correspondence,
            "npwp_address": npwp_address_line,
            "additional1": additional1,
            "additional2": additional2,
            "group_name": _dash(row["GrpName"]),
            "mother_maiden_name": _dash(row["Mother"]),
            "place_of_birth": _dash(row["PLACEBIRTH"]),
            "date_of_birth": _fmt_date(row["TGLBIRTH"]),
            "gender": _dash(row["gender"]),
            "marital_status": _dash(row["marital"]),
            "religion": _dash(row["religion"]),
            "id_card_no": _dash(row["ID_CARD"]),
            "id_card_validity": _fmt_validity(row["Id_Card_Valid"]),
            "citizenship": _dash(citizen),
            "nationality": _dash(row["Nationality"]),
            "passport_no": row["PASSPORTNO"] or "",
            "family_card_no": _dash(row["FAM_CARD"]),
            "other_phone1": row["OTHER_PHONE1"] or "",
            "other_phone1_notes": row["OTHER_PHONENOTES1"] or "",
            "other_phone2": row["OTHER_PHONE2"] or "",
            "other_phone2_notes": row["OTHER_PHONENOTES2"] or "",
            "last_education": row["LAST_EDUCATION"] or "",
            "career_field": _lookup_combo("CAREER_FIELD", row["CAREER_FIELD"]) or "",
            "industrial_code": _dash(row["Descrip"]),
            "bi_customer_type": row["MLCI_Desc"] or "",
            "emergency": {
                "name": row["EMERGENCY_NAME"] or "",
                "address": row["EMERGENCY_ADDRESS"] or "",
                "phone": row["EMERGENCY_PHONE"] or "",
                "relation": row["EMERGENCY_RELATION"] or "",
            },
            "spouse": {
                "name_id_card": _dash(row["Spouse"]),
                "name_without_title": _dash(row["SPOUSE_Fullname_Without_Title"]),
                "mobile_phone": row["SPOUSE_MobilePhone"] or "",
                "email": row["SPOUSE_Email"] or "",
                "place_of_birth": row["SPOUSE_PLACEBIRTH"] or "",
                "date_of_birth": _fmt_date(row["SPOUSE_TGLBIRTH"]),
                "citizenship": spouse_citizen,
                "nationality": row["SPOUSE_NATIONALITY"] or "",
                "id_card_no": row["SPOUSE_ID_CARD"] or "",
                "id_card_validity": _fmt_validity(row["SPOUSE_Id_CARD_VALID"]),
                "passport_no": row["SPOUSE_PASSPORTNO"] or "",
                "marriage_agreement": "Yes" if row["SPOUSE_MARRIAGE"] == "1" else "No",
                "total_dependent": row["SPOUSE_DEPENDENT"] or "",
                "relationship": _lookup_combo("RELATIONSHIP_MLCI", row["RELATIONSHIP"]) or "",
            },
            "references": references,
            "citizen": citizen,
            "document_groups": document_groups,
            "show_documents": show_documents,
        })

    except Exception:
        current_app.logger.exception("CAM customer detail error")
        return jsonify({"error": "Failed to load data"}), 500

def _phone_fax(phone, fax):
    phone_part = f"(P) {phone}" if phone else "-"
    return phone_part + _fax_suffix(fax)

def _addr_block(address, city, zipcode):
    if not address:
        return "-"
    tail = city or ""
    if zipcode:
        tail = f"{tail}, {zipcode}" if tail else f", {zipcode}"
    return f"{address}\n{tail}" if tail else address

def _money0(value):
    if value in (None, ""):
        return "0"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "0"

GUARANTOR_DETAIL_SQL = """
SELECT
    a.GRNNAME, a.GRNDOB, a.GRNADD, a.GRNCITY, a.GRNPHONE, a.GRNRELATION,
    a.GRNOCCUPATION, a.GRNTTL, a.GRNIDCARD, a.GRNIDVAL, a.GRNZIPCODE, a.GRNFAX,
    a.GRNLOB, a.GRNContact, a.CON_SIGNPOS, a.GRNSpouse, a.GRNStatus, a.GRNSPOUSEADD, a.GRNSPOUSECITY,
    a.GRNSPOUSECODE, b.Name AS guarntype, c.Name AS guarncat, a.GRNNAME_WITHOUT_TITLE, a.GRNPASSPORTNO, a.GRNCITIZEN,
    d.Name AS GRNNATIONALITY, a.GRNNPWP, e.MLCI_Desc AS GRN_BITYPE, a.GRNNAME_NPWP, a.GRNCITY_NPWP, a.GRNZIPCODE_NPWP,
    a.GRNADD_NPWP, f.DESC_VALUE AS Gender, g.name AS Marital, a.GRNSPOUSEIDCARD, a.GRNEMAIL, a.GRNSpouseMobilePhone,
    a.GRNSpouseEmail, a.GRNConSignerMobilePhone, a.GRNConSignerEmail, a.GRNSpouseCitizenship, dd.Name AS GRNSpouseNationality
FROM
    CAFGUARN a WITH (NOLOCK)
    LEFT JOIN MSTTYPE b WITH (NOLOCK) ON a.GRNTP=b.Grnttp
    LEFT JOIN MSTCATEGORY c WITH (NOLOCK) ON a.GRNCAT=c.Code
    LEFT JOIN Mst_Country d WITH (NOLOCK) ON d.ID2digit=a.GRNNATIONALITY
    LEFT JOIN Mst_Country dd WITH (NOLOCK) ON dd.ID2digit=a.GRNSpouseNationality
    LEFT JOIN UMFBITYP_lbpp e WITH (NOLOCK) ON e.OJK_Code=a.GRN_BITYPE
    LEFT JOIN MSTCOMBO f WITH (NOLOCK) ON f.VALUE=a.Gender AND f.CAT_VALUE='Gender'
    LEFT JOIN mstmarital g WITH (NOLOCK) ON g.Marital=a.Marital
WHERE a.APPL_NO=:applno AND a.GRNID=:grnid AND a.APLESS=:apless
"""

def _guarantor_documents(applno, grnid):
    rows = db.session.execute(
        text("""
            SELECT id_customer_document, AWSKey, a.file_document, DocumentType
            FROM CUSTOMER_DOCUMENT a WITH (NOLOCK)
                LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.appl_no = b.APPL_NO
            WHERE a.doc_type='guarn' AND a.APPL_NO=:applno AND a.GRNID=:grnid AND a.APLESS IS NOT NULL
            ORDER BY DocumentType, Upload_Dt DESC
        """),
        {"applno": applno, "grnid": grnid}
    ).mappings().all()

    buckets = {}
    for r in rows:
        name = r["file_document"]
        if not name or name == "-":
            continue
        buckets.setdefault(r["DocumentType"], []).append({
            "id": r["id_customer_document"],
            "name": name,
            "download_url": _build_download_url(r["AWSKey"], name),
        })
    return buckets

def _guarantor_bank_statement_files(applno, grnid):
    rows = db.session.execute(
        text("""
            SELECT Id, DocumentName, AWSKey
            FROM GUARANTOR_BANK_STATEMENT_DOCUMENT WITH (NOLOCK)
            WHERE appl_no=:applno AND GuarantorId=:grnid
            ORDER BY CreatedDate DESC
        """),
        {"applno": applno, "grnid": grnid}
    ).mappings().all()

    files = []
    for r in rows:
        name = r["DocumentName"]
        if not name:
            continue
        files.append({
            "id": r["Id"],
            "name": name,
            "download_url": _build_download_url(r["AWSKey"], name),
        })
    return files

def _build_guarantor_document_rows_pr(buckets):
    rows = [
        ("guarantor-spouse-kk", "Kartu Keluarga a/n Suami/Istri Penjamin"),
        ("guarantor-ktp", "KTP a/n Penjamin"),
        ("guarantor-spouse-ktp", "KTP a/n Suami/Istri Penjamin"),
        ("guarantor-kk", "Kartu Keluarga a/n Penjamin"),
        ("guarantor-npwp", "NPWP a/n Penjamin"),
        ("guarantor-marriage-or-death-statement", "Akta Cerai/Mati a/n Penjamin"),
    ]
    return [{"key": key, "label": label, "files": buckets.get(key, [])} for key, label in rows]

def _build_guarantor_document_rows_pt(buckets):
    rows = [
        ("corp-guarantor-kk", "Kartu Keluarga a/n Pemegang Saham (jika ada)"),
        ("corp-guarantor-akta", "Akta Pendirian"),
        ("corp-guarantor-sk-akta", "SK Kemenkumham Akta Pendirian"),
        ("corp-guarantor-akta-terakhir", "Akta Perubahan Terakhir"),
        ("corp-guarantor-sk-akta-terakhir", "SK Kemenkumham atas Akta Perubahan Terakhir"),
    ]
    result = [{"key": key, "label": label, "files": buckets.get(key, [])} for key, label in rows]

    def _index_of(key):
        tail = key.rsplit("_", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    ocr_keys = sorted((k for k in buckets if k.startswith("corp-guarantor-ocr-ktp_")), key=_index_of)
    board_keys = sorted((k for k in buckets if k.startswith("wna-corp-guarantor-board_")), key=_index_of)

    dynamic_groups = [{"key": k, "files": buckets[k]} for k in ocr_keys]
    dynamic_groups += [{"key": k, "files": buckets[k]} for k in board_keys]
    if buckets.get("corp-ktp-akta-terakhir"):
        dynamic_groups.append({"key": "corp-ktp-akta-terakhir", "files": buckets["corp-ktp-akta-terakhir"]})

    result.append({
        "key": "corp-guarantor-ktp-pengurus",
        "label": "KTP Pengurus atas Akta Perubahan Terakhir",
        "files": [],
        "dynamic_groups": dynamic_groups,
    })
    result.append({"key": "corp-guarantor-npwp", "label": "NPWP", "files": buckets.get("corp-guarantor-npwp", [])})
    return result

@cam_view_bp.route("/guarantor-list")
@login_required
def get_guarantor_list():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        rows = db.session.execute(
            text("""
                SELECT GRNID, GRNNAME, GRNTP, GRNOCCUPATION, GRNRELATION
                FROM CAFGUARN WITH (NOLOCK)
                WHERE APPL_NO=:applno
                ORDER BY GRNID
            """),
            {"applno": applno}
        ).mappings().all()

        guarantors = [
            {
                "grnid": r["GRNID"],
                "name": r["GRNNAME"] or "",
                "type": r["GRNTP"] or "",
                "occupation": r["GRNOCCUPATION"] or "",
                "relation": r["GRNRELATION"] or "",
            }
            for r in rows
        ]
        return jsonify({"guarantors": guarantors, "no_data": len(guarantors) == 0})
    except Exception:
        current_app.logger.exception("CAM guarantor list error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/guarantor-detail")
@login_required
def get_guarantor_detail():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    grnid = request.args.get("grnid", "")
    grntp = request.args.get("grntp", "")
    if not (apless and applno and grnid):
        return jsonify({"error": "Missing apless/applno/grnid"}), 400

    try:
        row = db.session.execute(
            text(GUARANTOR_DETAIL_SQL), {"apless": apless, "applno": applno, "grnid": grnid}
        ).mappings().first()
        if not row:
            return jsonify({"error": "Not found"}), 404

        common = {
            "guarantor_type": grntp,
            "type_label": row["guarntype"] or "",
            "category": row["guarncat"] or "",
            "npwp": _npwp_format(row["GRNNPWP"]),
            "bi_customer_type": row["GRN_BITYPE"] or "",
        }

        if grntp == "PT":
            summary = {
                **common,
                "name_akta": row["GRNNAME"] or "",
                "name_npwp": row["GRNNAME_NPWP"] or "",
                "name_without_title": f"{row['GRNNAME_WITHOUT_TITLE'] or ''} - {row['guarncat'] or ''}",
                "establishment_date": _fmt_date(row["GRNDOB"]),
                "address_sk_domisili": _addr_block(row["GRNADD"], row["GRNCITY"], row["GRNZIPCODE"]),
                "pic_phone_fax": _phone_fax(row["GRNPHONE"], row["GRNFAX"]),
                "address_npwp": (
                    f"{row['GRNADD_NPWP']}, {row['GRNCITY_NPWP'] or ''}, {row['GRNZIPCODE_NPWP'] or ''}"
                    if row["GRNADD_NPWP"] else "-"
                ),
                "line_of_business": row["GRNLOB"] or "-",
                "relationship": row["GRNRELATION"] or "-",
                "total_exposure": _money0(row["GRNTTL"]),
                "contract_signer": row["GRNContact"] or "-",
                "contract_signer_position": row["CON_SIGNPOS"] or "-",
                "contract_signer_id_card": row["GRNIDCARD"] or "-",
                "contract_signer_mobile": row["GRNConSignerMobilePhone"] or "-",
                "contract_signer_email": row["GRNConSignerEmail"] or "-",
                "contract_signer_citizenship": f"{row['GRNCITIZEN'] or ''} / {row['GRNNATIONALITY'] or ''}",
            }
        else:
            summary = {
                **common,
                "name_id_card": row["GRNNAME"] or "",
                "name_without_title": f"{row['GRNNAME_WITHOUT_TITLE'] or ''} - {row['guarncat'] or ''}",
                "marital_status": row["Marital"] or "",
                "spouse_name": row["GRNSpouse"] or "-",
                "spouse_status": row["GRNStatus"] or "",
                "gender": row["Gender"] or "",
                "spouse_id_card_no": row["GRNSPOUSEIDCARD"] or "",
                "date_of_birth": _fmt_date(row["GRNDOB"]),
                "spouse_address": _addr_block(row["GRNSPOUSEADD"], row["GRNSPOUSECITY"], row["GRNSPOUSECODE"]),
                "address": _addr_block(row["GRNADD"], row["GRNCITY"], row["GRNZIPCODE"]),
                "spouse_citizenship": f"{row['GRNSpouseCitizenship'] or ''} / {row['GRNSpouseNationality'] or ''}",
                "phone_fax": _phone_fax(row["GRNPHONE"], row["GRNFAX"]),
                "spouse_mobile": row["GRNSpouseMobilePhone"] or "",
                "email": row["GRNEMAIL"] or "",
                "spouse_email": row["GRNSpouseEmail"] or "",
                "relationship": row["GRNRELATION"] or "",
                "occupation": row["GRNOCCUPATION"] or "",
                "total_exposure": _money0(row["GRNTTL"]),
                "citizenship": f"{row['GRNCITIZEN'] or ''} / {row['GRNNATIONALITY'] or ''}",
                "id_card_no": row["GRNIDCARD"] or "",
                "id_card_validity": _fmt_validity(row["GRNIDVAL"]),
                "passport_no": row["GRNPASSPORTNO"] or "",
            }

        buckets = _guarantor_documents(applno, grnid)
        document_rows = (
            _build_guarantor_document_rows_pt(buckets) if grntp == "PT"
            else _build_guarantor_document_rows_pr(buckets)
        )
        show_documents = any(r["files"] or r.get("dynamic_groups") for r in document_rows)

        return jsonify({
            "summary": summary,
            "documents": document_rows,
            "show_documents": show_documents,
            "bank_statement_files": _guarantor_bank_statement_files(applno, grnid),
        })
    except Exception:
        current_app.logger.exception("CAM guarantor detail error")
        return jsonify({"error": "Failed to load data"}), 500

def _get_dscr(apless, period):
    if not period:
        return "0"
    amt = db.session.execute(
        text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE PERIOD=:p AND APLESS=:apless AND ITEM_CODE='500101'"),
        {"p": period, "apless": apless}
    ).scalar()
    return f"{float(amt):.2f}" if amt else "0"

def _individual_finance(apless, applno):
    period1 = db.session.execute(
        text("SELECT TOP 1 PERIOD FROM CAFFS WITH (NOLOCK) WHERE APLESS=:apless "
             "AND [PERIOD] <= (SELECT YEAR(CREATE_DATE) FROM CAFCONT WHERE APPL_NO=:applno) "
             "AND FS_CODE='I' GROUP BY PERIOD ORDER BY PERIOD DESC"),
        {"apless": apless, "applno": applno}
    ).scalar()

    if not period1:
        return {"no_data": True}

    curr_code = db.session.execute(
        text("SELECT FS_Curr FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:apless"),
        {"apless": apless}
    ).scalar() or "IDR"

    liab_rows = db.session.execute(
        text("SELECT AMOUNT, NOTES, [DESC] FROM CAFLA WITH (NOLOCK) WHERE PERIOD=:p AND APLESS=:apless AND LA_CODE='L'"),
        {"p": period1, "apless": apless}
    ).mappings().all()
    liabilities = [{"category": r["NOTES"] or "", "description": r["DESC"] or "", "amount": float(r["AMOUNT"] or 0)} for r in liab_rows]
    tot_l = sum(r["amount"] for r in liabilities)

    income_items, tot_income = [], 0.0
    for ic in db.session.execute(
        text("SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK) WHERE FS_CODE LIKE '3101%' ORDER BY FS_CODE")
    ).mappings().all():
        amt = db.session.execute(
            text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='I' AND PERIOD=:p AND APLESS=:apless AND ITEM_CODE=:item"),
            {"p": period1, "apless": apless, "item": ic["FS_CODE"]}
        ).scalar() or 0
        income_items.append({"label": ic["FS_DESC"], "amount": float(amt)})
        tot_income += float(amt)

    expense_items, expense_total = [], 0.0
    for ec in db.session.execute(
        text("SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK) WHERE FS_CODE LIKE '3102%' ORDER BY FS_CODE")
    ).mappings().all():
        amt = db.session.execute(
            text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='I' AND PERIOD=:p AND APLESS=:apless AND ITEM_CODE=:item"),
            {"p": period1, "apless": apless, "item": ec["FS_CODE"]}
        ).scalar() or 0
        expense_items.append({"label": ec["FS_DESC"], "amount": float(amt)})
        expense_total += float(amt)

    net_saving = tot_income - expense_total - tot_l

    asset_rows = db.session.execute(
        text("SELECT AMOUNT, [DESC], NOTES FROM CAFLA WITH (NOLOCK) WHERE PERIOD=:p AND APLESS=:apless AND LA_CODE='A'"),
        {"p": period1, "apless": apless}
    ).mappings().all()
    assets = [{"description": r["DESC"] or "", "amount": float(r["AMOUNT"] or 0), "notes": r["NOTES"] or ""} for r in asset_rows]
    tot_a = sum(r["amount"] for r in assets)

    return {
        "no_data": False,
        "period_label": period1,
        "currency": curr_code,
        "liabilities": {"rows": liabilities, "total": tot_l},
        "income": {
            "income_items": income_items, "total_income": tot_income,
            "expense_items": expense_items, "liabilities_total": tot_l,
            "net_saving": net_saving,
        },
        "dscr": _get_dscr(apless, period1),
        "assets": {"rows": assets, "total": tot_a},
    }

def _build_balance_sheet_section(apless, period_a, period_b, code_lower, code_upper, skip_total_for_prefix):
   
    sections = []
    grand_a = grand_b = 0.0

    prefixes = db.session.execute(
        text("SELECT SUBSTRING(FS_CODE, 1, 4) AS kode FROM MSTFS WITH (NOLOCK) "
             "WHERE FS_CODE >= :lo AND FS_CODE < :hi GROUP BY SUBSTRING(FS_CODE, 1, 4)"),
        {"lo": code_lower, "hi": code_upper}
    ).mappings().all()

    for p in prefixes:
        prefix = p["kode"]
        items = db.session.execute(
            text("SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK) "
                 "WHERE FS_CODE >= :lo AND FS_CODE < :hi AND FS_CODE LIKE :pat ORDER BY FS_CODE"),
            {"lo": code_lower, "hi": code_upper, "pat": f"{prefix}%"}
        ).mappings().all()

        header, rows = "", []
        subtotal_a = subtotal_b = 0.0

        for item in items:
            fs_code, fs_desc = item["FS_CODE"], item["FS_DESC"]
            if fs_code[4:6] == "00":
                header = fs_desc
                continue

            amt_a = db.session.execute(
                text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='B' AND PERIOD=:p AND APLESS=:apless AND ITEM_CODE=:item"),
                {"p": period_a, "apless": apless, "item": fs_code}
            ).scalar() or 0
            amt_b = db.session.execute(
                text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='B' AND PERIOD=:p AND APLESS=:apless AND ITEM_CODE=:item"),
                {"p": period_b, "apless": apless, "item": fs_code}
            ).scalar() or 0

            rows.append({"label": fs_desc, "amount_a": float(amt_a), "amount_b": float(amt_b)})
            subtotal_a += float(amt_a)
            subtotal_b += float(amt_b)

        grand_a += subtotal_a
        grand_b += subtotal_b
        sections.append({
            "header": header, "rows": rows,
            "subtotal_a": subtotal_a, "subtotal_b": subtotal_b,
            "show_subtotal": prefix != skip_total_for_prefix,
        })

    return sections, grand_a, grand_b

def _period_label_query(apless, dates, fs_code):
    return db.session.execute(
        text("""
            SELECT TOP 2 PERIOD,
                   CASE WHEN LEN(PERIOD) > 4
                        THEN CONVERT(CHAR(3), UPPER(DATENAME(MONTH, SUBSTRING(PERIOD,1,4)+'-'+SUBSTRING(PERIOD,5,2)+'-1'))) + ' - ' + SUBSTRING(PERIOD,1,4)
                        ELSE PERIOD END AS periode
            FROM CAFFS WITH (NOLOCK)
            WHERE APLESS=:apless
                AND PERIOD <= :dates AND FS_CODE=:fs_code
            GROUP BY PERIOD
            ORDER BY PERIOD DESC
        """),
        {"apless": apless, "dates": dates, "fs_code": fs_code}
    ).mappings().all()

def _corporate_finance(apless, applno, dates):
    bs_periods = _period_label_query(apless, dates, "B")
    period1 = period2 = None
    periode1 = periode2 = None
    if len(bs_periods) >= 1:
        period2, periode2 = bs_periods[0]["PERIOD"], bs_periods[0]["periode"]
    if len(bs_periods) >= 2:
        period1, periode1 = bs_periods[1]["PERIOD"], bs_periods[1]["periode"]

    pl_periods = _period_label_query(apless, dates, "P")[:1]
    period3 = pl_periods[0]["PERIOD"] if pl_periods else None
    periode3 = pl_periods[0]["periode"] if pl_periods else None

    if not period1 and not period2 and not period3:
        return {"no_data": True}

    asset_sections, asset_total1, asset_total2 = _build_balance_sheet_section(
        apless, period1, period2, "", "120000", "1100"
    )
    liability_sections, liab_total1, liab_total2 = _build_balance_sheet_section(
        apless, period1, period2, "120000", "210000", "1200"
    )

    BOLD_CODES = {"210103", "210301", "210501", "210701", "210901"}
    pl_rows = []
    for r in db.session.execute(
        text("SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK) WHERE FS_CODE >= '210101' AND FS_CODE <= '210901' ORDER BY FS_CODE")
    ).mappings().all():
        fs_code = r["FS_CODE"]
        amt = db.session.execute(
            text("SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='P' AND PERIOD=:p AND APLESS=:apless AND ITEM_CODE=:item"),
            {"p": period3, "apless": apless, "item": fs_code}
        ).scalar() or 0
        pl_rows.append({
            "fs_code": fs_code, "label": r["FS_DESC"], "amount": float(amt),
            "bold": fs_code in BOLD_CODES, "section_header": fs_code == "210201",
        })

    return {
        "no_data": False,
        "balance_sheet": {
            "period_label_1": periode1, "period_label_2": periode2,
            "asset_sections": asset_sections, "asset_total1": asset_total1, "asset_total2": asset_total2,
            "liability_sections": liability_sections, "liability_total1": liab_total1, "liability_total2": liab_total2,
        },
        "profit_loss": {"period_label": periode3, "rows": pl_rows},
        "dscr": _get_dscr(apless, period3),
    }

def _bank_accounts(apless, applno):
    accounts = db.session.execute(
        text("""
            SELECT a.Bank, a.ACC_No, a.ACC_Nm, a.Curr_code,
                   CASE WHEN b.[DESC] IS NULL THEN a.Bank ELSE b.[DESC] END AS bank_name,
                   a.NOTES_REK, a.Bank_Branch
            FROM CAFBANKSTM a WITH (NOLOCK)
                LEFT JOIN UMFBANK b WITH (NOLOCK) ON a.Bank = b.BANK_CODE
            WHERE a.APLESS=:apless AND a.APPL_NO=:applno
            GROUP BY a.Bank, a.ACC_No, a.ACC_Nm, a.CURR_CODE, b.[DESC], a.NOTES_REK, a.Bank_Branch
        """),
        {"apless": apless, "applno": applno}
    ).mappings().all()

    result = []
    for acc in accounts:
        stmt_rows = db.session.execute(
            text("""
                SELECT CONCAT(LEFT(Period,4), RIGHT(CONCAT('00', SUBSTRING(Period,5,2)), 2)) AS Period,
                       BegBal, Debet, Credit, EndBal, Notes
                FROM CAFBANKSTM WITH (NOLOCK)
                WHERE APLESS=:apless
                    AND APPL_NO=:applno
                    AND Bank=:bank
                    AND ACC_No=:acc_no
                    AND ACC_Nm=:acc_nm AND Curr_code=:curr
                ORDER BY 1
            """),
            {"apless": apless, "applno": applno, "bank": acc["Bank"], "acc_no": acc["ACC_No"],
             "acc_nm": acc["ACC_Nm"], "curr": acc["Curr_code"]}
        ).mappings().all()

        statements = []
        for s in stmt_rows:
            period_raw = s["Period"] or ""
            month, year = period_raw[4:6], period_raw[0:4]
            statements.append({
                "period_label": f"{bulan(month)} {year}".strip(),
                "beginning_balance": float(s["BegBal"] or 0),
                "debet": float(s["Debet"] or 0),
                "credit": float(s["Credit"] or 0),
                "ending_balance": float(s["EndBal"] or 0),
                "notes": s["Notes"] or "",
            })

        result.append({
            "bank_name": acc["bank_name"] or "",
            "branch": acc["Bank_Branch"] or "",
            "account_no": acc["ACC_No"] or "",
            "account_name": acc["ACC_Nm"] or "",
            "currency": acc["Curr_code"] or "",
            "notes": acc["NOTES_REK"] or "",
            "statements": statements,
        })
    return result

def _bank_statement_files(apless, applno):
    rows = db.session.execute(
        text("""
            SELECT a.Id, a.DocumentName, a.AWSKey
            FROM BANK_STATEMENT_DOCUMENT a WITH (NOLOCK)
            WHERE a.Apless=:apless AND a.ApplNo=:applno
            ORDER BY a.CreatedDate
        """),
        {"apless": apless, "applno": applno}
    ).mappings().all()

    files = []
    for r in rows:
        name = r["DocumentName"]
        if not name:
            continue
        files.append({"id": r["Id"], "name": name, "download_url": _build_download_url(r["AWSKey"], name)})
    return files

@cam_view_bp.route("/financial-info")
@login_required
def get_financial_info():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    ind_cor = request.args.get("ind_cor", "")

    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        date_row = db.session.execute(
            text("SELECT CONVERT(VARCHAR(6), CREATE_DATE, 112) AS YEARS FROM CAFCONT WITH (NOLOCK) "
                 "WHERE APLESS=:apless AND APPL_NO=:applno"),
            {"apless": apless, "applno": applno}
        ).mappings().first()
        years = date_row["YEARS"] if date_row else None
        dates = years if years else datetime.now().strftime("%Y")

        if ind_cor == "1":
            section = _individual_finance(apless, applno)
        elif ind_cor == "2":
            section = _corporate_finance(apless, applno, dates)
        else:
            section = {"no_data": True}

        return jsonify({
            "ind_cor": ind_cor,
            "individual": section if ind_cor == "1" else None,
            "corporate": section if ind_cor == "2" else None,
            "bank_accounts": _bank_accounts(apless, applno),
            "bank_statement_files": _bank_statement_files(apless, applno),
        })

    except Exception:
        current_app.logger.exception("CAM financial info error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/business-history")
@login_required
def get_business_history():
    apless = request.args.get("apless", "")
    if not apless:
        return jsonify({"error": "Missing apless"}), 400

    try:
        lessee_cat = db.session.execute(
            text("SELECT Lessee_Cat FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:apless"),
            {"apless": apless}
        ).scalar() or ""

        rows = db.session.execute(
            text("""
                SELECT ch.[FROM], ch.UNTIL, ch.Company, ch.Company_Address, ch.Phone,
                       ch.Employee_ID, ua.KABUPATEN, ua.PROPINSI, ch.Postcode,
                       CONCAT(mc.DESC_VALUE, IIF(ch.Position_Other<>'', CONCAT(' (', ch.Position_Other, ')'), '')) AS PositionLabel
                FROM CAFLESS_History ch WITH (NOLOCK)
                    INNER JOIN UMFAREA ua ON ua.Area_Cd = ch.AREA_CD
                    INNER JOIN MSTCOMBO mc ON mc.VALUE = ch.Position AND mc.CAT_VALUE = 'HISTORY_POSITION'
                WHERE ch.APLESS = :apless
            """),
            {"apless": apless}
        ).mappings().all()

        history = []
        for r in rows:
            from_raw = str(r["FROM"] or "")
            until_raw = str(r["UNTIL"] or "")
            from_label = f"{from_raw[4:6]}-{from_raw[0:4]}" if len(from_raw) >= 6 else ""
            until_label = "Present" if until_raw == "000000" else (
                f"{until_raw[4:6]}-{until_raw[0:4]}" if len(until_raw) >= 6 else ""
            )
            history.append({
                "from": from_label,
                "until": until_label,
                "company": r["Company"] or "",
                "company_address": r["Company_Address"] or "",
                "kabupaten": r["KABUPATEN"] or "",
                "propinsi": r["PROPINSI"] or "",
                "postcode": r["Postcode"] or "",
                "employee_id": r["Employee_ID"] or "",
                "position": r["PositionLabel"] or "",
                "phone": r["Phone"] or "",
            })

        return jsonify({
            "lessee_cat": lessee_cat,
            "show_employee_id": lessee_cat == "EM",
            "history": history,
            "no_data": len(history) == 0,
        })

    except Exception:
        current_app.logger.exception("CAM business history error")
        return jsonify({"error": "Failed to load data"}), 500

_HTML_BREAK_RE = re.compile(r'<\s*(br|/p|/div|/li|/tr)\s*/?\s*>', re.IGNORECASE)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_BLANK_LINES_RE = re.compile(r'\n{3,}')

def _html_to_text(value):
    if not value:
        return ""
    text = _HTML_BREAK_RE.sub('\n', value)
    text = _HTML_TAG_RE.sub('', text)
    text = unescape(text)
    text = _BLANK_LINES_RE.sub('\n\n', text)
    return text.strip()

SURVEY_TYPES = ["home-survey", "office-survey", "other-survey"]

def _survey_files(apless, applno):
    rows = db.session.execute(
        text("""
            SELECT Id, DocumentName, AWSKey, DocumentType
            FROM SURVEY_FILE WITH (NOLOCK)
            WHERE Apless=:apless AND ApplNo=:applno
                AND DocumentType IN ('home-survey', 'office-survey', 'other-survey')
            ORDER BY DocumentType, CreatedDate
        """),
        {"apless": apless, "applno": applno}
    ).mappings().all()

    buckets = {t: [] for t in SURVEY_TYPES}
    total_rows = 0
    for r in rows:
        total_rows += 1
        name = r["DocumentName"]
        doc_type = r["DocumentType"]
        if name and doc_type in buckets:
            buckets[doc_type].append({
                "id": r["Id"],
                "name": name,
                "download_url": _build_download_url(r["AWSKey"], name),
            })

    return buckets, total_rows == 0

def _survey_notes(applno, survey_type):
    note = db.session.execute(
        text("""
            SELECT TOP 1 NOTES FROM SURVEY_NOTES WITH (NOLOCK)
            WHERE ApplNo=:applno AND SurveyType=:t
            ORDER BY CreatedDate DESC
        """),
        {"applno": applno, "t": survey_type}
    ).scalar()
    return _html_to_text(note)

def _survey_information(apless, applno):
    cont_sts_raw = db.session.execute(
        text("SELECT ContSts FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).scalar()
    if cont_sts_raw is None:
        contract_status = "-"
    elif cont_sts_raw == "N":
        contract_status = "NEW"
    else:
        contract_status = "REPEAT"

    customer_name = _dash(db.session.execute(
        text("SELECT LESSEE_NM FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:apless"),
        {"apless": apless}
    ).scalar())

    vs = db.session.execute(
        text("""
            SELECT b.BRAND_NM, d.TYPE_NM, c.MODEL_NM, a.CHASIS, a.ENGINE, a.COLOUR, a.POLICENO,
                   a.BPKB_AN, a.BPKB_ADDR, a.TAHUN, a.CONDITION, e.NAME AS SUPP_NAME, a.BPKB_AN_TP,
                   DATEDIFF(yy, a.BPKB_TGLBIRTH, f.CREATE_DATE)
                    - CASE WHEN MONTH(a.BPKB_TGLBIRTH) > MONTH(f.CREATE_DATE) THEN 1 ELSE 0 END AS AGE_YEARS
            FROM CAFEQUIP a WITH (NOLOCK)
                LEFT JOIN CAFCONT f WITH (NOLOCK) ON a.APPL_NO = f.APPL_NO
                LEFT JOIN UMFBRAND b WITH (NOLOCK) ON a.brand = b.brand
                LEFT JOIN UMFMODEL c WITH (NOLOCK) ON a.model = c.model
                LEFT JOIN UMFType d WITH (NOLOCK) ON a.brand = d.brand AND a.Type = d.Type
                LEFT JOIN clfsupp e WITH (NOLOCK) ON a.SUPP = e.Supp
            WHERE a.appl_no = :applno
        """),
        {"applno": applno}
    ).mappings().first() or {}

    age_years = vs.get("AGE_YEARS")
    bpkb_age_suffix = ""
    if vs.get("BPKB_AN_TP") == "PR" and age_years not in (None, ""):
        bpkb_age_suffix = f" ({age_years} years old)"

    return {
        "contract_status": contract_status,
        "customer_name": customer_name,
        "brand": _dash(vs.get("BRAND_NM")),
        "model": _dash(vs.get("MODEL_NM")),
        "type": _dash(vs.get("TYPE_NM")),
        "chassis": _dash(vs.get("CHASIS")),
        "bpkb_name": _dash(vs.get("BPKB_AN")),
        "bpkb_age_suffix": bpkb_age_suffix,
        "engine": _dash(vs.get("ENGINE")),
        "bpkb_address": _dash(vs.get("BPKB_ADDR")),
        "year": _dash(vs.get("TAHUN")),
        "condition": _dash(vs.get("CONDITION")),
        "supplier": _dash(vs.get("SUPP_NAME")),
        "color": _dash(vs.get("COLOUR")),
        "police_no": _dash(vs.get("POLICENO")),
    }

@cam_view_bp.route("/customer-survey-file")
@login_required
def get_customer_survey_file():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        buckets, no_data = _survey_files(apless, applno)
        summary = _survey_information(apless, applno)

        return jsonify({
            "no_data": no_data,
            "summary": summary,
            "sections": {
                "home": {"files": buckets["home-survey"], "notes": _survey_notes(applno, "home-survey")},
                "office": {"files": buckets["office-survey"], "notes": _survey_notes(applno, "office-survey")},
                "other": {"files": buckets["other-survey"], "notes": _survey_notes(applno, "other-survey")},
            },
        })

    except Exception:
        current_app.logger.exception("CAM customer survey file error")
        return jsonify({"error": "Failed to load data"}), 500

EQUIPMENT_SQL = """
SELECT
    a.SUPP, a.TAHUN, a.CONDITION, a.CHASIS, a.ENGINE, a.COLOUR, a.POLICENO,
    a.USERUSAGE, a.PARK_LOC, pp.KABUPATEN AS CITY_PARK, a.BPKB_AN_TP, a.PARK_ZIPCODE,
    (CASE WHEN a.BPKB_AN_TP='PR' THEN 'Individu' WHEN a.BPKB_AN_TP='PT' THEN 'Corporate' ELSE '' END) AS bpkb_type,
    a.BPKB_NO, a.BPKB_AN, a.Relation, a.BPKB_ADDR, a.CITY_BPKB, a.KAROSERI, a.STNK_VALIDDT, a.MODEL, a.WHEELS,
    a.KAROSERI_SUPP, a.ACCESSORIES_SUPP, a.OTHER_SUPP, a.BPKB_AREA_CD, l.[NAME] AS karoseri_name, l.[ADDRESS] AS karoseri_address,
    m.[NAME] AS accessories_name, m.[ADDRESS] AS accessories_address, n.[NAME] AS OTHER_name, n.[ADDRESS] AS OTHER_address, b.[NAME] AS supp_name,
    b.ADDRESS, b.CITY, c.TYPE_NM AS type_equip, d.BRAND_NM, e.MODEL_NM, f.TYPE_NM,
    g.name AS purpose, dd.desc_value AS fin_purpose_d, mm.desc_value AS fin_purpose_m,
    h.DESKRIPSI, j.Notary_nm, k.Fdc_Area_Desc,
    LOWER([dbo].udfDateDiffinYrMonDay(a.BPKB_TGLBIRTH, DATEADD(day, -1, i.CREATE_DATE))) AS xxx,
    (CASE WHEN xx.IsRedCode='1' THEN 'Yes' ELSE 'No' END) AS IsRedCode, oo.NAME AS GPS_Vendor, a.FUND_PURPOSE
FROM
    CAFEQUIP AS a WITH (NOLOCK)
    LEFT JOIN CLFSUPP AS b WITH (NOLOCK) ON a.SUPP=b.SUPP
    LEFT JOIN CLFSUPP AS l WITH (NOLOCK) ON a.KAROSERI_SUPP=l.SUPP
    LEFT JOIN CLFSUPP AS m WITH (NOLOCK) ON a.ACCESSORIES_SUPP=m.SUPP
    LEFT JOIN CLFSUPP AS n WITH (NOLOCK) ON a.OTHER_SUPP=n.SUPP
    LEFT JOIN UMFJBM AS c WITH (NOLOCK) ON a.TYPE_CD=c.TYPE_CD
    LEFT JOIN UMFBRAND AS d WITH (NOLOCK) ON a.BRAND=d.BRAND
    LEFT JOIN UMFMODEL AS e WITH (NOLOCK) ON a.MODEL=e.MODEL
    LEFT JOIN UMFTYPE AS f WITH (NOLOCK) ON a.BRAND=f.BRAND AND a.TYPE=f.[TYPE]
    LEFT JOIN mstPurpose AS g WITH (NOLOCK) ON a.PURPOSE=g.Purpose
    LEFT JOIN MSTFAMSTATUS AS h WITH (NOLOCK) ON a.BPKB_AN_STS=h.ID_FAM
    LEFT JOIN CAFCONT AS i WITH (NOLOCK) ON a.APPL_NO=i.APPL_NO
    LEFT JOIN UMFNOTARY AS j WITH (NOLOCK) ON i.Notary_no=j.Notary_no
    LEFT JOIN CLFNOTARY_AREA AS k WITH (NOLOCK) ON i.Notary_no=k.Notary_no AND a.Fdc_Area=k.Fdc_Area
    LEFT JOIN Cafequip_Detail xx ON a.APPL_NO = xx.APPL_NO
    LEFT JOIN mstcombo AS dd WITH (NOLOCK) ON xx.FIN_PURPOSE=dd.value AND dd.cat_value='Fund_Facility'
    LEFT JOIN mstcombo AS mm WITH (NOLOCK) ON xx.FIN_PURPOSE=mm.value AND mm.cat_value='Business_Capital_Facility'
    LEFT JOIN VENDOR AS oo WITH (NOLOCK) ON xx.GPS_Vendor=oo.SUPP
    LEFT JOIN UMFAREA AS pp WITH (NOLOCK) ON a.CITY_PARK=pp.AREA_CD
WHERE
    a.APPL_NO=:applno
"""

def _equipment_detail(applno, fin_type):
    row = db.session.execute(text(EQUIPMENT_SQL), {"applno": applno}).mappings().first()
    if not row:
        return None

    condition_raw = (row["CONDITION"] or "").strip()
    kondisi = "New" if condition_raw == "NEW" else "Used"
    tahun = row["TAHUN"] or ""
    year_condition = "-" if (tahun == "" and condition_raw == "") else f"{tahun}/ {kondisi}"

    model, karoseri = row["MODEL"], row["KAROSERI"]
    karoseri_desc = None
    if model is not None and karoseri is not None:
        karoseri_desc = db.session.execute(
            text("SELECT KAROSERI_DESC FROM UMFKAROSERI WITH (NOLOCK) WHERE MODEL=:model AND KAROSERI=:karoseri"),
            {"model": model, "karoseri": karoseri}
        ).scalar()
    model_nm = row["MODEL_NM"] or ""
    model_karoseri = f"{model_nm} / {karoseri_desc}" if karoseri_desc else model_nm

    area_cd = row["BPKB_AREA_CD"]
    area_label = "-"
    if area_cd:
        area_row = db.session.execute(
            text("SELECT Propinsi, Kabupaten FROM UMFAREA WITH (NOLOCK) WHERE area_cd=:area_cd"),
            {"area_cd": area_cd}
        ).mappings().first()
        if area_row:
            area_label = f"{area_row['Propinsi']} - {area_row['Kabupaten']}"

    umur = row["xxx"]
    bpkb_an_tp = row["BPKB_AN_TP"]
    age_suffix = f" ({umur} years old)" if (bpkb_an_tp == "PR" and umur) else ""

    bpkb_an = row["BPKB_AN"] or ""
    bpkb_type = row["bpkb_type"] or ""
    bpkb_name_type = "-" if not bpkb_an else f"{bpkb_an}{age_suffix}/ {bpkb_type}"

    bpkb_addr = row["BPKB_ADDR"] or ""
    city_bpkb = row["CITY_BPKB"] or ""
    bpkb_address = "-" if not bpkb_addr else f"{bpkb_addr}, {city_bpkb}"

    address = (row["ADDRESS"] or "").strip()
    city = (row["CITY"] or "").strip()
    dealer_address_combined = f"{address}\n{city}".strip()
    dealer_address = dealer_address_combined if dealer_address_combined else "-"

    park_loc = row["PARK_LOC"] or ""
    city_park = row["CITY_PARK"] or ""
    parking_address = "-" if (park_loc == "" and city_park == "") else f"{park_loc}, {city_park}"

    stnk_validdt = _fmt_date(row["STNK_VALIDDT"]) if row["STNK_VALIDDT"] else ""

    show_financing_purpose = fin_type in ("D", "M", "W")
    if fin_type == "D":
        financing_purpose = row["fin_purpose_d"] or ""
    elif fin_type in ("M", "W"):
        financing_purpose = row["fin_purpose_m"] or ""
    else:
        financing_purpose = ""
    fund_purpose = row["FUND_PURPOSE"] or ""

    red_code_gps = f"{row['IsRedCode']} ({row['GPS_Vendor'] or ''})"

    has_karoseri = row["KAROSERI_SUPP"] not in (None, "")
    has_accessories = row["ACCESSORIES_SUPP"] not in (None, "")
    has_other = row["OTHER_SUPP"] not in (None, "")

    detail = {
        "brand": _dash(row["BRAND_NM"]),
        "show_stnk_valid_date": condition_raw == "USED",
        "stnk_valid_date": stnk_validdt,
        "type": _dash(row["TYPE_NM"]),
        "chassis": _dash(row["CHASIS"]),
        "model_karoseri": _dash(model_karoseri),
        "engine": _dash(row["ENGINE"]),
        "wheels": _dash(row["WHEELS"]),
        "police_no": _dash(row["POLICENO"]),
        "year_condition": year_condition,
        "color": _dash(row["COLOUR"]),
        "type_of_equipment": _dash(row["type_equip"]),
        "user_usage": _dash(row["USERUSAGE"]),
        "dealer_name": _dash(row["supp_name"]),
        "vehicle_purpose": _dash(row["purpose"]),
        "show_financing_purpose": show_financing_purpose,
        "financing_purpose": _dash(financing_purpose) if show_financing_purpose else "",
        "fund_purpose": _dash(fund_purpose) if show_financing_purpose else "",
        "dealer_address": dealer_address,
        "parking_address": parking_address,
        "red_code_gps": red_code_gps,
        "zip_code": row["PARK_ZIPCODE"] or "",
        "karoseri_name": _dash(row["karoseri_name"]) if has_karoseri else None,
        "karoseri_address": _dash(row["karoseri_address"]) if has_karoseri else None,
        "accessories_name": _dash(row["accessories_name"]) if has_accessories else None,
        "accessories_address": _dash(row["accessories_address"]) if has_accessories else None,
        "other_name": _dash(row["OTHER_name"]) if has_other else None,
        "other_address": _dash(row["OTHER_address"]) if has_other else None,
        "bpkb_no": row["BPKB_NO"] or "",
        "bpkb_name_type": bpkb_name_type,
        "show_family_status": bpkb_an_tp == "PR",
        "family_status": _dash(row["DESKRIPSI"]),
        "relation": _dash(row["Relation"]),
        "bpkb_address": bpkb_address,
        "area": area_label,
        "notary_name": _dash(row["Notary_nm"]),
        "fdc_area": _dash(row["Fdc_Area_Desc"]),
    }
    return detail, row["CHASIS"], row["ENGINE"], row["SUPP"]

CTOC_SQL = """
SELECT
    a.NAME AS ctoc_name, a.ADDRESS AS ctoc_addr, a.CITY AS ctoc_city, a.ZipCode AS ctoc_zip,
    a.PHONE AS ctoc_phone, a.ACCNO AS ctoc_accno, a.AccNoName AS ctoc_accname,
    d.[DESC] AS ctoc_bank, a.BankBranch AS ctoc_branch, b.Name AS ctoc_type, c.Name AS ctoc_cat
FROM CLFSUPP1 AS a WITH (NOLOCK)
    LEFT JOIN MSTTYPE b WITH (NOLOCK) ON a.SUPP_TYPE=b.Grnttp
    LEFT JOIN MSTCATEGORY c WITH (NOLOCK) ON a.SUPP_CAT=c.Code
    LEFT JOIN UMFBANK d WITH (NOLOCK) ON a.Bank = d.BANK_CODE
WHERE a.SUPP=:applno
"""

def _equipment_ctoc(applno):
    row = db.session.execute(text(CTOC_SQL), {"applno": applno}).mappings().first()
    if not row:
        return None
    return {
        "supplier_type": _dash(row["ctoc_type"]),
        "supplier_category": _dash(row["ctoc_cat"]),
        "supplier_id_name": f"{applno} / {row['ctoc_name'] or ''}",
        "address": _dash(row["ctoc_addr"]),
        "city_postcode": "-" if not row["ctoc_city"] else f"{row['ctoc_city']}, {row['ctoc_zip'] or ''}",
        "phone": _dash(row["ctoc_phone"]),
        "account_no_name": "-" if not row["ctoc_accno"] else f"{row['ctoc_accno']} / {row['ctoc_accname'] or ''}",
        "bank_branch": "-" if not row["ctoc_bank"] else f"{row['ctoc_bank']} / {row['ctoc_branch'] or ''}",
    }

def _equipment_financing_history(applno, chasis, engine):
    if not chasis or not engine:
        return []
    rows = db.session.execute(
        text("""
            SELECT a.LEASE_NO, c.LESSEE_NM, b.L_AMOUNT, d.Net_Finance, b.EXECUTION, b.LESSEE_NO,
                   (CASE WHEN b.upd_stat='T' THEN b.ET_DT WHEN b.UPD_STAT='F' THEN e.PAYMENT ELSE NULL END) AS finish,
                   b.UPD_STAT AS status
            FROM clfequip a WITH (NOLOCK)
                INNER JOIN clfcont b WITH (NOLOCK) ON a.LEASE_NO=b.LEASE_NO
                INNER JOIN clfless c WITH (NOLOCK) ON b.LESSEE_NO=c.LESSEE_NO
                INNER JOIN V_NetFinance d WITH (NOLOCK) ON a.LEASE_NO=d.LEASE_NO
                LEFT JOIN bgiro e WITH (NOLOCK) ON b.LEASE_NO=e.LEASE_NO AND b.TENOR=e.PERIOD
            WHERE (a.chasis=:chasis OR a.ENGINE=:engine) AND b.appl_no<>:applno AND b.EXECUTION IS NOT NULL
        """),
        {"chasis": chasis, "engine": engine, "applno": applno}
    ).mappings().all()

    history = []
    for r in rows:
        finish_dt = "-" if r["status"] == "Y" else _fmt_date(r["finish"])
        history.append({
            "lease_no": r["LEASE_NO"],
            "lessee_no": r["LESSEE_NO"],
            "lessee_nm": r["LESSEE_NM"] or "",
            "otr": float(r["L_AMOUNT"] or 0),
            "net_finance": float(r["Net_Finance"] or 0),
            "disburse_date": _fmt_date(r["EXECUTION"]),
            "finish_date": finish_dt,
        })
    return history

@cam_view_bp.route("/equipment")
@login_required
def get_equipment():
    applno = request.args.get("applno", "")
    fin_type = request.args.get("fin_type", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        result = _equipment_detail(applno, fin_type)
        if result is None:
            return jsonify({"no_data": True})
        detail, chasis, engine, supp = result

        show_ctoc = str(supp) == "999999"

        return jsonify({
            "no_data": False,
            "title": "Financing Object Detail Review" if fin_type == "S" else "Equipment Detail Review",
            "detail": detail,
            "financing_history": _equipment_financing_history(applno, chasis, engine),
            "show_ctoc": show_ctoc,
            "ctoc": _equipment_ctoc(applno) if show_ctoc else None,
        })

    except Exception:
        current_app.logger.exception("CAM equipment detail error")
        return jsonify({"error": "Failed to load data"}), 500

EQUIPMENT_SURVEY_FILE_TYPES = ["vehicle-photo-front", "vehicle-photo", "vehicle-data-bpkb", "vehicle-data"]
def _equipment_survey_files(apless, applno):
    rows = db.session.execute(
        text("""
            SELECT Id, DocumentName, AWSKey, DocumentType
            FROM SURVEY_FILE WITH (NOLOCK)
            WHERE Apless=:apless AND ApplNo=:applno AND SurveyType='vehicle-survey'
            ORDER BY DocumentType, CreatedDate
        """),
        {"apless": apless, "applno": applno}
    ).mappings().all()

    buckets = {t: [] for t in EQUIPMENT_SURVEY_FILE_TYPES}
    total_rows = 0
    for r in rows:
        total_rows += 1
        name = r["DocumentName"]
        doc_type = r["DocumentType"]
        if name and doc_type in buckets:
            buckets[doc_type].append({
                "id": r["Id"],
                "name": name,
                "download_url": _build_download_url(r["AWSKey"], name),
            })
    return buckets, total_rows == 0

def _vehicle_survey_notes(applno):
    note = db.session.execute(
        text("""
            SELECT TOP 1 NOTES FROM SURVEY_NOTES WITH (NOLOCK)
            WHERE ApplNo=:applno AND SurveyType='vehicle-survey'
            ORDER BY CreatedDate DESC
        """),
        {"applno": applno}
    ).scalar()
    return note or ""

@cam_view_bp.route("/equipment-survey-file")
@login_required
def get_equipment_survey_file():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        buckets, no_data = _equipment_survey_files(apless, applno)
        summary = _survey_information(apless, applno)
        notes = _vehicle_survey_notes(applno)

        return jsonify({
            "no_data": no_data,
            "summary": summary,
            "notes": notes,
            "files": {
                "vehicle_photo_front": buckets["vehicle-photo-front"],
                "vehicle_photo": buckets["vehicle-photo"],
                "vehicle_data_bpkb": buckets["vehicle-data-bpkb"],
                "vehicle_data": buckets["vehicle-data"],
            },
        })

    except Exception:
        current_app.logger.exception("CAM equipment survey file error")
        return jsonify({"error": "Failed to load data"}), 500

CONTSTS_LABELS = {"N": "New", "R1": "R1", "R2": "R2", "R3": "R3", "R4": "R4", "R5": "R5", "R6": ">5"}
PURPOSE_LABELS = {"1": "Finished", "2": "ET", "3": "Rental", "4": "Overdue Rental", "5": "Penalty"}

def _truncate_decimal(value, places):
   
    if value is None:
        return ""
    s = str(value)
    if "." not in s:
        return s
    head, _, tail = s.partition(".")
    return f"{head}.{tail[:places]}"

def _f(value):
    return float(value) if value is not None else 0.0

FINANCING_MAIN_SQL = """
SELECT
    a.Cons_Leas, a.CURR_CODE, ISNULL(a.L_AMOUNT,0) as L_AMOUNT, a.SECURITY, a.DECLRATE, a.FLATRATE, a.COL_TYPE, a.ADV_ARR, a.L_TYPE, a.FIX_FLOAT,
    a.FLOAT_CYC, a.TENOR, a.PAY_CYCLE, ISNULL(a.RENTAL,0) as RENTAL, a.MLCIDECL, a.MLCIFLAT, a.MLCIRENT, a.ContSts,
    a.AdmFee, a.Otherloan, a.tenor1000, a.FLATRATE1000, a.Notary, a.Fiduciary, a.Disb_Type, a.Cont_type,
    ISNULL(a.Refund_Supp,0) as Refund_Supp, ISNULL(a.Subsidy_Supp,0) as Subsidy_Supp, a.SUBSIDY, a.incentive, a.Disc_Cust, b.name AS l_type_ket,
    c.name AS cont_type_ket, d.name AS disb_type_ket, e.name AS col_type_ket, a.PROVISION,
    f.[DESC] AS PURPOFFINC, a.BaseInterestFee, a.InterestIncome, a.BaseAdmFee, ISNULL(a.BusinessTrip_Fee,0) as BusinessTrip_Fee, a.CREATE_DATE, h.DESC_VALUE as RESTRUCTURING_CHANGE,
    ISNULL(i.Survey_Fee_Cigna,0) as Survey_Fee_Cigna, i.Survey_Base_Rate_Cigna, i.Survey_Loan_Cigna, case when i.GuarantedAcceptance = '1' then 'Yes' else 'No' end as GuarantedAcceptance
FROM
    CAFCONT a WITH (NOLOCK)
    LEFT JOIN MSTAMORTYPE b WITH (NOLOCK) ON a.L_TYPE=b.L_Type
    LEFT JOIN MSTCONTTYPE c WITH (NOLOCK) ON a.Cont_type=c.Cont_type
    LEFT JOIN MSTDISBTYPE d WITH (NOLOCK) ON a.Disb_Type=d.Disb_Type
    LEFT JOIN MSTCOLLTYPE e WITH (NOLOCK) ON a.COL_TYPE=e.Col_Type
    LEFT JOIN MSTPURPOFFINC f WITH (NOLOCK) ON a.PURPOFFINC=f.PURPOFFINC
    LEFT JOIN CAFCONT_RESTRUCTURING g WITH (NOLOCK) ON a.APPL_NO=g.APPL_NO
    LEFT JOIN MSTCOMBO h WITH (NOLOCK) ON g.RESTRUCTURING_CHANGE=h.VALUE AND h.CAT_VALUE='RESTRUCTURING_CHANGE'
    LEFT JOIN CIGNA_FEE i WITH (NOLOCK) ON i.APPL_NO=a.APPL_NO
WHERE
    a.APPL_NO=:applno
    AND a.APLESS=:apless
"""

def _financing_cross_no(applno):
    rows = db.session.execute(
        text("SELECT CROSSNO FROM TACROSSNO WITH (NOLOCK) WHERE APPL_NO=:applno AND CROSS_TYPE='CN' AND CROSSNO<>''"),
        {"applno": applno}
    ).scalars().all()
    if len(rows) == 1:
        return f"Cross Contract | {rows[0]}"
    if len(rows) > 1:
        return "Cross Contract | Attachment"
    return None

def _financing_bbn(applno):
    return db.session.execute(
        text("""SELECT bbnvia, paidby, serviceagencyNM, BBNloan, ISNULL(BBN_FEE,0) as BBN_FEE,
                 ISNULL(ServiceAgencyFee,0) as ServiceAgencyFee, NettServiceAgencyFee
                 FROM BBN WITH (NOLOCK) WHERE APPL_NO=:applno"""),
        {"applno": applno}
    ).mappings().first() or {}

def _provision_loan(applno):
    return db.session.execute(
        text("SELECT Prov_loan FROM Provision_Loan WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).scalar() or 0

CAFINSU_SQL = """
SELECT ISNULL(a.CREDITAMT,0) as CREDITAMT, a.INS_POL, a.USAGE,
(CASE WHEN a.PAY_METHOD='1' THEN 'Cash' WHEN a.PAY_METHOD='2' THEN 'Yearly' WHEN a.PAY_METHOD='3' THEN 'Credit' END) AS PAY_METHOD,
a.CONDITION, a.Total_Seat, b.INS_CO, c.DESC_VALUE as MODEL_NM
FROM CAFINSU a WITH (NOLOCK)
    LEFT JOIN UMFINSCD b WITH (NOLOCK) ON a.INS_CD=b.INS_CD
    LEFT JOIN MSTCOMBO c WITH (NOLOCK) ON a.MODEL=c.VALUE AND c.CAT_VALUE='MODEL_ASURANSI'
WHERE a.APPL_NO=:applno
"""

def _financing_gross_prem(applno):
    return db.session.execute(
        text("SELECT GROSS_PREM FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:applno AND split=''"),
        {"applno": applno}
    ).scalar()

VDISBURSE_SQL = """
SELECT ISNULL(FIRST_INST,0) as FIRST_INST, ISNULL(ADMFEE,0) as ADMFEE, ISNULL(DP,0) as DP, DISB_INSC, ISNULL(Prov,0) as Prov,
SERVICE_AGENCY_FEE, ISNULL(BBN_FEE,0) as BBN_FEE, SurveyFeeGross_Cigna, ISNULL(Notary_Fee,0) as Notary_Fee
FROM VDISBURSE WITH (NOLOCK)
WHERE APPL_NO=:applno
"""

def _financing_dealer_commission(applno):
    row = db.session.execute(
        text("SELECT FEE, PPNAmount, GrossAmount FROM CAFKOMIS WITH (NOLOCK) WHERE APPL_NO=:applno AND SD_TYPE='D'"),
        {"applno": applno}
    ).mappings().first()
    if not row:
        return 0.0
    return _f(row["GrossAmount"]) + _f(row["PPNAmount"])

def _financing_step_rental(applno):
    no_step = db.session.execute(
        text("SELECT MAX(STEP) AS no_step FROM CAFSTEP WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).scalar() or 0
    steps = []
    for i in range(1, int(no_step) + 1):
        row = db.session.execute(
            text("SELECT * FROM CAFSTEP WITH (NOLOCK) WHERE APPL_NO=:applno AND STEP=:step"),
            {"applno": applno, "step": i}
        ).mappings().first()
        if not row:
            continue
        steps.append({
            "step": i,
            "month": row.get("NO_STEP"),
            "rental": _f(row.get("PMT_STEP")),
            "based": _f(row.get("MLCI_STEP")),
        })
    return steps

def _financing_insurance(ins_pol, model_nm, kondisi, pay_method, total_seat, usage, ins_co):
    if not ins_pol:
        return None
    rows = db.session.execute(
        text("""SELECT a.INS_POL, a.YEAR_NO, a.INS_AMT, a.PRER_AMT, a.PREP_AMT, a.TPL_AMT, b.NAME AS TLO_AR
                FROM CAFINSUD a WITH (NOLOCK)
                    LEFT JOIN mstTLOAR b WITH (NOLOCK) ON a.TLO_AR=b.CODE
                WHERE a.INS_POL=:ins_pol ORDER BY a.YEAR_NO"""),
        {"ins_pol": ins_pol}
    ).mappings().all()
    if not rows:
        return None

    year_rows = []
    for r in rows:
        year_no = r["YEAR_NO"]
        clause_rows = db.session.execute(
            text("""SELECT cc.name as clause_nm FROM CAFINSUD_Clause xx WITH (NOLOCK)
                    INNER JOIN mstclause cc WITH (NOLOCK) ON xx.clause = cc.code
                    WHERE xx.INS_POL=:ins_pol AND xx.year_no=:year_no ORDER BY cc.name"""),
            {"ins_pol": ins_pol, "year_no": year_no}
        ).scalars().all()
        year_rows.append({
            "year": year_no,
            "ins_amount": _f(r["INS_AMT"]),
            "tpl_amount": _f(r["TPL_AMT"]),
            "tlo_ar": r["TLO_AR"] or "",
            "clause": " + ".join(clause_rows),
            "premium_receive": _f(r["PRER_AMT"]),
            "premium_payment": _f(r["PREP_AMT"]),
        })

    return {
        "ins_policy": ins_pol,
        "ins_company": ins_co or "",
        "pay_method": pay_method or "",
        "model_nm": model_nm or "",
        "condition": kondisi,
        "total_seat": total_seat,
        "show_usage": bool(usage),
        "usage_label": "Commercial" if usage == "C" else ("Private" if usage else ""),
        "rows": year_rows,
    }

def _financing_internal_disbursement(applno):
    rows = db.session.execute(
        text("""SELECT ROW_NUMBER() OVER(ORDER BY ID_TACrossNo) AS No, CROSSNO, AMOUNT, PURPOSE
                FROM TACrossNo WITH (NOLOCK)
                WHERE APPL_NO=:applno AND CROSS_TYPE='CD'"""),
        {"applno": applno}
    ).mappings().all()
    result, total = [], 0.0
    for r in rows:
        amount = _f(r["AMOUNT"])
        total += amount
        result.append({
            "no": r["No"],
            "contract_no": r["CROSSNO"],
            "amount": amount,
            "purpose": PURPOSE_LABELS.get(str(r["PURPOSE"]), ""),
        })
    return result, total

def _financing_external_disbursement(applno, ind_cor):
    rows = db.session.execute(
        text("""
            SELECT ROW_NUMBER() OVER(ORDER BY a.ID) AS No, a.BANK, a.BANK_BRANCH, a.ACC_NO, a.ACC_NM, a.AMOUNT,
                   b.[DESC] as bank_name, a.APPL_NO,
                   c.SUPP, c.KAROSERI_SUPP, c.ACCESSORIES_SUPP, c.OTHER_SUPP, a.[SPLIT]
            FROM CAFDISBACC a WITH (NOLOCK)
                LEFT JOIN UMFBANK b WITH (NOLOCK) ON a.Bank = b.BANK_CODE
                LEFT JOIN CAFEQUIP c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
            WHERE a.APPL_NO=:applno
        """),
        {"applno": applno}
    ).mappings().all()

    result, total = [], 0.0
    for r in rows:
        split = r["SPLIT"]
        supp_id = {
            "Dealer": r["SUPP"], "Karoseri": r["KAROSERI_SUPP"],
            "Accessories": r["ACCESSORIES_SUPP"], "Others": r["OTHER_SUPP"],
        }.get(split)

        name, address = "", ""
        if supp_id:
            supp_row = db.session.execute(
                text("SELECT NAME, [ADDRESS] FROM CLFSUPP WITH (NOLOCK) WHERE SUPP=:supp"),
                {"supp": supp_id}
            ).mappings().first()
            if supp_row:
                name, address = supp_row["NAME"] or "", supp_row["ADDRESS"] or ""

        if not name and not address:
            lessee_row = db.session.execute(
                text("""SELECT LESSEE_NM, ADDRESS1, ADDRESS2 FROM CAFLESS WITH (NOLOCK)
                        WHERE APLESS IN (SELECT apless FROM cafcont WHERE appl_no=:applno)"""),
                {"applno": r["APPL_NO"]}
            ).mappings().first()
            if lessee_row:
                name = lessee_row["LESSEE_NM"] or ""
                address = (lessee_row["ADDRESS2"] if ind_cor == "2" else lessee_row["ADDRESS1"]) or ""

        amount = _f(r["AMOUNT"])
        total += amount
        result.append({
            "no": r["No"],
            "name": name,
            "address": address,
            "bank_branch": f"{r['bank_name'] or ''} - {r['BANK_BRANCH'] or ''}",
            "account_no": r["ACC_NO"] or "",
            "account_name": r["ACC_NM"] or "",
            "amount": amount,
        })
    return result, total

def _financing_commission_rows(applno, create_date_raw):
    create_date_str = _fmt_date(create_date_raw) if create_date_raw else ""
    today = datetime.now()

    rows = db.session.execute(
        text("""SELECT SD_TYPE, SALES_NO, TaxAmount, PPNAmount, GrossAmount
                 FROM CAFKOMIS WITH (NOLOCK) WHERE APPL_NO=:applno AND Incentive='1'
                 ORDER BY SD_TYPE, FEE DESC"""),
        {"applno": applno}
    ).mappings().all()

    result = []
    for i, r in enumerate(rows, start=1):
        tax_amt = r["TaxAmount"]
        sd_type = r["SD_TYPE"]
        sales_no = r["SALES_NO"]
        no_tax = not tax_amt
        code = ""

        if sd_type == "S":
            tax_row = db.session.execute(
                text("""SELECT ppn, NPWP_Type, Sales_Type, a.NPWP_No, a.DateStart, a.TFFrom, a.TFTo
                         FROM BeneficiaryTax a WITH (NOLOCK)
                         INNER JOIN CLFSALES b WITH (NOLOCK) ON b.SALES_NO=a.BeneficiaryID
                         WHERE a.BeneficiaryID=:sales_no AND Category='SALES'"""),
                {"sales_no": sales_no}
            ).mappings().first() or {}
            ppn, npwp_type, sales_type, npwp_no = (
                tax_row.get("ppn"), tax_row.get("NPWP_Type"), tax_row.get("Sales_Type"), tax_row.get("NPWP_No")
            )
            datestart_raw, tffrom_raw, tfto_raw = tax_row.get("DateStart"), tax_row.get("TFFrom"), tax_row.get("TFTo")
            datestart_str = _fmt_date(datestart_raw) if datestart_raw else ""
            has_npwp = npwp_no not in (None, "")
            in_tax_window = bool(tffrom_raw and tfto_raw and tffrom_raw <= today <= tfto_raw)
            datestart_before_create = bool(datestart_str) and datestart_str <= create_date_str

            if sales_type == "PT":
                if npwp_type == "PT" and has_npwp:
                    if ppn == "1" and datestart_str and datestart_before_create:
                        code = "B<sup>TVB</sup>" if no_tax else "B<sup>TV</sup>"
                    else:
                        code = "B<sup>TB</sup>" if (no_tax and in_tax_window) else "B<sup>T</sup>"
                if npwp_type == "PR" and has_npwp:
                    if ppn == "1" and datestart_str and datestart_before_create:
                        code = "B<sup>RVB</sup>" if no_tax else "B<sup>RV</sup>"
                    else:
                        code = "B<sup>RB</sup>" if (no_tax and in_tax_window) else "B<sup>R</sup>"
                if npwp_type in ("PR", "00") and not has_npwp:
                    code = "B"
            else:
                code = "S" if (npwp_type in ("", "00", "PR", None) and not has_npwp) else "S<sup>N</sup>"

            sales_row = db.session.execute(
                text("SELECT NAME, ADDRESS FROM CLFSALES WITH (NOLOCK) WHERE SALES_NO=:sales_no"),
                {"sales_no": sales_no}
            ).mappings().first() or {}
            name, address = sales_row.get("NAME") or "", sales_row.get("ADDRESS") or ""

        else:
            tax_row = db.session.execute(
                text("SELECT ppn, DateStart, TFFrom, TFTo FROM BeneficiaryTax WITH (NOLOCK) WHERE BeneficiaryID=:sales_no"),
                {"sales_no": sales_no}
            ).mappings().first() or {}
            ppn = tax_row.get("ppn")
            datestart_raw, tffrom_raw, tfto_raw = tax_row.get("DateStart"), tax_row.get("TFFrom"), tax_row.get("TFTo")
            datestart_str = _fmt_date(datestart_raw) if datestart_raw else ""
            ppn_year = datestart_raw.strftime("%Y") if datestart_raw else ""
            in_tax_window = bool(tffrom_raw and tfto_raw and tffrom_raw <= today <= tfto_raw)
            datestart_before_create = bool(datestart_str) and datestart_str <= create_date_str

            if ppn == "1" and datestart_str and datestart_before_create and ppn_year != "1900":
                code = "D<sup>VB</sup>" if no_tax else "D<sup>V</sup>"
            else:
                code = "D<sup>B</sup>" if (no_tax and in_tax_window) else "D"

            supp_row = db.session.execute(
                text("SELECT NAME, ADDRESS FROM CLFSUPP WITH (NOLOCK) WHERE SUPP=:sales_no"),
                {"sales_no": sales_no}
            ).mappings().first() or {}
            name, address = supp_row.get("NAME") or "", supp_row.get("ADDRESS") or ""

        result.append({
            "no": i,
            "code": f"{code} {sales_no}".strip(),
            "name": name,
            "address": address,
            "fee": _f(r["GrossAmount"]) + _f(r["PPNAmount"]),
        })
    return result

def _subsidy_sum(applno, amount_type):
    return db.session.execute(
        text("""SELECT SUM(b.Amount) as jumlah FROM CAFCONT a WITH (NOLOCK)
                 INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO=b.APPL_No
                 WHERE a.APPL_NO=:applno AND b.AmountType=:t GROUP BY a.APPL_No, b.AmountType"""),
        {"applno": applno, "t": amount_type}
    ).scalar() or 0

def _financing_calculator(applno, fin_type, ins_pol, admfee_non_disb, provfee, base_interest_fee,
                            interest_income, basesurv, survey_fee_cigna, survey_base_rate_cigna):
    jumlah_sur = _f(_subsidy_sum(applno, "Survey"))
    jumlah_sur2 = _f(_subsidy_sum(applno, "SurveyFee2"))
    jumlah_prov = _f(_subsidy_sum(applno, "Provision"))
    jumlah_int = _f(_subsidy_sum(applno, "Interest"))

    disb_row = db.session.execute(
        text("SELECT GROSS_PREM, NET_COM FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).mappings().first() or {}
    grosspremi, net_comi = _f(disb_row.get("GROSS_PREM")), _f(disb_row.get("NET_COM"))

    max_pee = db.session.execute(
        text("SELECT Max_Fee FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).scalar()
    max_pee = _f(max_pee)

    totalnetinsu = 0.0
    if ins_pol:
        insud_rows = db.session.execute(
            text("SELECT PREP_AMT FROM CAFINSUD WITH (NOLOCK) WHERE INS_POL=:ins_pol ORDER BY YEAR_NO"),
            {"ins_pol": ins_pol}
        ).scalars().all()
        totalnetinsu = sum(_f(v) for v in insud_rows)

    ttlincomer = grosspremi - net_comi
    ttlincome = ttlincomer
    ttlincomenet = ttlincome

    ttlsubinc = ttlincome
    ttlsubincnet = ttlincomenet
    execinc = ttlsubinc

    subsidy_tot = jumlah_sur + jumlah_prov + jumlah_int + jumlah_sur2
    ttlint = interest_income + jumlah_int
    excint = ttlint - base_interest_fee
    ttlsurv = admfee_non_disb + jumlah_sur
    ttlsurv2 = survey_fee_cigna + jumlah_sur2
    excesurv = ttlsurv - basesurv
    excesurv2 = ttlsurv2 - survey_base_rate_cigna
    ttlprov = provfee + jumlah_prov
    provexec = ttlprov

    if fin_type == "I" and ttlsurv >= 2500000:
        ttlsurv = 2500000.0
    elif fin_type == "S" and ttlsurv >= 5000000:
        ttlsurv = 5000000.0

    ttlsubtot = ttlsurv + ttlprov + ttlint + ttlsubincnet + ttlsurv2
    ttlexctot = execinc + excesurv + provexec + excint + excesurv2

    party_row = db.session.execute(
        text("SELECT CAST([Percentage] AS FLOAT) as Percentage, COMM_THIRDPARTY FROM COMM_PARTY WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).mappings().first() or {}
    percentage = party_row.get("Percentage") or 16
    maxcomm = _f(party_row.get("COMM_THIRDPARTY"))

    eligiblecomm = max_pee
    marketing_fee = 0.0 if eligiblecomm <= maxcomm else (eligiblecomm - round(maxcomm))

    rows = [
        {"label": "Insurance Income", "income": ttlincome, "subsidy": None, "total_income": None, "base_rate": 0.0, "max_refund": execinc},
        {"label": "Net Insurance Prem. Received", "income": ttlincomenet, "subsidy": None, "total_income": ttlsubincnet, "base_rate": None, "max_refund": None},
        {"label": "Survey Fee 1", "income": admfee_non_disb, "subsidy": jumlah_sur, "total_income": ttlsurv, "base_rate": basesurv, "max_refund": excesurv},
        {"label": "Survey Fee 2", "income": survey_fee_cigna, "subsidy": jumlah_sur2, "total_income": ttlsurv2, "base_rate": survey_base_rate_cigna, "max_refund": excesurv2},
        {"label": "Provision Fee", "income": provfee, "subsidy": jumlah_prov, "total_income": ttlprov, "base_rate": 0.0, "max_refund": provexec},
        {"label": "Interest Income", "income": interest_income, "subsidy": jumlah_int, "total_income": ttlint, "base_rate": base_interest_fee, "max_refund": excint},
    ]

    return {
        "rows": rows,
        "subsidy_total": subsidy_tot,
        "total_income_total": ttlsubtot,
        "max_refund_total": ttlexctot,
        "max_incentive_percent": percentage,
        "max_incentive_amount": maxcomm,
        "marketing_fee": marketing_fee,
        "incentive_to_be_paid": eligiblecomm,
    }

def _financing_outstanding(applno):
    rows = db.session.execute(
        text("""
            SELECT TYPE, ASOF, OUTS_NOTES, SUM(UNIT) as UNIT, SUM(OUTS) as OUTS
            FROM CAFCUST_OUTS WITH (NOLOCK)
            WHERE APPL_NO=:applno AND
                ASOF=(SELECT TOP 1 ASOF
                    FROM CAFCUST_OUTS WITH (NOLOCK)
                    WHERE APPL_NO=:applno
                    GROUP BY ASOF
                    ORDER BY ASOF DESC)
            GROUP BY TYPE, ASOF, OUTS_NOTES
            ORDER BY TYPE
        """),
        {"applno": applno}
    ).mappings().all()
    if not rows:
        return None

    by_type, fl_tot_unit, fl_tot = {}, 0.0, 0.0
    for r in rows:
        by_type[str(r["TYPE"])] = {"unit": _f(r["UNIT"]), "amount": _f(r["OUTS"])}
        fl_tot_unit += _f(r["UNIT"])
        fl_tot += _f(r["OUTS"])

    type_labels = {"1": "disbursement", "2": "undisbursement", "3": "unapprove", "4": "group", "5": "guarantor"}
    return {
        "rows": {label: by_type.get(code, {"unit": 0.0, "amount": 0.0}) for code, label in type_labels.items()},
        "total_unit": fl_tot_unit,
        "total_amount": fl_tot,
        "calc_date": _fmt_date(rows[0]["ASOF"]),
        "notes": rows[0]["OUTS_NOTES"] or None,
    }

def _outstanding_proc_rows(applno, mode):
    return db.session.execute(text("EXEC USP_CAM_OUTSTANDING :applno, :mode"), {"applno": applno, "mode": mode}).mappings().all()

def _ratio(op_v, mrkt_v):
    return round(op_v / mrkt_v * 100, 2) if (op_v and mrkt_v) else None

def _financing_loan_ratio_disbursement(applno):
    rows = _outstanding_proc_rows(applno, "1")
    rentalcross1 = rentalcross0 = ophasil1 = ophasil0 = totmrktcross = totmrktcross2 = 0.0
    rentalinstall = rentalfinance = rentalsale = rentaldana = rentalmodal = 0
    ophasilI = ophasilF = ophasilS = ophasilD = ophasilM = 0.0
    totmrkt = ophasil = totrental = 0.0
    loan_rows = []

    for i, r in enumerate(rows, start=1):
        market_price, op, rental = _f(r.get("MARKETPRICE")), _f(r.get("op")), _f(r.get("RENTAL"))

        if r.get("REMARK") == "Cross Collateral":
            rentalcross1 += rental
            ophasil1 += op
            totmrktcross += market_price
        else:
            rentalcross0 += rental
            ophasil0 += op
            totmrktcross2 += market_price

        cons_leas = r.get("Cons_Leas")
        if cons_leas == "I":
            rentalinstall += 1
            ophasilI += op
        elif cons_leas == "S":
            rentalsale += 1
            ophasilS += op
        elif cons_leas == "D":
            rentaldana += 1
            ophasilD += op
        elif cons_leas == "M":
            rentalmodal += 1
            ophasilM += op
        if cons_leas == "F":
            rentalfinance += 1
            ophasilF += op

        loan_rows.append({
            "no": i, "label": r.get("LEASE_NO"), "brand_type": r.get("brand_type") or "",
            "tahun": r.get("TAHUN"), "market_price": market_price, "op": op, "rental": rental,
            "term": r.get("TERM"), "tenor": r.get("tenor"), "payment_status": r.get("PAYMENTSTATUS"),
            "user_usage": r.get("USERUSAGE"), "loan_ratio": r.get("loan_ratio"), "branch": r.get("NickName"),
            "remark": r.get("REMARK"),
        })
        totmrkt += market_price
        ophasil += op
        totrental += rental

    sub_total = {"market": totmrkt, "op": ophasil, "rental": totrental, "ratio": _ratio(ophasil, totmrkt)}
    breakdown = {
        "cross": {"market": totmrktcross, "op": ophasil1, "rental": rentalcross1, "ratio": _ratio(ophasil1, totmrktcross)},
        "non_cross": {"market": totmrktcross2, "op": ophasil0, "rental": rentalcross0, "ratio": _ratio(ophasil0, totmrktcross2)},
        "total_exposure": {
            "market": totmrktcross + totmrktcross2, "op": ophasil1 + ophasil0, "rental": rentalcross1 + rentalcross0,
            "ratio": _ratio(ophasil1 + ophasil0, totmrktcross + totmrktcross2),
        },
        "by_finance_type": {
            "installment_financing": {"op": ophasilI, "units": rentalinstall},
            "finance_lease": {"op": ophasilF, "units": rentalfinance},
            "sale_leaseback": {"op": ophasilS, "units": rentalsale},
            "dana": {"op": ophasilD, "units": rentaldana},
            "modal_usaha": {"op": ophasilM, "units": rentalmodal},
        },
    }
    return {"rows": loan_rows, "sub_total": sub_total}, breakdown, totmrkt, ophasil, totrental

def _financing_loan_ratio_simple(applno, mode, label_mode):
    rows = _outstanding_proc_rows(applno, mode)
    loan_rows = []
    totmrkt = ophasil = totrental = 0.0
    for i, r in enumerate(rows, start=1):
        market_price, op = _f(r.get("MARKETPRICE")), _f(r.get("op"))
        rental = _f(r.get("RENTAL") if r.get("RENTAL") is not None else r.get("rental"))

        if label_mode == "lease_no":
            label = r.get("LEASE_NO")
        elif label_mode == "appl_no":
            label = r.get("APPL_NO")
        else:
            label = r.get("LEASE_NO") or r.get("APPL_NO")

        loan_rows.append({
            "no": i, "label": label, "apless": r.get("APLESS"), "applno": r.get("APPL_NO"),
            "brand_type": r.get("brand_type") or "", "tahun": r.get("TAHUN"),
            "market_price": market_price, "op": op, "rental": rental,
            "term": r.get("TERM"), "tenor": r.get("tenor"), "payment_status": r.get("PAYMENTSTATUS"),
            "user_usage": r.get("USERUSAGE"), "loan_ratio": r.get("loan_ratio"), "branch": r.get("NickName"),
            "cons_leas": r.get("Cons_Leas") if mode == "3" else None,
        })
        totmrkt += market_price
        ophasil += op
        totrental += rental

    sub_total = {"market": totmrkt, "op": ophasil, "rental": totrental, "ratio": _ratio(ophasil, totmrkt)}
    return {"rows": loan_rows, "sub_total": sub_total}, totmrkt, ophasil, totrental

@cam_view_bp.route("/financing")
@login_required
def get_financing():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    fin_type = request.args.get("fin_type", "")
    ind_cor = request.args.get("ind_cor", "")
    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        row = db.session.execute(text(FINANCING_MAIN_SQL), {"applno": applno, "apless": apless}).mappings().first()
        if not row:
            return jsonify({"no_data": True})

        l_amount_raw = _f(row["L_AMOUNT"])
        cont_type = row["Cont_type"]
        cont_type_ket = row["cont_type_ket"] or ""
        if row["Cons_Leas"] == "L":
            if cont_type == "RF1":
                cont_type_ket = "Lease Back 1 (No Outs)"
            elif cont_type == "RF2":
                cont_type_ket = "Lease Back 2 (Any Outs)"

        contsts_raw = row["ContSts"]
        contsts = CONTSTS_LABELS.get(contsts_raw, "-") if contsts_raw else ""

        l_type = row["L_TYPE"]
        adv_arr = row["ADV_ARR"]
        adv_arr_ket = "In Advance" if adv_arr == "V" else ("In Arrears" if adv_arr == "R" else "")
        fix_float = row["FIX_FLOAT"]
        fix_float_ket = "Fix" if fix_float == "X" else (f"Float / {row['FLOAT_CYC']} month" if fix_float == "L" else "")

        security = _f(row["SECURITY"])
        security_persen = round(security * 100 / l_amount_raw, 2) if (security and l_amount_raw) else 0.0
        netfinance = l_amount_raw - security

        cafinsu = db.session.execute(text(CAFINSU_SQL), {"applno": applno}).mappings().first() or {}
        creditamt = _f(cafinsu.get("CREDITAMT"))
        ins_pol = cafinsu.get("INS_POL")
        kondisi = "New" if (cafinsu.get("CONDITION") or "").strip() == "NEW" else "Used"

        prov_loan = _f(_provision_loan(applno))
        totnetfinance = netfinance + creditamt + _f(row["Otherloan"]) + prov_loan

        disc_cust = row["Disc_Cust"]
        rental_raw = _f(row["RENTAL"])
        if disc_cust == "1":
            rental_disb = rental_raw if adv_arr == "V" else 0.0
            creditamt_disb = creditamt
        else:
            gross_prem = _f(_financing_gross_prem(applno))
            rental_disb = rental_raw
            creditamt_disb = gross_prem - creditamt

        bbn = _financing_bbn(applno)
        bbn_via = bbn.get("bbnvia") or ""
        paid_by = bbn.get("paidby") or ""
        bbnloan_hitung = _f(bbn.get("BBNloan"))
        agency_nm = bbn.get("serviceagencyNM") or ""
        bbn_hitung = _f(bbn.get("BBN_FEE"))
        birja_hitung = _f(bbn.get("ServiceAgencyFee"))
        nett_birja = _f(bbn.get("NettServiceAgencyFee"))

        totnetfinance += bbnloan_hitung
        survey_loan_cigna = _f(row["Survey_Loan_Cigna"])
        totnetfinance_survey_loan2 = totnetfinance + survey_loan_cigna

        vdisb = db.session.execute(text(VDISBURSE_SQL), {"applno": applno}).mappings().first()
        business_trip = _f(row["BusinessTrip_Fee"])
        survey_fee_cigna = _f(row["Survey_Fee_Cigna"])
        survey_base_rate_cigna = _f(row["Survey_Base_Rate_Cigna"])
        admfee_non_disb = _f(row["AdmFee"])
        basesurv = _f(row["BaseAdmFee"])

        if vdisb:
            security_disb = _f(vdisb["DP"]) if vdisb["DP"] not in (None, "") else security
            admfee = _f(vdisb["ADMFEE"]) if vdisb["ADMFEE"] not in (None, "") else admfee_non_disb
            survey_fee_gross_disb = _f(vdisb["SurveyFeeGross_Cigna"]) if vdisb["SurveyFeeGross_Cigna"] not in (None, "") else survey_fee_cigna
            rental_disb = _f(vdisb["FIRST_INST"]) if vdisb["FIRST_INST"] not in (None, "") else rental_raw
            provfee_disb = _f(vdisb["Prov"]) if vdisb["Prov"] not in (None, "") else _f(row["PROVISION"])
            if vdisb["DISB_INSC"] not in (None, ""):
                creditamt_disb = _f(vdisb["DISB_INSC"])
            if paid_by == "Deduct from disbursement":
                if vdisb["SERVICE_AGENCY_FEE"] not in (None, ""):
                    birja_hitung = _f(vdisb["SERVICE_AGENCY_FEE"])
                birja_disb = birja_hitung
                if vdisb["BBN_FEE"] not in (None, ""):
                    bbn_hitung = _f(vdisb["BBN_FEE"])
                bbn_disb = bbn_hitung
            else:
                birja_disb, birja_hitung, bbn_disb, bbn_hitung = 0.0, 0.0, 0.0, 0.0
            notary_gross = _f(vdisb["Notary_Fee"]) if vdisb["Notary_Fee"] not in (None, "") else _f(row["Notary"])
        else:
            security_disb, admfee, provfee_disb = 0.0, 0.0, 0.0
            survey_fee_gross_disb = survey_fee_cigna
            birja_disb, bbn_disb = 0.0, 0.0
            notary_gross = _f(row["Notary"])

        notaryfee = _f(db.session.execute(
            text("SELECT Gross FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"), {"applno": applno}
        ).scalar())

        totnetfinance_disb = (
            l_amount_raw - security_disb - admfee - notary_gross - provfee_disb - creditamt_disb
            - rental_disb - bbn_hitung - birja_hitung - business_trip - _f(row["Subsidy_Supp"]) - survey_fee_gross_disb
            + _f(row["Refund_Supp"])
        )
        comm_dealer = _financing_dealer_commission(applno)
        tot_pmt_dealer = totnetfinance_disb + comm_dealer

        flatrate = _truncate_decimal(row["FLATRATE"], 4)
        mlciflat = _truncate_decimal(row["MLCIFLAT"], 4)
        declrate = _truncate_decimal(row["DECLRATE"], 4)
        mlcidecl = _truncate_decimal(row["MLCIDECL"], 4)

        rental_fmt = _f(row["RENTAL"])
        mlcirent_fmt = _f(row["MLCIRENT"])
        rental_selling, rental_base = (rental_fmt, mlcirent_fmt) if l_type != "3" else (None, None)

        step_rental = _financing_step_rental(applno) if l_type == "3" else None

        var_dp = "Security Deposit" if fin_type in ("S", "F") else "Down Payment"
        cross_note = _financing_cross_no(applno)
        incent = bool(row["incentive"])

        tenor_label = f"{row['tenor1000'] if l_type == '4' else row['TENOR']} month / {row['PAY_CYCLE']} month"

        fund_facility_label = None
        fund_facility_amount = None
        grand_fund_facility_label = None
        grand_fund_facility_amount = None
        if fin_type in ("D", "M"):
            outs_ff = _f(db.session.execute(
                text("""SELECT SUM(outstanding) AS totalpembiayaan FROM V_CustomerOutstanding
                        WHERE Cons_Leas=:cons_leas AND APLESS=:apless AND APPL_NO<>:applno"""),
                {"cons_leas": fin_type, "apless": apless, "applno": applno}
            ).scalar())
            if fin_type == "D":
                fund_facility_label = "Total Customer's Outstanding Contract & CAM Net Finance for Fund Facility (FD)"
                grand_fund_facility_label = "Grand Total Customer's Outstanding Contract & CAM Net Finance for Fund Facility (FD)"
            else:
                fund_facility_label = "Total Customer's Outstanding Contract & CAM Net Finance for Business Capital Facility (FMU)"
                grand_fund_facility_label = "Grand Total Customer's Outstanding Contract & CAM Net Finance for Business Capital Facility (FMU)"
            fund_facility_amount = outs_ff
            grand_fund_facility_amount = outs_ff + totnetfinance

        header = {
            "l_type_label": row["l_type_ket"] or "",
            "status": contsts,
            "currency": row["CURR_CODE"] or "",
            "contract_type": cont_type_ket,
            "asset_value": l_amount_raw,
            "disbursement_type": row["disb_type_ket"] or "",
            "cross_note": cross_note,
            "dp_label": var_dp,
            "security_percent": security_persen,
            "security_amount": security,
            "payment_method": row["col_type_ket"] or "",
            "net_finance": netfinance,
            "purpose_of_finance": row["PURPOFFINC"] or "",
            "insurance_loan": creditamt,
            "type_of_payment": f"{row['l_type_ket'] or ''} - {adv_arr_ket}",
            "bbn_loan": bbnloan_hitung,
            "fix_float": fix_float_ket,
            "provision_loan": prov_loan,
            "tenor_label": tenor_label,
            "other_loan": _f(row["Otherloan"]),
            "subsidy_from_dealer": _f(row["Subsidy_Supp"]),
            "total_net_finance": totnetfinance,
            "incentive_or_subsidy_label": "Incentive from APM" if incent else "Subsidy From APM",
            "incentive_or_subsidy_amount": _f(row["SUBSIDY"]),
            "survey_loan_2": survey_loan_cigna,
            "refund_to_dealer": _f(row["Refund_Supp"]),
            "total_net_finance_plus_survey_loan2": totnetfinance_survey_loan2,
            "bbn_via": bbn_via,
            "flat_rate_selling": flatrate, "flat_rate_base": mlciflat,
            "paid_by": paid_by,
            "effective_rate_selling": declrate, "effective_rate_base": mlcidecl,
            "agency_name": agency_nm,
            "rental_selling": rental_selling, "rental_base": rental_base,
            "agency_fee_gross": _f(bbn.get("ServiceAgencyFee")),
            "bbn_fee": _f(bbn.get("BBN_FEE")),
            "show_restructuring_change": cont_type in ("RS1", "RS0"),
            "restructuring_change": row["RESTRUCTURING_CHANGE"] or "",
            "notary_fee_gross": notaryfee,
            "business_trip_fee": business_trip,
            "nett_deed_fee": _f(row["Notary"]),
            "nett_certificate_fee": _f(row["Fiduciary"]),
            "nett_agency_fee": nett_birja,
            "guaranteed_acceptance": row["GuarantedAcceptance"] or "No",
            "show_customer_flat_rate": l_type == "4",
            "customer_flat_rate": _truncate_decimal(row["FLATRATE1000"], 4) if l_type == "4" else "",
            "fund_facility_label": fund_facility_label,
            "fund_facility_amount": fund_facility_amount,
            "grand_fund_facility_label": grand_fund_facility_label,
            "grand_fund_facility_amount": grand_fund_facility_amount,
        }

        calculator = _financing_calculator(
            applno, fin_type, ins_pol, admfee_non_disb, _f(row["PROVISION"]), _f(row["BaseInterestFee"]),
            _f(row["InterestIncome"]), basesurv, survey_fee_cigna, survey_base_rate_cigna,
        )

        insurance = _financing_insurance(
            ins_pol, cafinsu.get("MODEL_NM"), kondisi, cafinsu.get("PAY_METHOD"),
            cafinsu.get("Total_Seat"), cafinsu.get("USAGE"), cafinsu.get("INS_CO"),
        )

        internal_rows, internal_total = _financing_internal_disbursement(applno)
        external_rows, external_total = _financing_external_disbursement(applno, ind_cor)

        disbursement = {
            "left": {
                "asset_value": l_amount_raw,
                "dp_label": var_dp,
                "dp_or_security_amount": security,
                "survey_fee_gross": survey_fee_gross_disb,
                "notary_fee_gross": notary_gross,
                "provision_fee": provfee_disb,
                "business_trip_fee": business_trip,
                "insurance": creditamt_disb,
                "first_installment": rental_disb,
                "agency_fee_gross": birja_disb,
                "bbn_fee": bbn_disb,
                "refund_to_dealer": _f(row["Refund_Supp"]),
                "subsidy_from_dealer": _f(row["Subsidy_Supp"]),
                "disbursement_to_dealer": totnetfinance_disb,
                "commission_to_dealer_gross": comm_dealer,
                "total_payment_to_dealer": tot_pmt_dealer,
            },
            "internal": internal_rows,
            "internal_total": internal_total,
            "external": external_rows,
            "external_total": external_total,
        }

        commission_rows = _financing_commission_rows(applno, row["CREATE_DATE"])
        outstanding = _financing_outstanding(applno)
        disb_lr, breakdown, totmrkt, ophasil, totrental = _financing_loan_ratio_disbursement(applno)
        undis_lr, totmrkt_undis, ophasil_undis, totrental_undis = _financing_loan_ratio_simple(applno, "2", "lease_no")
        unapp_lr, totmrkt_unapp, ophasil_unapp, totrental_unapp = _financing_loan_ratio_simple(applno, "3", "appl_no")
        grp_lr, totmrkt_grp, ophasil_grp, totrental_grp = _financing_loan_ratio_simple(applno, "4", "fallback")
        gua_lr, totmrkt_gua, ophasil_gua, totrental_gua = _financing_loan_ratio_simple(applno, "5", "fallback")

        grand_dis_undis_unapp = {
            "market": totmrkt + totmrkt_undis + totmrkt_unapp,
            "op": ophasil + ophasil_undis + ophasil_unapp,
            "rental": totrental + totrental_undis + totrental_unapp,
            "ratio": _ratio(ophasil + ophasil_undis + ophasil_unapp, totmrkt + totmrkt_undis + totmrkt_unapp),
        }
        cek_group_guarn = len(grp_lr["rows"]) + len(gua_lr["rows"])
        grand_total_all = None
        if cek_group_guarn:
            tm_all = totmrkt + totmrkt_undis + totmrkt_unapp + totmrkt_gua + totmrkt_grp
            op_all = ophasil + ophasil_undis + ophasil_unapp + ophasil_gua + ophasil_grp
            rent_all = totrental + totrental_undis + totrental_unapp + totrental_gua + totrental_grp
            grand_total_all = {"market": tm_all, "op": op_all, "rental": rent_all, "ratio": _ratio(op_all, tm_all)}

        loan_ratio = {
            "disbursement": disb_lr,
            "cross_collateral_breakdown": breakdown,
            "undisbursement": undis_lr,
            "unapprove": unapp_lr,
            "grand_total_dis_undis_unapp": grand_dis_undis_unapp,
            "group": grp_lr,
            "guarantor": gua_lr,
            "grand_total_all": grand_total_all,
        }

        return jsonify({
            "no_data": l_amount_raw <= 0,
            "header": header,
            "step_rental": step_rental,
            "calculator": calculator,
            "insurance": insurance,
            "disbursement": disbursement,
            "commission": commission_rows if commission_rows else None,
            "outstanding": outstanding,
            "loan_ratio": loan_ratio,
        })

    except Exception:
        current_app.logger.exception("CAM financing error")
        return jsonify({"error": "Failed to load data"}), 500

SUBSIDY_TYPE_LABELS = {
    "SD": "Subsidy From Dealer",
    "SA": "Subsidy From APM",
    "IA": "Incentive From APM",
    "RD": "Refund To Dealer",
}

@cam_view_bp.route("/financing/subsidy-detail")
@login_required
def get_financing_subsidy_detail():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        rows = db.session.execute(
            text("""SELECT b.SubsidyType, b.Amount, b.AmountType
                    FROM CAFCONT a WITH (NOLOCK)
                    INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO=b.APPL_No
                    WHERE a.APPL_NO=:applno"""),
            {"applno": applno}
        ).mappings().all()

        result = [
            {
                "type": SUBSIDY_TYPE_LABELS.get(r["SubsidyType"], r["SubsidyType"] or ""),
                "payment_for": r["AmountType"] or "",
                "amount": _f(r["Amount"]),
            }
            for r in rows
        ]
        return jsonify(result)

    except Exception:
        current_app.logger.exception("CAM financing subsidy detail error")
        return jsonify({"error": "Failed to load data"}), 500

DEVIATION_SQL_STANDARD = """
SELECT
    CONVERT(VARCHAR(MAX), a.DEVIATION_CD) AS DEVIATION_CD,
    CONVERT(VARCHAR(MAX), a.STANDARD_DESC) AS STANDARD_DESC,
    CONVERT(VARCHAR(MAX), a.DEVIATION_DESC) AS DEVIATION_DESC,
    CONVERT(VARCHAR(MAX), a.REASON) AS REASON
FROM CAFDEV AS a WITH (NOLOCK)
WHERE a.APPL_NO=:applno
    AND a.DEVIATION_CD <> '4001'
GROUP BY CONVERT(VARCHAR(MAX), a.DEVIATION_CD), CONVERT(VARCHAR(MAX), a.STANDARD_DESC),
    CONVERT(VARCHAR(MAX), a.DEVIATION_DESC), CONVERT(VARCHAR(MAX), a.REASON)
ORDER BY CONVERT(VARCHAR(MAX), a.DEVIATION_CD) ASC
"""

DEVIATION_SQL_OTHER = """
SELECT
    CONVERT(VARCHAR(MAX), a.DEVIATION_CD) AS DEVIATION_CD,
    CONVERT(VARCHAR(MAX), a.REASON) AS REASON,
    CONVERT(VARCHAR(MAX), a.STANDARD_DESC) AS STANDARD_DESC,
    CONVERT(VARCHAR(MAX), a.DEVIATION_DESC) AS DEVIATION_DESC
FROM CAFDEV AS a WITH (NOLOCK)
WHERE a.APPL_NO=:applno
    AND a.DEVIATION_CD = '4001'
GROUP BY CONVERT(VARCHAR(MAX), a.DEVIATION_CD), CONVERT(VARCHAR(MAX), a.REASON),
    CONVERT(VARCHAR(MAX), a.STANDARD_DESC), CONVERT(VARCHAR(MAX), a.DEVIATION_DESC)
ORDER BY CONVERT(VARCHAR(MAX), a.DEVIATION_CD) ASC
"""

@cam_view_bp.route("/deviation")
@login_required
def get_deviation():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        standard_rows = db.session.execute(text(DEVIATION_SQL_STANDARD), {"applno": applno}).mappings().all()
        other_rows = db.session.execute(text(DEVIATION_SQL_OTHER), {"applno": applno}).mappings().all()

        rows = []
        for i, r in enumerate(list(standard_rows) + list(other_rows), start=1):
            rows.append({
                "no": i,
                "standard_desc": r["STANDARD_DESC"] or "",
                "deviation_desc": r["DEVIATION_DESC"] or "",
                "reason": r["REASON"] or "",
                "is_other": r["DEVIATION_CD"] == "4001",
            })

        return jsonify({"no_data": len(rows) == 0, "rows": rows})

    except Exception:
        current_app.logger.exception("CAM deviation error")
        return jsonify({"error": "Failed to load data"}), 500

PIL_CREDIT_HIS = {1: "Good", 2: "Medium", 3: "Low"}
PIL_REF = {1: "Our Customer", 2: "Showroom/ Dealer", 3: "Our Employee"}
PIL_WORK_EXP = {1: "<2 years", 2: "2-5 years", 3: ">5 years"}
PIL_LIVING = {1: "House", 2: "Apartment"}
PIL_CAR_OWN = {1: "First Car User", 2: "More than 1 Car"}
PIL_BANK_STAT = {1: "> Asset Value", 2: "= Asset Value", 3: "< Asset Value"}
PIL_JOB = {1: "Not Work", 2: "Entrepreneur", 3: "Employee", 4: "Professional"}
PIL_PMT = {0: "Auto Debet BCA", 1: "Giro", 2: "Transfer / Cash"}
PIL_COMP_STS = {1: "Pure Foreign Company", 2: "Joint Venture Company/ Multinational Company", 3: "National Company", 4: "Family Business", 5: "Private Business"}
PIL_SCALE = {1: "Local", 2: "National", 3: "International"}
PIL_NET_PROFIT = {1: "> 30%", 2: "10 - 30%", 3: "< 10%"}
PIL_BUS_LOC = {1: "Business District (Gedung, Ruko, Pasar)", 2: "House Complex", 3: "Non Permanent"}
PIL_UNIT_OWN = {1: "> 10", 2: "< 10", 3: "None"}
PIL_UNIT_FREE = {1: "> 50%", 2: "30 - 50%", 3: "< 30%"}
PIL_LIV_STATUS_HOUSE = {1: "Rent", 2: "Permanent - Owned", 3: "Permanent - Family Owned", 4: "Company"}
PIL_LIV_STATUS_APT = {1: "Rent", 2: "Owned", 3: "Company"}
KET_FUND_INDIVIDUAL = {1: "Gaji", 2: "Hasil Usaha", 3: "Hasil investasi (Saham, Sewa rumah, deposito)", 4: "Lain-lain"}
KET_FUND_CORPORATE = {2: "Hasil Usaha", 3: "Hasil investasi (Saham, Sewa rumah, deposito)", 4: "Lain-lain"}

def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def _pil(d, code):
    i = _to_int(code)
    return d.get(i, "") if i is not None else ""

def _survey_credit_period(tenor):
    t = _to_int(tenor)
    return f"{t if t is not None else tenor} months"

def _vs_installment(value, installment):
    v, inst = _f(value), _f(installment)
    if v < inst:
        return "(< Installment)"
    if v == inst:
        return "(= Installment)"
    return "(> Installment)"

def _survey_insurance(ins_row):
    ins_loan = _to_int(ins_row.get("CREDITAMT")) or 0
    if ins_loan:
        return "Credit"
    ins_cd = ins_row.get("INS_CD")
    if ins_cd:
        pay_method = ins_row.get("PAY_METHOD")
        if pay_method == "1":
            return "Cash"
        if pay_method == "2":
            return "Yearly"
        return "Credit"
    return ""

def _survey_dealer_status(applno):
    supp_type = db.session.execute(
        text("""SELECT a.Supp_Type
                FROM CLFSUPP a WITH (NOLOCK)
                    LEFT JOIN CAFEQUIP b WITH (NOLOCK) ON a.SUPP = b.SUPP WHERE b.APPL_NO=:applno"""),
        {"applno": applno}
    ).scalar()
    return "Authorized Dealer" if supp_type == "AD" else "Showroom"

def _survey_purpose(applno):
    return db.session.execute(
        text("SELECT PURPOSE FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO=:applno"), {"applno": applno}
    ).scalar()

def _total_outstanding_label(fl_tot):
    if fl_tot < 500_000_000:
        return "IDR < 500 Mio"
    if fl_tot <= 1_000_000_000:
        return "IDR 500 - 1,000 Mio"
    if fl_tot <= 5_000_000_000:
        return "IDR > 1,000 Mio"
    return "> 5,000 Mio"

def _estimated_asset_label(total_amount):
    if total_amount <= 50_000_000:
        return "0 to 50 million IDR"
    if total_amount <= 500_000_000:
        return "> 50 million to 500 million IDR"
    if total_amount <= 10_000_000_000:
        return "> 500 million to 10 billion IDR"
    if total_amount <= 100_000_000_000:
        return "> 10 billion to 100 billion IDR"
    if total_amount <= 1_000_000_000_000:
        return "> 100 billion to 1 trillion IDR"
    return "> 1 trillion IDR"

def _survey_outstanding_individual(applno):
    calc_dt = db.session.execute(
        text("SELECT TOP 1 ASOF FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:applno GROUP BY ASOF ORDER BY ASOF DESC"),
        {"applno": applno}
    ).scalar()
    if not calc_dt:
        return 0.0
    rows = db.session.execute(
        text("SELECT TYPE, OUTS FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:applno AND ASOF=:asof ORDER BY TYPE"),
        {"applno": applno, "asof": calc_dt}
    ).mappings().all()
    amount2 = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    for r in rows:
        t = _to_int(r["TYPE"])
        if t in amount2:
            amount2[t] = _f(r["OUTS"])
    return sum(amount2.values())

def _survey_outstanding_corporate(applno):
    calc_dt = db.session.execute(
        text("SELECT TOP 1 ASOF FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:applno GROUP BY ASOF ORDER BY ASOF DESC"),
        {"applno": applno}
    ).scalar()
    if not calc_dt:
        return 0.0, None
    rows = db.session.execute(
        text("""SELECT OUTS FROM CAFCUST_OUTS WITH (NOLOCK)
                 WHERE APPL_NO=:applno AND ASOF=:asof AND TYPE='1'"""),
        {"applno": applno, "asof": calc_dt}
    ).scalars().all()
    return sum(_f(v) for v in rows), calc_dt

def _survey_individual(applno, apless, installment, contsts, kondisi):
    row = db.session.execute(
        text("""SELECT CREDIT_HIS, REF, WORK_EXP, NOTE_CHAR, LIVING, LIVING_STS, CAR_OWN, NOTE_CAPITAL, FIX_INC, JOB,
                 TOT_OTH_INC, TOT_INC, TOT_CREDIT, NOTE_CAPACITY, PMT, NOTE_COLLATERAL, FIX_INC_SOURCE,
                 TOT_OTH_INC_SOURCE, FIX_SOURCE_REMARK, OTH_SOURCE_REMARK, NOTE_SID_CHECKING, TOT_INC_YEAR, APPL_NO
                 FROM CAFSURV_PR WITH (NOLOCK) WHERE APPL_NO=:applno"""),
        {"applno": applno}
    ).mappings().first()
    if not row:
        return None

    living_int = _to_int(row["LIVING"])
    liv_status_dict = PIL_LIV_STATUS_HOUSE if living_int == 1 else (PIL_LIV_STATUS_APT if living_int == 2 else {})

    src_fund1, src_fund2 = _to_int(row["FIX_INC_SOURCE"]), _to_int(row["TOT_OTH_INC_SOURCE"])
    lain1 = f"({row['FIX_SOURCE_REMARK']})" if row["FIX_SOURCE_REMARK"] else ""
    lain2 = f"({row['OTH_SOURCE_REMARK']})" if row["OTH_SOURCE_REMARK"] else ""

    job_stat = db.session.execute(
        text("""SELECT b.NAME FROM CAFLESS a WITH (NOLOCK)
                LEFT JOIN MSTLESSEETYPE b WITH (NOLOCK) ON a.Lessee_Cat = b.CUST_TYPE WHERE a.APLESS=:apless"""),
        {"apless": apless}
    ).scalar()

    spouseincome = _f(db.session.execute(
        text("SELECT TOP 1 AMOUNT FROM CAFFS WITH (NOLOCK) WHERE APLESS=:apless AND ITEM_CODE='310103' ORDER BY PERIOD DESC"),
        {"apless": apless}
    ).scalar())

    credit_his_label = _pil(PIL_CREDIT_HIS, row["CREDIT_HIS"])
    cred_hist = "RO" if contsts != "N" else "New"
    credit_history_label = f"{cred_hist} - {credit_his_label}" if contsts != "N" else cred_hist

    tot_oth_inc, tot_inc = _f(row["TOT_OTH_INC"]), _f(row["TOT_INC"])

    ins_row = db.session.execute(
        text("SELECT INS_CD, PAY_METHOD, CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).mappings().first() or {}

    fl_tot = _survey_outstanding_individual(applno)
    purpose = _survey_purpose(applno)
    usage_car = "Private" if purpose == "01" else "Non Private"

    return {
        "character": {
            "credit_history_label": credit_history_label,
            "reference": _pil(PIL_REF, row["REF"]) or "Unavailable",
            "work_experience": _pil(PIL_WORK_EXP, row["WORK_EXP"]),
            "note": row["NOTE_CHAR"] or "",
            "company_status": None,
            "scale_of_business": None,
        },
        "capital": {
            "living_label": _pil(PIL_LIVING, living_int) or None,
            "living_status_label": _pil(liv_status_dict, row["LIVING_STS"]),
            "car_ownership": _pil(PIL_CAR_OWN, row["CAR_OWN"]),
            "note": row["NOTE_CAPITAL"] or "",
            "business_location": None, "office_status": None, "total_unit_owned": None,
            "unit_free_from_finance": None, "estimated_total_assets_label": None, "estimated_total_assets_asof": None,
        },
        "capacity": {
            "job_occupation_customer": job_stat or "",
            "fixed_monthly_income": _f(row["FIX_INC"]),
            "fixed_income_source_label": f"{KET_FUND_INDIVIDUAL.get(src_fund1, '')} {lain1}".strip(),
            "job_occupation_spouse": _pil(PIL_JOB, row["JOB"]),
            "spouse_income_per_month": spouseincome,
            "total_other_income": tot_oth_inc,
            "total_other_income_status": _vs_installment(tot_oth_inc, installment),
            "total_other_income_source_label": f"{KET_FUND_INDIVIDUAL.get(src_fund2, '')} {lain2}".strip(),
            "total_income_per_month": tot_inc,
            "total_income_status": _vs_installment(tot_inc, installment),
            "average_income_per_year": _f(row["TOT_INC_YEAR"]),
            "note": row["NOTE_CAPACITY"] or "",
            "monthly_profit": None, "monthly_profit_status": None, "monthly_profit_source_label": None,
            "sales_per_month": None, "net_profit_to_sales": None,
        },
        "collateral": {
            "unit_type": kondisi,
            "insurance": _survey_insurance(ins_row),
            "payment_method": _pil(PIL_PMT, row["PMT"]),
            "note": row["NOTE_COLLATERAL"] or "",
        },
        "condition": {
            "total_outstanding_label": _total_outstanding_label(fl_tot),
            "dealer_status": _survey_dealer_status(applno),
            "usage_of_car": usage_car,
        },
        "note_sid": row["NOTE_SID_CHECKING"] or "",
    }

def _survey_corporate(applno, apless, installment, contsts, kondisi):
    row = db.session.execute(
        text("""SELECT a.CREDIT_HIS, a.REF, a.WORK_EXP, a.NOTE_CHAR, a.NOTE_CAPITAL, a.NOTE_CAPACITY, a.PMT,
                a.NOTE_COLLATERAL, a.COMP_STS, a.SCALE, a.MONTH_PROFIT, a.NET_PROFIT, a.TOT_CREDIT, a.BUS_LOC,
                a.UNIT_OWN, a.UNIT_FREE, a.MONTH_SALES, d.name AS officestatus, a.MONTH_PROFIT_SOURCE,
                a.MONTH_PROFIT_REMARK, a.NOTE_SID_CHECKING, a.APPL_NO
                FROM CAFSURV_PT a WITH (NOLOCK)
                    LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO=b.APPL_NO
                    LEFT JOIN CAFLESS c WITH (NOLOCK) ON b.APLESS=c.APLESS
                    LEFT JOIN MSTADDRESSSTATUS d WITH (NOLOCK) ON c.Address_Status=d.AddressStatus
                WHERE a.APPL_NO=:applno"""),
        {"applno": applno}
    ).mappings().first()
    if not row:
        return None

    src_fund1 = _to_int(row["MONTH_PROFIT_SOURCE"])
    lain1 = f"({row['MONTH_PROFIT_REMARK']})" if row["MONTH_PROFIT_REMARK"] else ""

    credit_his_label = _pil(PIL_CREDIT_HIS, row["CREDIT_HIS"])
    cred_hist = "RO" if contsts != "N" else "New"
    credit_history_label = f"{cred_hist} - {credit_his_label}" if contsts != "N" else cred_hist

    month_profit = _f(row["MONTH_PROFIT"])

    ins_row = db.session.execute(
        text("SELECT INS_CD, PAY_METHOD, CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).mappings().first() or {}

    fl_tot, calc_dt = _survey_outstanding_corporate(applno)
    estimated_asset_label = _estimated_asset_label(fl_tot)

    purpose = _survey_purpose(applno)
    if purpose == "01":
        usage_car = "Private"
    elif purpose == "02":
        usage_car = "Operational Business"
    else:
        usage_car = "Rental / Third Party"

    return {
        "character": {
            "credit_history_label": credit_history_label,
            "reference": _pil(PIL_REF, row["REF"]) or "Unavailable",
            "work_experience": _pil(PIL_WORK_EXP, row["WORK_EXP"]),
            "note": row["NOTE_CHAR"] or "",
            "company_status": _pil(PIL_COMP_STS, row["COMP_STS"]),
            "scale_of_business": _pil(PIL_SCALE, row["SCALE"]),
        },
        "capital": {
            "living_label": None, "living_status_label": None, "car_ownership": None,
            "business_location": _pil(PIL_BUS_LOC, row["BUS_LOC"]),
            "office_status": row["officestatus"] or "",
            "total_unit_owned": _pil(PIL_UNIT_OWN, row["UNIT_OWN"]),
            "unit_free_from_finance": _pil(PIL_UNIT_FREE, row["UNIT_FREE"]),
            "estimated_total_assets_label": estimated_asset_label,
            "estimated_total_assets_asof": _fmt_date(calc_dt, "%d %b %Y") if calc_dt else "",
            "note": row["NOTE_CAPITAL"] or "",
        },
        "capacity": {
            "job_occupation_customer": None, "fixed_monthly_income": None, "fixed_income_source_label": None,
            "job_occupation_spouse": None, "spouse_income_per_month": None, "total_other_income": None,
            "total_other_income_status": None, "total_other_income_source_label": None,
            "total_income_per_month": None, "total_income_status": None, "average_income_per_year": None,
            "monthly_profit": month_profit,
            "monthly_profit_status": _vs_installment(month_profit, installment),
            "monthly_profit_source_label": f"{KET_FUND_CORPORATE.get(src_fund1, '')} {lain1}".strip(),
            "sales_per_month": _f(row["MONTH_SALES"]),
            "net_profit_to_sales": _pil(PIL_NET_PROFIT, row["NET_PROFIT"]),
            "note": row["NOTE_CAPACITY"] or "",
        },
        "collateral": {
            "unit_type": kondisi,
            "insurance": _survey_insurance(ins_row),
            "payment_method": _pil(PIL_PMT, row["PMT"]),
            "note": row["NOTE_COLLATERAL"] or "",
        },
        "condition": {
            "total_outstanding_label": _total_outstanding_label(fl_tot),
            "dealer_status": _survey_dealer_status(applno),
            "usage_of_car": usage_car,
        },
        "note_sid": row["NOTE_SID_CHECKING"] or "",
    }

def _mstcombo_dict(cat_value):
    rows = db.session.execute(
        text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE=:cat"), {"cat": cat_value}
    ).all()
    return {r[0]: r[1] for r in rows}

def _survey_sid_checking(applno):
    rows = db.session.execute(
        text("""SELECT DISTINCT Subject, Description, CreditBureau, RelatedParty, Status, Type, Score, Grade,
                 Pefindo, AWSKey FROM SIK_CHECKING_DOCUMENT WITH (NOLOCK) WHERE ApplNo=:applno"""),
        {"applno": applno}
    ).mappings().all()
    if not rows:
        return []

    subject_dict = _mstcombo_dict("SID1")
    related_party_dict = _mstcombo_dict("SIDa2")
    type_dict = _mstcombo_dict("SID_Type")
    status_dict = _mstcombo_dict("SIDST")

    result = []
    for r in rows:
        subject, related_party = r["Subject"], r["RelatedParty"]
        credit_bureau, type_code, score_raw = r["CreditBureau"], r["Type"], r["Score"]

        if credit_bureau == "APPI":
            score = "Whitelist" if _f(score_raw) == 0 else "Blacklist"
        elif credit_bureau == "SLIK":
            score = f"Col {score_raw}"
        else:
            score = score_raw

        show_related_party = subject == "RP"
        show_keterangan_text = related_party == "Other"
        show_type = bool(related_party)
        if related_party in ("Director", "Commissioner"):
            type_label = type_dict.get("PR", "") if type_code == "PR" else ""
        else:
            type_label = type_dict.get(type_code, "") if type_code else ""

        pefindo = r["Pefindo"]
        result.append({
            "subject": subject_dict.get(subject, ""),
            "show_related_party": show_related_party,
            "related_party": related_party_dict.get(related_party, "") if show_related_party else "",
            "show_keterangan_text": show_keterangan_text,
            "keterangan_text": (r["Description"] or "") if show_keterangan_text else "",
            "show_type": show_type,
            "type_label": type_label,
            "credit_bureau": credit_bureau or "",
            "status": status_dict.get(r["Status"], ""),
            "score": score if score is not None else "",
            "grade": r["Grade"] or "",
            "pefindo_download_url": _build_download_url(r["AWSKey"], r["AWSKey"]) if pefindo else None,
        })
    return result

@cam_view_bp.route("/survey")
@login_required
def get_survey():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    new_car = request.args.get("new_car", "")
    ind_cor = request.args.get("ind_cor", "")
    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        tenor = db.session.execute(
            text("SELECT TENOR FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno AND APLESS=:apless"),
            {"applno": applno, "apless": apless}
        ).scalar()
        credit_period = _survey_credit_period(tenor)

        kondisi = "Used" if new_car == "1" else ("New" if new_car == "2" else "")

        inst_row = db.session.execute(
            text("SELECT rental, ContSts FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"), {"applno": applno}
        ).first()
        installment = _f(inst_row[0]) if inst_row else 0.0
        contsts = inst_row[1] if inst_row else None

        data = (
            _survey_individual(applno, apless, installment, contsts, kondisi) if ind_cor == "1"
            else _survey_corporate(applno, apless, installment, contsts, kondisi)
        )
        if data is None:
            return jsonify({"no_data": True})

        cont_row = db.session.execute(
            text("""SELECT a.HAS_GUARANTOR, ISNULL(a.L_AMOUNT,0) as L_AMOUNT, ISNULL(a.SECURITY,0) as SECURITY,
                        ISNULL(a.Otherloan,0) as Otherloan, ISNULL(b.CREDITAMT,0) as CREDITAMT,
                        ISNULL(c.Survey_Loan_Cigna,0) as Survey_Loan_Cigna, ISNULL(d.BBNLoan,0) as BBNLoan,
                        ISNULL(e.Prov_loan,0) as Prov_loan
                    FROM CAFCONT a WITH (NOLOCK)
                        LEFT JOIN CAFINSU b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                        LEFT JOIN Cigna_fee c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                        LEFT JOIN BBN d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
                        LEFT JOIN Provision_Loan e WITH (NOLOCK) ON a.APPL_NO = e.APPL_NO
                    WHERE a.APPL_NO=:applno"""),
            {"applno": applno}
        ).mappings().first()

        loan_to_value, guarantor_label = 0.0, "Not Available"
        if cont_row:
            l_amount = _f(cont_row["L_AMOUNT"])
            totnetfinance = (
                l_amount - _f(cont_row["SECURITY"]) + _f(cont_row["CREDITAMT"]) + _f(cont_row["Otherloan"])
                + _f(cont_row["Survey_Loan_Cigna"]) + _f(cont_row["BBNLoan"]) + _f(cont_row["Prov_loan"])
            )
            loan_to_value = round(totnetfinance / l_amount * 100, 2) if l_amount else 0.0
            guarantor_label = "Available" if cont_row["HAS_GUARANTOR"] == "1" else "Not Available"

        data["collateral"]["loan_to_value"] = loan_to_value
        data["collateral"]["guarantor"] = guarantor_label
        data["condition"]["credit_period"] = credit_period

        return jsonify({
            "no_data": False,
            "ind_cor": ind_cor,
            "character": data["character"],
            "capital": data["capital"],
            "capacity": data["capacity"],
            "collateral": data["collateral"],
            "condition": data["condition"],
            "sid_checking": {"note": data["note_sid"], "rows": _survey_sid_checking(applno)},
        })

    except Exception:
        current_app.logger.exception("CAM survey error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/cam-notes")
@login_required
def get_cam_notes():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400
    try:
        notes = db.session.execute(
            text("SELECT CAM_NOTES FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"), {"applno": applno}
        ).scalar()
        return jsonify({"no_data": not notes, "notes": notes or ""})
    except Exception:
        current_app.logger.exception("CAM notes error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/other-notes")
@login_required
def get_other_notes():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400
    try:
        notes = db.session.execute(
            text("SELECT NOTES FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:applno"), {"applno": applno}
        ).scalar()
        return jsonify({"no_data": not notes, "notes": notes or ""})
    except Exception:
        current_app.logger.exception("CAM other notes error")
        return jsonify({"error": "Failed to load data"}), 500

APU_PPT_SQL = """
SELECT
    cl.LESSEE_NM, CASE WHEN cl.LESSEE_TP='PR' THEN 'Individu' ELSE 'Corporate' END AS lesse_tp,
    mlt.NAME, mc.DESC_VALUE,
    CASE WHEN SUBSTRING(cld.BUSINESS_TYPE,4,1)='H' THEN 'High Risk' ELSE 'Non High Risk' END AS status,
    CASE WHEN SUBSTRING(cld.BUSINESS_TYPE,4,1)='H' THEN 'Enhanced Due Diligence (EDD)' ELSE 'Customer Due Diligence (CDD)' END AS identity_Cus,
    bo.BO_Name,
    CASE WHEN bo.BO_TP='PR' THEN 'Individu' ELSE 'Corporate' END AS lesse_tp2,
    mlt1.NAME AS NAME2, mc1.DESC_VALUE AS DESC_VALUE2,
    CASE WHEN SUBSTRING(bo.BUSINESS_TYPE,4,1)='H' THEN 'High Risk' ELSE 'Non High Risk' END AS status2,
    CASE WHEN SUBSTRING(bo.BUSINESS_TYPE,4,1)='H' THEN 'Enhanced Due Diligence (EDD)' ELSE 'Customer Due Diligence (CDD)' END AS identity_BO
FROM
    CAFCONT cc WITH (NOLOCK)
    INNER JOIN CAFLESS cl WITH (NOLOCK) ON cl.APLESS=cc.APLESS
    LEFT JOIN CAFLESS_DETAIL cld WITH (NOLOCK) ON cld.APLESS=cc.APLESS
    LEFT JOIN MSTCOMBO mc WITH (NOLOCK) ON mc.VALUE=cld.BUSINESS_TYPE AND mc.CAT_VALUE IN ('PEP','USAHA_HIGH_RISK','KOPERASI_HIGH_RISK')
    INNER JOIN MSTLESSEETYPE mlt WITH (NOLOCK) ON mlt.CUST_TYPE=cl.Lessee_Cat
    LEFT JOIN BENEFICIARY_LINK bl WITH (NOLOCK) ON bl.APPL_NO=cc.APPL_NO
    LEFT JOIN BENEFICIARY_OWNER bo WITH (NOLOCK) ON bo.BO_ID=bl.BO_ID
    LEFT JOIN MSTLESSEETYPE mlt1 WITH (NOLOCK) ON mlt1.CUST_TYPE=bo.BO_Cat
    LEFT JOIN MSTCOMBO mc1 WITH (NOLOCK) ON mc1.VALUE=bo.BUSINESS_TYPE AND mc1.CAT_VALUE IN ('PEP','USAHA_HIGH_RISK','KOPERASI_HIGH_RISK')
WHERE cc.APPL_NO=:applno
"""

def _apu_ppt_main_row(applno):
    return db.session.execute(text(APU_PPT_SQL), {"applno": applno}).mappings().first()

def _apu_ppt_edd_flags(applno):
    row = db.session.execute(
        text("SELECT EDD_Customer, EDD_BO FROM Kuisioner_EDD WITH (NOLOCK) WHERE APPL_NO=:applno"),
        {"applno": applno}
    ).mappings().first()
    if not row:
        return "", ""
    return row.get("EDD_Customer") or "", row.get("EDD_BO") or ""

def _apu_ppt_questionnaire(cat_value):
    rows = db.session.execute(
        text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE cat_value=:cat"), {"cat": cat_value}
    ).all()
   
    return [{"no": r[0], "question": r[1], "answer": "YES"} for r in rows]

@cam_view_bp.route("/apu-ppt")
@login_required
def get_apu_ppt():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        main_row = _apu_ppt_main_row(applno)
        if main_row is None:
            return jsonify({"no_data": True})

        edd_customer, edd_bo = _apu_ppt_edd_flags(applno)
        bon = main_row.get("BO_Name") or "-"
        show_bo = bon != "-"

        return jsonify({
            "no_data": False,
            "customer": {
                "name": main_row.get("LESSEE_NM") or "-",
                "type": f"{main_row.get('lesse_tp', '')} / {main_row.get('NAME', '')}" if main_row.get("lesse_tp") else "-",
                "occupation_business_type": main_row.get("DESC_VALUE") or "-",
                "apu_ppt_status": main_row.get("status") or "-",
                "identification_verification": main_row.get("identity_Cus") or "-",
            },
            "show_edd_customer": edd_customer == "1",
            "edd_customer_questions": _apu_ppt_questionnaire("EDD_CustomerEng") if edd_customer == "1" else [],
            "show_beneficial_owner": show_bo,
            "beneficial_owner": {
                "name": bon,
                "type": f"{main_row.get('lesse_tp2', '')} / {main_row.get('NAME2', '')}" if main_row.get("lesse_tp2") else "-",
                "occupation_business_type": main_row.get("DESC_VALUE2") or "-",
                "apu_ppt_status": main_row.get("status2") or "-",
                "identification_verification": main_row.get("identity_BO") or "-",
            } if show_bo else None,
            "show_edd_bo": show_bo and edd_bo == "1",
            "edd_bo_questions": _apu_ppt_questionnaire("EDD_BOEng") if (show_bo and edd_bo == "1") else [],
        })

    except Exception:
        current_app.logger.exception("CAM APU PPT error")
        return jsonify({"error": "Failed to load data"}), 500

STATUS_LABELS = {"F": "Finish", "Y": "Outstanding", "T": "ET"}

def _history_payment_row_extras(lease_no, l_type):
    row_terminate = db.session.execute(
        text("""SELECT TOP 1 a.[status] AS status_, b.TENOR FROM bgiro a WITH (NOLOCK)
                 INNER JOIN clfcont b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                 WHERE a.LEASE_NO = :lease_no ORDER BY a.payment DESC, a.period DESC"""),
        {"lease_no": lease_no}
    ).mappings().first()

    if row_terminate and row_terminate["status_"] == "T":
        jlh_byr = row_terminate["TENOR"]
    else:
        row1 = db.session.execute(
            text("""SELECT COUNT(payment) AS jlh_byr, b.ADV_ARR FROM bgiro a WITH (NOLOCK)
                     INNER JOIN clfcont b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                     WHERE a.LEASE_NO = :lease_no AND PAYMENT IS NOT NULL AND STATUS NOT IN ('T','P')
                     GROUP BY b.ADV_ARR"""),
            {"lease_no": lease_no}
        ).mappings().first()
        if row1:
            jlh_byr = (row1["jlh_byr"] + 1) if row1["ADV_ARR"] == "V" else row1["jlh_byr"]
        else:
            jlh_byr = 0

    tenor_col = "tenor1000" if l_type == "4" else "tenor"
    tenor_kontrak = db.session.execute(
        text(f"SELECT {tenor_col} AS tenor FROM CLFCONT WITH (NOLOCK) WHERE LEASE_NO = :lease_no"),
        {"lease_no": lease_no}
    ).scalar()

    jumlah_reject = db.session.execute(
        text("SELECT COUNT([STATUS]) AS c FROM BGIRO WITH (NOLOCK) WHERE LEASE_NO = :lease_no AND [STATUS]='R'"),
        {"lease_no": lease_no}
    ).scalar() or 0

    return jlh_byr, tenor_kontrak, jumlah_reject

def _history_payment_build_row(no, r):
    lease_no = r["LEASE_NO"]
    jlh_byr, tenor_kontrak, jumlah_reject = _history_payment_row_extras(lease_no, r.get("L_TYPE"))
    return {
        "no": no,
        "lease_no": lease_no,
        "lessee_no": r.get("LESSEE_NO"),
        "status": STATUS_LABELS.get(r.get("UPD_STAT"), r.get("UPD_STAT") or ""),
        "term_paid": jlh_byr,
        "term_total": tenor_kontrak,
        "reject_count": jumlah_reject,
        "disbursement_date": _fmt_date(r.get("EXECUTION")),
    }

def _history_payment_list1(apless, applno):
    rows = db.session.execute(
        text("""
            SELECT LEASE_NO, EXECUTION, LESSEE_NO, UPD_STAT, L_TYPE FROM (
                SELECT a.LEASE_NO, a.EXECUTION, a.ET_DT, a.LESSEE_NO, a.UPD_STAT, a.L_TYPE
                FROM CLFCONT a WITH (NOLOCK)
                    INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                WHERE a.EXECUTION IS NOT NULL AND a.FLGDEL <> '1' AND b.APLESS = :apless1
                  AND (a.UPD_STAT = 'Y' OR (a.UPD_STAT = 'T' AND a.ET_DT > DATEADD(year,-1,GETDATE())))

                UNION

                SELECT c.LEASE_NO, c.EXECUTION, c.ET_DT, c.LESSEE_NO, c.UPD_STAT, c.L_TYPE
                FROM CLFCONT c WITH (NOLOCK)
                    INNER JOIN CAFCONT d WITH (NOLOCK) ON c.APPL_NO = d.APPL_NO
                    INNER JOIN BGIRO e WITH (NOLOCK) ON c.LEASE_NO = e.LEASE_NO
                WHERE c.EXECUTION IS NOT NULL AND d.APLESS = :apless2 AND c.UPD_STAT = 'F'
                  AND e.PAYMENT IN (SELECT TOP 1 PAYMENT FROM BGIRO WHERE LEASE_NO = c.LEASE_NO ORDER BY PAYMENT DESC)
                  AND e.GIRODT IN (SELECT TOP 1 GIRODT FROM BGIRO WHERE LEASE_NO = c.LEASE_NO ORDER BY GIRODT DESC)
                  AND e.PAYMENT > DATEADD(year,-1,GETDATE())

                UNION

                SELECT f.LEASE_NO, f.EXECUTION, f.ET_DT, f.LESSEE_NO, f.UPD_STAT, f.L_TYPE
                FROM CLFCONT f WITH (NOLOCK)
                    LEFT JOIN TACrossNo h WITH (NOLOCK) ON f.APPL_NO = h.APPL_NO AND h.CROSS_TYPE = 'CN'
                WHERE f.LEASE_NO IN (SELECT Crossno FROM TACrossNo WITH (NOLOCK) WHERE APPL_NO = :applno)
                    AND h.Crossno IS NOT NULL AND h.Crossno <> ''
                    AND f.LEASE_NO IN (
                        SELECT a.LEASE_NO FROM CLFCONT a WITH (NOLOCK)
                            INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                        WHERE a.EXECUTION IS NOT NULL AND a.FLGDEL <> '1' AND b.APLESS = :apless3
                            AND (a.UPD_STAT = 'Y' OR (a.UPD_STAT = 'T' AND a.ET_DT > DATEADD(year,-1,GETDATE())))
                    )
            ) t
            ORDER BY LEASE_NO
        """),
        {"apless1": apless, "apless2": apless, "apless3": apless, "applno": applno}
    ).mappings().all()

    deduped = []
    last_lease_no = None
    for r in rows:
        if r["LEASE_NO"] != last_lease_no:
            deduped.append(r)
            last_lease_no = r["LEASE_NO"]
    return deduped

def _history_payment_list2(apless):
    rows = db.session.execute(
        text("""
            SELECT a.LEASE_NO, a.EXECUTION, a.LESSEE_NO, a.UPD_STAT, a.L_TYPE
            FROM CLFCONT a WITH (NOLOCK)
                INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            WHERE b.APLESS IN (
                SELECT apless FROM CAFLESS WITH (NOLOCK)
                WHERE GrpCode IN (
                    SELECT GrpCode
                    FROM CAFLESS WITH (NOLOCK)
                    WHERE APLESS = :apless1 AND GrpCode NOT IN ('001','002') AND GrpCode <> ''
                )
                AND GrpCode NOT IN ('001','002') AND APLESS <> :apless2
            )
            AND a.UPD_STAT IN ('Y','T','F') AND a.EXECUTION > DATEADD(year,-1,GETDATE())
            ORDER BY a.LEASE_NO
        """),
        {"apless1": apless, "apless2": apless}
    ).mappings().all()
    return rows

@cam_view_bp.route("/history-payment/contract")
@login_required
def get_history_payment_contract():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 25, type=int)
    if not apless:
        return jsonify({"error": "Missing apless"}), 400
    try:
        all_rows = _history_payment_list1(apless, applno)
        total = len(all_rows)
        offset, end = (page - 1) * limit, page * limit
        page_rows = all_rows[offset:end]
        data = [_history_payment_build_row(i + 1, r) for i, r in enumerate(page_rows)]
        return jsonify({"total": total, "page": page, "limit": limit, "rows": data})
    except Exception:
        current_app.logger.exception("CAM history payment (contract) error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/history-payment/group")
@login_required
def get_history_payment_group():
    apless = request.args.get("apless", "")
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 25, type=int)
    if not apless:
        return jsonify({"error": "Missing apless"}), 400
    try:
        all_rows = _history_payment_list2(apless)
        total = len(all_rows)
        offset, end = (page - 1) * limit, page * limit
        page_rows = all_rows[offset:end]
        data = [_history_payment_build_row(i + 1, r) for i, r in enumerate(page_rows)]
        return jsonify({"total": total, "page": page, "limit": limit, "rows": data})
    except Exception:
        current_app.logger.exception("CAM history payment (group) error")
        return jsonify({"error": "Failed to load data"}), 500

def _af_load_docs(apless, applno, doc_type_filter):
    rows = db.session.execute(text("""
        SELECT a.AWSKey, a.file_document AS file_name, a.DocumentType
        FROM   CUSTOMER_DOCUMENT a WITH (NOLOCK)
            LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.appl_no = b.APPL_NO
        WHERE  a.doc_type = :dt AND a.APPL_NO = :applno
               AND a.APLESS = :apless AND a.APLESS IS NOT NULL
        ORDER BY a.DocumentType, a.Upload_Dt DESC
    """), {"dt": doc_type_filter, "applno": applno, "apless": apless}).mappings().all()
    docs: dict = {}
    for r in rows:
        fn = r.get("file_name")
        ak = r.get("AWSKey") or ""
        dt = r.get("DocumentType")
        if fn and fn != "-" and dt:
            docs.setdefault(dt, []).append({"file_name": fn, "aws_key": ak})
    return docs

def _af_load_survey(apless, applno, survey_type=None):
    if survey_type:
        rows = db.session.execute(text("""
            SELECT DocumentName AS file_name, AWSKey, DocumentType
            FROM   SURVEY_FILE WITH (NOLOCK)
            WHERE  Apless = :apless AND ApplNo = :applno
                   AND SurveyType = :st
            ORDER BY DocumentType, CreatedDate
        """), {"apless": apless, "applno": applno, "st": survey_type}).mappings().all()
    else:
        rows = db.session.execute(text("""
            SELECT DocumentName AS file_name, AWSKey, DocumentType
            FROM   SURVEY_FILE WITH (NOLOCK)
            WHERE  Apless = :apless AND ApplNo = :applno
                   AND DocumentType IN ('home-survey','office-survey','other-survey')
            ORDER BY DocumentType, CreatedDate
        """), {"apless": apless, "applno": applno}).mappings().all()
    result: dict = {}
    for r in rows:
        fn = r.get("file_name")
        ak = r.get("AWSKey") or ""
        dt = r.get("DocumentType")
        if fn and dt:
            result.setdefault(dt, []).append({"file_name": fn, "aws_key": ak})
    return result

@cam_view_bp.route("/all-files")
@login_required
def get_all_files():
    apless  = request.args.get("apless", "")
    applno  = request.args.get("applno", "")
    ind_cor = request.args.get("ind_cor", "1")
    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400
    try:
        lez = (db.session.execute(
            text("SELECT Lessee_Cat, Citizen FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :a"),
            {"a": apless}
        ).mappings().first() or {})
        lessee_cat = lez.get("Lessee_Cat") or ""
        citizen    = lez.get("Citizen")    or "WNI"

        spz = (db.session.execute(
            text("SELECT SPOUSE_CITIZEN FROM CAFLESS_Detail WITH (NOLOCK) WHERE APLESS = :a"),
            {"a": apless}
        ).mappings().first() or {})
        spouse_citizen = spz.get("SPOUSE_CITIZEN") or "WNI"

        bank_rows = db.session.execute(text("""
            SELECT DocumentName AS file_name, AWSKey
            FROM   BANK_STATEMENT_DOCUMENT WITH (NOLOCK)
            WHERE  Apless = :apless AND ApplNo = :applno
            ORDER BY CreatedDate
        """), {"apless": apless, "applno": applno}).mappings().all()
        bank_statement = [
            {"file_name": r["file_name"], "aws_key": r.get("AWSKey") or ""}
            for r in bank_rows if r.get("file_name")
        ]

        customer_documents = _af_load_docs(apless, applno, "non")

        grn_rows = db.session.execute(
            text("SELECT GRNTP, GRNID FROM CAFGUARN WITH (NOLOCK) WHERE APPL_NO = :applno"),
            {"applno": applno}
        ).mappings().all()
        has_guarantor     = len(grn_rows) > 0
        guarantor_type_pr = next((r["GRNTP"] for r in grn_rows if r.get("GRNTP") == "PR"), None)
        guarantor_type_pt = next((r["GRNTP"] for r in grn_rows if r.get("GRNTP") == "PT"), None)

        guarantor_documents    = _af_load_docs(apless, applno, "guarn") if has_guarantor else {}
        guarantor_bank_stmt: list = []
        if has_guarantor:
            gb = db.session.execute(text("""
                SELECT d.DocumentName AS file_name, d.AWSKey
                FROM   GUARANTOR_BANK_STATEMENT_DOCUMENT d WITH (NOLOCK)
                INNER JOIN CAFGUARN g WITH (NOLOCK) ON d.GuarantorId = g.GRNID
                WHERE  g.APPL_NO = :applno
                ORDER BY d.CreatedDate DESC
            """), {"applno": applno}).mappings().all()
            guarantor_bank_stmt = [
                {"file_name": r["file_name"], "aws_key": r.get("AWSKey") or ""}
                for r in gb if r.get("file_name")
            ]

        cust_survey = _af_load_survey(apless, applno)
        eq_survey   = _af_load_survey(apless, applno, survey_type="vehicle-survey")

        appr = db.session.execute(
            text("SELECT appr_sts FROM V_LastCAMStatusApproval WITH (NOLOCK) WHERE appl_no = :applno"),
            {"applno": applno}
        ).mappings().first()
        is_approved = (appr or {}).get("appr_sts") or ""

        return jsonify({
            "ind_cor": ind_cor,
            "lessee_cat": lessee_cat,
            "citizen": citizen,
            "spouse_citizen": spouse_citizen,
            "customer_documents": customer_documents,
            "bank_statement": bank_statement,
            "has_guarantor": has_guarantor,
            "guarantor_type_pr": guarantor_type_pr,
            "guarantor_type_pt": guarantor_type_pt,
            "guarantor_documents": guarantor_documents,
            "guarantor_bank_statement": guarantor_bank_stmt,
            "cust_survey": cust_survey,
            "eq_survey": eq_survey,
            "is_approved": is_approved,
            "applno": applno,
            "apless": apless,
        })
    except Exception:
        current_app.logger.exception("CAM all-files error")
        return jsonify({"error": "Failed to load data"}), 500

def _cam_appr_access_level(applno, username, base_level):
    row = db.session.execute(text("""
        SELECT TOP 1 [Role] FROM MCMOCAMStatus WITH (NOLOCK)
        WHERE APPL_NO=:a AND APPR_ID=:u ORDER BY [No] DESC
    """), {"a": applno, "u": username}).mappings().first()
    return row["Role"] if (row and row.get("Role")) else base_level

def _cam_appr_form_id(applno, tot_outs, access_level):
    if access_level != "CMO" and tot_outs is not None:
        r = db.session.execute(text("""
            SELECT TOP 1 ApprovalFormId FROM mstCamApprovalFlow WITH (NOLOCK)
            WHERE :outs BETWEEN OutstandingFrom AND OutstandingTo ORDER BY OutstandingTo DESC
        """), {"outs": float(tot_outs)}).mappings().first()
        if r: return r.get("ApprovalFormId") or 1
        r2 = db.session.execute(text(
            "SELECT ApprovalFormId FROM documentApproval WITH (NOLOCK) WHERE DocumentNumber=:a"),
            {"a": applno}).mappings().first()
        if r2: return r2.get("ApprovalFormId") or 1
    return 1

def _cam_appr_next_available_approver(current_approval_level, approval_form_id, branch_code, username="", appr_plafond=None):
  
    next_approval_level = int(current_approval_level or 0) + 1
    row = db.session.execute(
        text("EXEC USP_CAM_GETAVAILABLEAPPROVER :lvl, :fid, :branch, :user, :plafond"),
        {
            "lvl": next_approval_level,
            "fid": approval_form_id,
            "branch": branch_code,
            "user": username,
            "plafond": appr_plafond,
        },
    ).mappings().first()

    if row is None:
        return None

    approver_username = (row.get("USERNAME") or "").strip()
    if approver_username:
        return approver_username, row.get("AccessLevel") or ""
    return "Admin", "Admin"

def _cam_appr_next_approvers(current_approval_level, approval_form_id, branch_code, username, appr_plafond):
    
    result = _cam_appr_next_available_approver(
        current_approval_level, approval_form_id, branch_code, username, appr_plafond
    )
    if result is None:
        return []

    approver_username, approver_access_level = result
    value = f"{approver_username}|{approver_access_level}"
    label = "Send to Admin" if approver_username.upper() == "ADMIN" else approver_username
    return [{"value": value, "label": label}]

def _cam_appr_fd_warning(apless, fin_type):
    if fin_type not in ("D", "M", "W"): return "", False
    try:
        fd = float((db.session.execute(text("""
            SELECT SUM(outstanding) AS v FROM V_CustomerOutstanding WITH (NOLOCK)
            WHERE Cons_Leas='D' AND APLESS=:a"""), {"a": apless}).mappings().first() or {}).get("v") or 0)
        fm = float((db.session.execute(text("""
            SELECT SUM(outstanding) AS v FROM V_CustomerOutstanding WITH (NOLOCK)
            WHERE Cons_Leas='M' AND APLESS=:a"""), {"a": apless}).mappings().first() or {}).get("v") or 0)
        if fin_type == "D" and fd > 500_000_000:
            return ('Grand Total Outstanding for Fund Facility (FF) > Rp. 500.000.000,-', True)
        if fin_type == "M" and fm > 10_000_000_000:
            return ('Grand Total Outstanding for Business Capital Facility (FMU) > Rp. 10.000.000.000,-', True)
        return "", False
    except Exception: return "", False
    
@cam_view_bp.route("/approval")
@login_required
def get_cam_approval():
    apless   = request.args.get("apless", "")
    applno   = request.args.get("applno", "")
    fin_type = request.args.get("fin_type", "")
    ind_cor  = request.args.get("ind_cor", "1")
    if not apless or not applno: return jsonify({"error": "Missing apless/applno"}), 400

    username  = session.get("username", "")
    base_al   = session.get("accesslevel", "")
    branch_cd = session.get("branchcode", "")

    try:
        status_rows = db.session.execute(text("""
            SELECT [No], [Role], APPR_STS, APPR_ID, APPR_DATE, APPR_ID_From
            FROM MCMOCAMStatus WITH (NOLOCK)
            WHERE APPL_NO=:a
            ORDER BY [No] DESC
        """), {"a": applno}).mappings().all()

        user_row = next((r for r in status_rows if (r.get("APPR_ID") or "").upper() == username.upper()), None)
        access_level = (user_row.get("Role") if user_row else None) or base_al

        cont = (db.session.execute(text("""
            SELECT a.CORP_RET, a.L_AMOUNT, a.PURPOFFINC, b.Strength, b.Weakness, b.Tbo
            FROM CAFCONT a WITH (NOLOCK)
            LEFT JOIN CAFCONT_DETAIL b WITH (NOLOCK) ON a.Appl_No=b.Appl_No
            WHERE a.APPL_NO=:a"""), {"a": applno}).mappings().first() or {})
        mstr = cont
        is_multiple = (mstr.get("CORP_RET") or "") == "M"
        multiple_appl_nos = applno
        if is_multiple:
            mnos = db.session.execute(text("""
                SELECT APPL_NO FROM TAMASTER WITH (NOLOCK)
                WHERE MSTR_CA IN (SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO=:a)
            """), {"a": applno}).mappings().all()
            multiple_appl_nos = ",".join(r["APPL_NO"] for r in mnos)
        rev = (db.session.execute(text(
            "SELECT REVISI FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO=:a"),
            {"a": multiple_appl_nos}).mappings().first() or {})
        cam_no_display = multiple_appl_nos + (f"R{rev['REVISI']}" if rev.get("REVISI") else "")

        info = (db.session.execute(text("""
            SELECT LTRIM(RTRIM(a.CMO)) AS CMO, b.LESSEE_NM, c.USERNAME,
                   b.lessee_cat, b.LESSEE_TP, b.ID_CARD, b.NPWP, b.ADDRESS1
            FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS=b.APLESS
                LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO=c.EMPLOYEE_ID
            WHERE a.APPL_NO=:a
        """), {"a": applno}).mappings().first() or {})
        lessee_nm = info.get("LESSEE_NM") or ""

        rejection_message = ""
        withdrawn_message = ""

        top = status_rows[0] if status_rows else {}
        top_sts = top.get("APPR_STS") or ""

        if access_level not in ("CMO", "NCH", "ODH", "DR"):
            if top.get("APPR_STS") == "T" and (top.get("APPR_ID") or "").upper() == username.upper():
                withdrawn_message = f"This CAM has been withdrawn by {top.get('APPR_ID_From', '')}"
            elif top.get("APPR_STS") == "R" and (top.get("APPR_ID") or "").upper() != username.upper():
                rejection_message = f"This CAM has been rejected by {top.get('APPR_ID', '')}"

        sent = next((r for r in status_rows if r.get("APPR_STS") == "F"), None)
        already_sent = sent is not None
        sent_date = _fmt_date(sent["APPR_DATE"]) if sent else None

        is_completed = any(r.get("APPR_STS") == "E" for r in status_rows)

        prog = next((r for r in status_rows if r.get("APPR_STS") == "P"), None)
        in_progress_by = (prog or {}).get("APPR_ID")
        can_act = (not is_completed and not already_sent and
                   (in_progress_by is None or (in_progress_by or "").upper() == username.upper()))
        if withdrawn_message:
            can_act = False

        STATUS_LBL = {"A": "Approved", "F": "Approved & Send to Admin",
                      "R": "Reject", "N": "Send for Approval"}
        hist = db.session.execute(text("""
            SELECT * FROM (
                SELECT a.[No], a.APPR_ID, a.APPR_DATE,
                       CAST(a.COMMENT AS VARCHAR(5000)) AS COMMENT,
                       SUBSTRING(a.APPR_STS,1,1) AS APPR_STS, b.FULLNAME,
                       CASE WHEN a.IsNotRecommend=1 THEN 'No'
                            WHEN a.IsNotRecommend=0 THEN 'Yes' ELSE '-' END AS Rec
                FROM MCMOCAMStatus a WITH (NOLOCK)
                    INNER JOIN APP_USRMST b ON b.USERNAME=a.APPR_ID
                WHERE a.APPL_NO=:a
                  AND (a.APPR_STS IN ('N','A','F','R') OR a.APPR_STS LIKE '%R')
            ) x ORDER BY APPR_DATE, [No]
        """), {"a": applno}).mappings().all()
        approval_history = [
            {"date": r["APPR_DATE"].strftime("%d-%m-%Y %H:%M:%S") if r.get("APPR_DATE") else "",
             "full_name": r.get("FULLNAME") or r.get("APPR_ID") or "",
             "status_label": STATUS_LBL.get(r.get("APPR_STS") or "", r.get("APPR_STS") or ""),
             "comment": r.get("COMMENT") or "",
             "recommendation": r.get("Rec") or "-",
             "not_recommend": r.get("Rec") == "No"}
            for r in hist if r.get("APPR_STS") != "T"
        ]

        ots_v = (db.session.execute(text("""
            SELECT SUM(OUTS) AS v FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a
            AND ASOF=(SELECT MAX(ASOF) FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a2)
        """), {"a": applno, "a2": applno}).mappings().first() or {}).get("v")
        form_id = _cam_appr_form_id(applno, ots_v, access_level)
        al_row = (db.session.execute(text("""
            SELECT ApprovalLevel FROM mstApprovalMatrix WITH (NOLOCK)
            WHERE ApprovalFormId=:fid AND AccessLevel=:al
        """), {"fid": form_id, "al": access_level}).mappings().first() or {})
        appr_lvl = al_row.get("ApprovalLevel") or 0

        appr_plafond = None
        if access_level != "CMO":
            plafond_row = (db.session.execute(text("""
                SELECT TOP 1 OutstandingTo FROM mstCamApprovalFlow WITH (NOLOCK)
                WHERE :ots BETWEEN OutstandingFrom AND OutstandingTo
                ORDER BY OutstandingTo DESC
            """), {"ots": ots_v or 0}).mappings().first() or {})
            appr_plafond = plafond_row.get("OutstandingTo")

        next_opts = _cam_appr_next_approvers(appr_lvl, form_id, branch_cd, username, appr_plafond) if can_act else []
        warning, disabled = _cam_appr_fd_warning(apless, fin_type)

        eq = (db.session.execute(text("""
            SELECT cd.IsRedCode, cd.GPS_Vendor FROM CAFEQUIP a WITH (NOLOCK)
            LEFT JOIN CAFEQUIP_DETAIL cd WITH (NOLOCK) ON a.CAFEQUIP_ID=cd.CAFEQUIP_ID
            WHERE a.APPL_NO=:a"""), {"a": applno}).mappings().first() or {})
        gps_vendors = db.session.execute(text(
            "SELECT SUPP, NAME FROM VENDOR WITH (NOLOCK) WHERE Supp_Category='GPS' ORDER BY NAME"
        )).mappings().all()

        crd = cont
        purpoffinc_val = crd.get("PURPOFFINC") or ""

        ri_row = (db.session.execute(text(
            "SELECT Result_Independent FROM mcmocamcompletelist WITH (NOLOCK) WHERE APPL_NO=:a"),
            {"a": applno}).mappings().first() or {})
        result_independent = ri_row.get("Result_Independent") or ""

        SURV_ALS = ("CR","CRH","CH","ODH","DR","PD","CRUH","CRDH","OPDH")
        show_survey = access_level in SURV_ALS
        mat_in = mat_kau = False
        adaisi = ""
        if can_act:
            if result_independent:
                adaisi = "1"
                if access_level == "CRH":
                    mat_in = True; mat_kau = result_independent != "1"
                elif access_level in ("CH","ODH","DR","PD","CRUH","OPDH"):
                    mat_in = mat_kau = True
            else:
                adaisi = "" if access_level == "CR" else "0"
                if access_level == "CRH": mat_kau = True
                elif access_level in ("CH","ODH","DR","PD","CRUH","OPDH"): mat_in = mat_kau = True

        surv_opts = db.session.execute(text(
            "SELECT VALUE, DESC_VALUE FROM mstcombo WITH (NOLOCK) WHERE CAT_VALUE='YES_NO'"
        )).mappings().all()
        ri_opts = db.session.execute(text(
            "SELECT VALUE, DESC_VALUE FROM mstcombo WITH (NOLOCK) WHERE CAT_VALUE='Result_Independent'"
        )).mappings().all() if result_independent else []

        show_form = can_act and not is_completed and top_sts != "R"

        tot_nf_end = 0.0
        if purpoffinc_val in ("3", "4"):
            nf = (db.session.execute(text(
                "SELECT SUM(Net_Finance) AS v FROM V_NetFinance WITH (NOLOCK) WHERE APPL_NO=:a"),
                {"a": applno}).mappings().first() or {})
            tot_nf_end = float(nf.get("v") or 0)

        return jsonify({
            "cam_no_display": cam_no_display,
            "lessee_nm": lessee_nm,
            "cmo_nm": info.get("USERNAME") or "",
            "access_level": access_level,
            "username": username,
            "can_act": can_act,
            "in_progress_by": in_progress_by,
            "is_completed": is_completed,
            "already_sent_to_admin": already_sent,
            "sent_to_admin_date": sent_date,
            "warning": warning,
            "disabled": disabled,
            "rejection_message": rejection_message,
            "withdrawn_message": withdrawn_message,
            "approval_history": approval_history,
            "show_form": show_form,
            "show_watchlist_option": access_level in ("BM","CRH","CH","ODH","DR","PD","CRUH","OPDH"),
            "show_credit_recommendation": access_level == "CRH",
            "show_survey_section": show_survey,
            "strength": (crd.get("Strength") or "").replace("<br />", "\n") if access_level == "CRH" else "",
            "weakness": (crd.get("Weakness") or "").replace("<br />", "\n") if access_level == "CRH" else "",
            "tbo": (crd.get("Tbo") or "").replace("<br />", "\n") if access_level == "CRH" else "",
            "survey_independent_value": adaisi,
            "result_independent_value": result_independent,
            "survey_options": [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in surv_opts],
            "result_options": [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in ri_opts],
            "mat_in": mat_in,
            "mat_kau": mat_kau,
            "next_approver_options": next_opts,
            "red_code_selected": (eq.get("IsRedCode") or "0") == "1",
            "gps_vendor": eq.get("GPS_Vendor") or "",
            "gps_vendors": [{"value": r["SUPP"], "label": r["NAME"]} for r in gps_vendors],
            "purpoffinc": purpoffinc_val,
            "tot_net_finance_end": tot_nf_end,
            "is_cmo": access_level == "CMO",
            "is_multiple": is_multiple,
            "multiple_appl_nos": multiple_appl_nos,
            "watchlist": _get_approval_watchlist(apless),
        })
    except Exception:
        current_app.logger.exception("CAM approval GET error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/approval/result-options")
@login_required
def get_approval_result_options():
    if request.args.get("isisurv") == "1":
        rows = db.session.execute(text(
            "SELECT VALUE, DESC_VALUE FROM mstcombo WITH (NOLOCK) WHERE CAT_VALUE='Result_Independent'"
        )).mappings().all()
        return jsonify([{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in rows])
    return jsonify([])

@cam_view_bp.route("/approval/confirm", methods=["POST"])
@login_required
def post_cam_approval_confirm():
    username  = session.get("username", "")
    base_al   = session.get("accesslevel", "")
    branch_cd = session.get("branchcode", "")
    emp_id    = session.get("emp_id", "")

    data = request.get_json() or {}
    applno       = data.get("applno", "")
    apless       = data.get("apless", "")
    approval_sts = data.get("approval_sts", "A")
    next_appr    = data.get("next_appr", "")
    comment      = (data.get("comment") or "").replace("'", "`")
    send_to_admin = int(data.get("send_to_admin", 0))
    strength     = (data.get("strength") or "").replace("\n", "<br />")
    weakness     = (data.get("weakness") or "").replace("\n", "<br />")
    tbo_val      = (data.get("tbo") or "").replace("\n", "<br />")
    not_recommend = data.get("not_recommend", 0)
    red_code     = data.get("red_code", "0")
    gps_vendor   = data.get("gps_vendor", "")
    isiresult    = data.get("isiresult", "")
    resulti      = data.get("resulti", "")
    ind_cor      = data.get("ind_cor", "1")

    if not applno or not apless:
        return jsonify({"error": "Missing applno/apless"}), 400

    try:
        access_level = _cam_appr_access_level(applno, username, base_al)
        mstr = (db.session.execute(text(
            "SELECT CORP_RET, L_AMOUNT FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a"),
            {"a": applno}).mappings().first() or {})
        is_multiple  = (mstr.get("CORP_RET") or "") == "M"
        l_amount     = float(mstr.get("L_AMOUNT") or 0)
        applno_t2    = applno
        if is_multiple:
            mnos = db.session.execute(text("""
                SELECT APPL_NO FROM TAMASTER WITH (NOLOCK)
                WHERE MSTR_CA IN (SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO=:a)
            """), {"a": applno}).mappings().all()
            applno_t2 = ",".join(r["APPL_NO"] for r in mnos)

        top = (db.session.execute(text("""
            SELECT TOP 1 APPR_STS, APPR_ID, APPR_ID_From FROM MCMOCAMStatus WITH (NOLOCK)
            WHERE APPL_NO=:a ORDER BY No DESC
        """), {"a": applno}).mappings().first() or {})
        if top.get("APPR_STS") == "P" and (top.get("APPR_ID") or "").upper() != username.upper():
            return jsonify({"redirect": True, "message": f"This CAM has been taken over by {top.get('APPR_ID')}"})
        if top.get("APPR_STS") == "T" and (top.get("APPR_ID") or "").upper() == username.upper():
            return jsonify({"redirect": True, "message": f"Your CAM has been withdrawn by {top.get('APPR_ID_From')}"})

        if approval_sts in ("R", "RW"):
            if not comment: return jsonify({"error": "Comment must not be empty"}), 400
            for appl in [a.strip() for a in applno_t2.split(",") if a.strip()]:
                is_rw = approval_sts == "RW"
                ac = "reject-to-watchlist" if is_rw else "reject"
                ds = "rejected-to-watchlist" if is_rw else "rejected"
                rmk = f"{access_level} has rejected CAM No. {appl}" + (" to watchlist" if is_rw else "")
                for p in db.session.execute(text("""
                    SELECT APPR_STS, [No] FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO=:a AND APPR_STS<>'P' AND APPR_STS NOT LIKE '%R'
                """), {"a": appl}).mappings().all():
                    s = p["APPR_STS"]
                    ns = s[1]+"R" if len(s)==2 else (("TR") if s=="T" else s+"R")
                    if s == "T":
                        db.session.execute(text(
                            "DELETE FROM MCMOCAMStatus WHERE APPL_NO=:a AND [No]=:n AND APPR_STS='T'"),
                            {"a": appl, "n": p["No"]})
                    db.session.execute(text(
                        "UPDATE MCMOCAMStatus SET APPR_STS=:ns WHERE APPL_NO=:a AND [No]=:n"),
                        {"ns": ns, "a": appl, "n": p["No"]})
                db.session.execute(text("""
                    UPDATE MCMOCAMStatus SET APPR_STS=:sts,COMMENT=:cmt,
                    APPR_DATE=GETDATE(),IsNotRecommend=:nr WHERE APPL_NO=:a AND APPR_STS='P'
                """), {"sts": approval_sts, "cmt": comment, "nr": not_recommend, "a": appl})
                db.session.execute(text("""
                    UPDATE documentApproval SET Progress=0,CurrentApprover=NULL,
                    DocumentStatusCode=:ds,LastApprovalActionCode=:ac,LastActionBy=:u,
                    LastActionDate=GETDATE(),UpdatedBy=:u2,UpdatedDate=GETDATE()
                    WHERE DocumentNumber=:dn
                """), {"ds": ds, "ac": ac, "u": username, "u2": username, "dn": appl})
                db.session.execute(text("""
                    INSERT INTO documentApprovalHistory
                        (DocumentApprovalId,ApprovalActionCode,Remarks,CreatedBy,CreatedDate)
                    VALUES((SELECT TOP 1 Id FROM documentApproval WHERE DocumentNumber=:dn),:ac,:rmk,:u,GETDATE())
                """), {"dn": appl, "ac": ac, "rmk": rmk, "u": username})
                db.session.execute(text("DELETE TAMASTER WHERE appl_no=:a"), {"a": appl})
                if is_rw:
                    current_app.logger.warning("RW: MCMOWatchList mutation NOT implemented for %s", appl)
            db.session.commit()
            return jsonify({"success": True, "redirect": True})

        bpkb = (db.session.execute(text("SELECT BPKB_AN_TP FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}).mappings().first() or {})
        if not (bpkb.get("BPKB_AN_TP") or "").strip(): return jsonify({"error": "BPKB Name Type is empty"}), 422

        em = (db.session.execute(text("""SELECT EMAIL1 FROM CAFLESS WITH (NOLOCK)
            WHERE APLESS=(SELECT APLESS FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a)"""), {"a": applno}).mappings().first() or {})
        if not em.get("EMAIL1"): return jsonify({"error": "Email 1 must not be empty"}), 422

        sp_c = (db.session.execute(text("""
            SELECT cc.MARITAL,cd.SPOUSE_MobilePhone,cd.SPOUSE_Email FROM CAFCONT c WITH (NOLOCK)
            INNER JOIN CAFLESS cc WITH (NOLOCK) ON cc.APLESS=c.APLESS
            LEFT JOIN CAFLESS_DETAIL cd WITH (NOLOCK) ON cd.APLESS=cc.APLESS WHERE c.APPL_NO=:a
        """), {"a": applno}).mappings().first() or {})
        if sp_c.get("MARITAL") == "M":
            if not sp_c.get("SPOUSE_MobilePhone"): return jsonify({"error": "Spouse Mobile Phone No. must not be empty"}), 422
            if not sp_c.get("SPOUSE_Email"):        return jsonify({"error": "Spouse Email must not be empty"}), 422

        cl = (db.session.execute(text("""
            SELECT cont_type,Notary_no,ISNULL(Gross,0) AS Gross,Cons_Leas
            FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a"""), {"a": applno}).mappings().first() or {})
        if not (cl.get("cont_type") or "").strip(): return jsonify({"error": "Contract Type is empty"}), 422
        if cl.get("Cons_Leas") != "F":
            if (cl.get("Notary_no") or "").strip():
                if float(cl.get("Gross") or 0) <= 0: return jsonify({"error": "Gross Amount must be more than 0"}), 422
            else: return jsonify({"error": "Please fill Notary in Equipment BPKB"}), 422

        if not db.session.execute(text("SELECT 1 FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}).mappings().first():
            return jsonify({"error": "Calculate Total Outstanding first!"}), 422

        for sr in db.session.execute(text("SELECT Phone,Email FROM V_ContractSigner WHERE appl_no=:a"), {"a": applno}).mappings().all():
            if not sr.get("Phone"): return jsonify({"error": "Mobile Phone No. must not be empty"}), 422
            if not sr.get("Email"): return jsonify({"error": "Email must not be empty"}), 422

        if red_code == "1" and not gps_vendor: return jsonify({"error": "Please select GPS Vendor"}), 422

        target_appl_nos = [a.strip() for a in applno_t2.split(",") if a.strip()] if is_multiple else [applno]

        for a in target_appl_nos:
            if not db.session.execute(text("SELECT Cafequip_ID FROM Cafequip_Detail WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": a}).mappings().first():
                db.session.execute(text("INSERT INTO Cafequip_Detail (Cafequip_ID,APPL_NO,IsRedCode,GPS_Vendor) SELECT cafequip_id,appl_no,:rc,:gv FROM CAFEQUIP WHERE APPL_NO=:a"), {"rc": red_code, "gv": gps_vendor, "a": a})
            else:
                db.session.execute(text("UPDATE CAFEQUIP_DETAIL SET IsRedCode=:rc,GPS_Vendor=:gv WHERE APPL_NO=:a"), {"rc": red_code, "gv": gps_vendor, "a": a})

            if access_level == "CRH":
                if db.session.execute(text("SELECT 1 FROM CAFCONT_DETAIL WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": a}).mappings().first():
                    db.session.execute(text("UPDATE CAFCONT_DETAIL SET Strength=:s,Weakness=:w,Tbo=:t WHERE Appl_No=:a"), {"s": strength, "w": weakness, "t": tbo_val, "a": a})
                else:
                    db.session.execute(text("INSERT INTO CAFCONT_DETAIL (Appl_No,Strength,Weakness,Tbo) VALUES (:a,:s,:w,:t)"), {"a": a, "s": strength, "w": weakness, "t": tbo_val})

            if access_level == "CR":
                rv = isiresult or None
                db.session.execute(text("UPDATE mcmocamcompletelist SET Result_Independent=:v WHERE APPL_NO=:a"), {"v": rv, "a": a})
            elif access_level in ("CRH", "CRDH", "DR", "PD"):
                rv = isiresult or (resulti if resulti in ("2", "3") else None)
                db.session.execute(text("UPDATE mcmocamcompletelist SET Result_Independent=:v WHERE APPL_NO=:a"), {"v": rv, "a": a})

        if access_level == "CMO":
            db.session.execute(text("UPDATE CAFCONT SET CORP_RET=:cr WHERE APPL_NO=:a"), {"cr": "C" if ind_cor=="2" else "R", "a": applno})

        if db.session.execute(text("SELECT APPL_NO FROM CAFCONT_TOTOUTS WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}).mappings().first():
            db.session.execute(text("UPDATE CAFCONT_TOTOUTS SET OUTSTANDING=:la WHERE APPL_NO=:a"), {"la": float(mstr.get("L_AMOUNT") or 0), "a": applno})
        else:
            db.session.execute(text("INSERT INTO CAFCONT_TOTOUTS VALUES(:a,:la)"), {"a": applno, "la": float(mstr.get("L_AMOUNT") or 0)})

        approval1 = next_appr
        if next_appr == "CRH":
            try:
                crh = db.session.execute(text("EXEC USP_CAM_GETVALIDCRH :p"), {"p": applno}).mappings().first()
                approval1 = (crh or {}).get("Username") or "Admin"
            except Exception:
                approval1 = "Admin"

        wd = 1 if db.session.execute(text("SELECT 1 FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:a AND APPR_STS LIKE 'T'"), {"a": applno}).mappings().first() else 0
        ots2 = float((db.session.execute(text("SELECT SUM(OUTS) AS v FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a AND ASOF=(SELECT MAX(ASOF) FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a2)"), {"a": applno, "a2": applno}).mappings().first() or {}).get("v") or 0)
        fid  = _cam_appr_form_id(applno, ots2, access_level)
        aps  = "F" if send_to_admin else "A"
        aal  = next_appr.split("|")[1] if "|" in next_appr else ""
        cmoid = session.get("emp_id", "")

        if is_multiple:
            sp = db.session.execute(text("""EXEC USP_CAM_SENTBYMULTIPLE :a,:wd,:ap1,:al,:u,:sts,:cmt,:cmoid,:eid,:adm,:csp,:fid,:nr"""),
                {"a": applno, "wd": wd, "ap1": approval1, "al": access_level, "u": username, "sts": aps, "cmt": comment, "cmoid": cmoid, "eid": emp_id, "adm": send_to_admin, "csp": 0, "fid": fid, "nr": not_recommend})
        else:
            sp = db.session.execute(text("""EXEC USP_CAM_SENTBYAPPLNO :a,:wd,:ap1,:al,:u,:sts,:cmt,:cmoid,:eid,:adm,:csp,:fid,:nr,:aal"""),
                {"a": applno_t2, "wd": wd, "ap1": approval1, "al": access_level, "u": username, "sts": aps, "cmt": comment, "cmoid": cmoid, "eid": emp_id, "adm": send_to_admin, "csp": 0, "fid": fid, "nr": not_recommend, "aal": aal})

        sp_row = (sp.mappings().first() if sp else None) or {}
        if sp_row.get("status") == "FAILED":
            db.session.rollback()
            return jsonify({"error": "Failed to submit CAM. Please contact your administrator."}), 500

        db.session.commit()
        return jsonify({"success": True, "redirect": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("CAM approval confirm error")
        return jsonify({"error": "Failed to process approval"}), 500
    
_WATCHLIST_SQL = """
SELECT TOP 1
    a.NAME,
    b.DESC_VALUE,
    ISNULL(a.LastUser, a.CreateUser)   AS createby,
    ISNULL(a.LastUpdate, a.CreateDate) AS createdt,
    CASE WHEN (a.LastUser <> '' OR a.LastUser IS NOT NULL) THEN 'U' ELSE 'C' END AS cekjenis
FROM MCMOWATCHLIST a WITH (NOLOCK)
    INNER JOIN mstcombo b WITH (NOLOCK)
        ON a.Reason_Category = b.value
    AND b.cat_value = 'BLACKLIST_CATEGORY'
WHERE {cond}
    AND a.Flag_Type = 'W'
    AND a.FlagDel = '0'
"""

def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ''

def _like(value: Any) -> str:
    return f"%{_clean(value)}%"

def _format_date(value: Any) -> str:
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d-%m-%Y')
    return str(value)

def _fetch_watchlist(cursor, cond: str, params: list) -> Optional[dict]:
    cursor.execute(_WATCHLIST_SQL.format(cond=cond), params)
    row = cursor.fetchone()
    if not row:
        return None

    is_update = _clean(row.cekjenis) == 'U'
    return {
        'category': _clean(row.DESC_VALUE),
        'by_label': 'Update By' if is_update else 'Created By',
        'date_label': 'Last Update' if is_update else 'Created Date',
        'created_by': _clean(row.createby),
        'created_date': _format_date(row.createdt),
    }

def get_watchlist(cursor, apless: str) -> Optional[dict]:
    cursor.execute(
        """
        SELECT LESSEE_NM, ADDRESS1, ADDRESS2, ID_CARD, LESSEE_TP, NPWP
        FROM CAFLESS WITH (NOLOCK)
        WHERE APLESS = ?
        """,
        [apless],
    )
    less = cursor.fetchone()
    if not less:
        return None

    less_tp = _clean(less.LESSEE_TP)
    lessee_nm = _clean(less.LESSEE_NM)
    address1 = _clean(less.ADDRESS1)
    id_card = _clean(less.ID_CARD)
    npwp = _clean(less.NPWP)

    if less_tp == 'PR':
        if id_card:
            wl = _fetch_watchlist(cursor, "a.ID_card LIKE ?", [_like(id_card)])
            if wl:
                return wl
    else:
        if npwp:
            wl = _fetch_watchlist(cursor, "a.NPWP LIKE ?", [_like(npwp)])
            if wl:
                return wl

    if lessee_nm and address1:
        wl = _fetch_watchlist(
            cursor,
            "a.Name LIKE ? AND a.Address LIKE ?",
            [_like(lessee_nm), _like(address1)],
        )
        if wl:
            return wl

    if less_tp == 'PR' and address1:
        return _fetch_watchlist(cursor, "a.Address LIKE ?", [_like(address1)])

    return None

def _get_approval_watchlist(apless):
    
    less = db.session.execute(text("""
        SELECT LESSEE_NM, ADDRESS1, ID_CARD, LESSEE_TP, NPWP
        FROM CAFLESS WITH (NOLOCK)
        WHERE APLESS = :apless
    """), {"apless": apless}).mappings().first()

    if not less:
        return None

    def clean(v):
        return str(v).strip() if v is not None else ""

    def fetch(cond, params):
        row = db.session.execute(text(f"""
            SELECT TOP 1
                b.DESC_VALUE,
                ISNULL(a.LastUser, a.CreateUser)   AS createby,
                ISNULL(a.LastUpdate, a.CreateDate) AS createdt,
                CASE WHEN (a.LastUser <> '' OR a.LastUser IS NOT NULL) THEN 'U' ELSE 'C' END AS cekjenis
            FROM MCMOWATCHLIST a WITH (NOLOCK)
                INNER JOIN mstcombo b WITH (NOLOCK)
                    ON a.Reason_Category = b.VALUE
                AND b.CAT_VALUE = 'BLACKLIST_CATEGORY'
            WHERE {cond}
              AND a.Flag_Type = 'W'
              AND a.FlagDel = '0'
        """), params).mappings().first()

        if not row:
            return None

        is_update = clean(row["cekjenis"]) == "U"
        createdt = row["createdt"]
        return {
            "category": clean(row["DESC_VALUE"]),
            "by_label": "Update By" if is_update else "Created By",
            "date_label": "Last Update" if is_update else "Created Date",
            "created_by": clean(row["createby"]),
            "created_date": createdt.strftime("%d-%m-%Y") if createdt else "",
        }

    less_tp = clean(less["LESSEE_TP"])
    lessee_nm = clean(less["LESSEE_NM"])
    address1 = clean(less["ADDRESS1"])
    id_card = clean(less["ID_CARD"])
    npwp = clean(less["NPWP"])

    if less_tp == "PR":
        if id_card:
            wl = fetch("a.ID_card LIKE :v", {"v": f"%{id_card}%"})
            if wl:
                return wl
    elif npwp:
        wl = fetch("a.NPWP LIKE :v", {"v": f"%{npwp}%"})
        if wl:
            return wl

    if lessee_nm and address1:
        wl = fetch("a.Name LIKE :nm AND a.Address LIKE :addr",
                   {"nm": f"%{lessee_nm}%", "addr": f"%{address1}%"})
        if wl:
            return wl

    if less_tp == "PR" and address1:
        return fetch("a.Address LIKE :addr", {"addr": f"%{address1}%"})

    return None
    
OMITTED_REPORT_SECTIONS = [
    "Business Profile (Organization Structure)",
    "Guarantor Detail Review",
    "Beneficial Owner Detail Review",
]

SIGNOFF_ROLES = [
    {"code": "CA", "label": "CA"},
    {"code": "FA", "label": "FA"},
    {"code": "OA", "label": "OA"},
    {"code": "FIN_HO", "label": "FIN - HO"},
]

def _report_cam_revision_note(applno):
    row = db.session.execute(
        text("SELECT Revisi, Revisi_note FROM MCMOREVISI WITH (NOLOCK) WHERE NewAppl_No=:a"),
        {"a": applno}
    ).mappings().first() or {}
    revisi = row.get("Revisi")
    return (f"R{revisi}" if revisi else ""), (row.get("Revisi_note") or "")

def _report_cam_multiple_flag(applno):
    corp_ret = db.session.execute(
        text("SELECT CORP_RET FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a"),
        {"a": applno}
    ).scalar()
    if (corp_ret or "").strip() != "M":
        return ""
    found = db.session.execute(
        text("SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO=:a"),
        {"a": applno}
    ).first()
    return "M" if found else ""

def _report_cam_cross_numbers(applno):
    cn = [r[0] for r in db.session.execute(
        text("SELECT CROSSNO FROM TACROSSNO WITH (NOLOCK) "
             "WHERE APPL_NO=:a AND CROSS_TYPE='CN' AND CROSSNO<>''"),
        {"a": applno}
    ).all()]
    comma_cn = " / ".join(cn)
    cross_no_atasan = comma_cn if len(cn) == 1 else ""

    cd = [r[0] for r in db.session.execute(
        text("SELECT CROSSNO FROM TACROSSNO WITH (NOLOCK) "
             "WHERE APPL_NO=:a AND (CROSS_TYPE='CD' OR CROSS_TYPE IS NULL)"),
        {"a": applno}
    ).all()]
    comma_cd = " / ".join(cd)

    cross_no_atasd = ""
    if len(cd) == 1 and comma_cd != comma_cn:
        cross_no_atasd = comma_cd
    elif len(cd) == 2:
        g = [r[0] for r in db.session.execute(
            text("SELECT CROSSNO FROM TACROSSNO WITH (NOLOCK) "
                 "WHERE APPL_NO=:a AND CROSS_TYPE='CD' AND CROSSNO NOT IN "
                 "(SELECT CROSSNO FROM TACROSSNO WITH (NOLOCK) WHERE APPL_NO=:a AND CROSS_TYPE='CN')"),
            {"a": applno}
        ).all()]
        cross_no_atasd = g[0] if len(g) == 1 else "Attachment"
    elif len(cd) > 1:
        cross_no_atasd = "Attachment"

    return cn, cross_no_atasan, cross_no_atasd

def _report_cam_contract_no(applno):
    transacted = db.session.execute(
        text("SELECT 1 FROM CAFCONT WITH (NOLOCK) WHERE DateTrans IS NOT NULL AND APPL_NO=:a"),
        {"a": applno}
    ).first()
    if not transacted:
        return "", ""

    def _rev(column, value):
        return db.session.execute(
            text(f"SELECT OldAppl_No, NewAppl_No FROM MCMORevisi WITH (NOLOCK) WHERE {column}=:a"),
            {"a": value}
        ).mappings().first()

    candidates = []
    first = _rev("NewAppl_No", applno)
    if first:
        candidates.append(first["NewAppl_No"])

    chain = applno
    for _ in range(4):
        nxt = _rev("OldAppl_No", chain)
        if not nxt or nxt["NewAppl_No"] in candidates:
            break
        candidates.append(nxt["NewAppl_No"])
        chain = nxt["NewAppl_No"]

    if first:
        candidates.append(first["OldAppl_No"])
    candidates.append(applno)

    for appl in candidates:
        if not appl:
            continue
        row = db.session.execute(
            text("SELECT lease_no, LESSEE_NO FROM CLFCONT WITH (NOLOCK) WHERE FLGDEL='0' AND appl_no=:a"),
            {"a": appl}
        ).mappings().first()
        if row and (row["lease_no"] or row["LESSEE_NO"]):
            return (row["lease_no"] or ""), (row["LESSEE_NO"] or "")
    return "", ""

def _report_cam_related_survey(applno, apless):
    rows = db.session.execute(
        text("SELECT a.APPL_NO FROM CAFCONT a WITH (NOLOCK) "
             "INNER JOIN TAMASTER c WITH (NOLOCK) ON c.APPL_NO=a.APPL_NO "
             "LEFT JOIN MCMOCAMCOMPLETELIST b WITH (NOLOCK) ON a.APPL_NO=b.APPL_NO "
             "WHERE a.APLESS=:ap AND b.AdmSts=0 AND a.NOTES IS NOT NULL AND a.NOTES<>'' "
             "AND a.APPL_NO<>:a ORDER BY a.APPL_NO"),
        {"ap": apless, "a": applno}
    ).all()
    return ", ".join(r[0] for r in rows)

def _report_cam_pending_notes(applno):
    return db.session.execute(
        text("SELECT PENDING_NOTES FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a"),
        {"a": applno}
    ).scalar() or ""

def _report_cam_bo_availability(applno):
    bo_id = db.session.execute(
        text("SELECT BO_ID FROM BENEFICIARY_LINK WITH (NOLOCK) WHERE APPL_NO=:a"),
        {"a": applno}
    ).scalar()
    return "Available" if bo_id else "Not Available"

def _report_cam_corporate_finance(apless):
    return bool(db.session.execute(
        text("SELECT TOP 1 a.apless FROM cafless a WITH (NOLOCK) "
             "INNER JOIN clfless b WITH (NOLOCK) ON a.apless=b.apless "
             "LEFT JOIN cafcont c WITH (NOLOCK) ON c.apless=a.apless "
             "LEFT JOIN clfcont d WITH (NOLOCK) ON d.appl_no=c.appl_no "
             "WHERE d.upd_stat='Y' AND d.execution IS NOT NULL AND d.branch_cd='91' AND a.APLESS=:ap"),
        {"ap": apless}
    ).first())

def _report_cam_industry(mlci_code, descrip):
    if not descrip:
        return mlci_code or ""
    words = str(descrip).split(" ")
    s9 = " ".join(words[:9])
    s8 = " ".join(words[:8])
    potongan = s8 if s9.split(" ")[-1] == "dan" else s9
    if potongan.endswith(","):
        potongan = potongan[:-1]
    return f"{mlci_code or ''} - {potongan}"

def _report_cam_insurance_type(applno, ins_pol):
    if not ins_pol:
        return ""
    total_year = db.session.execute(
        text("SELECT TOP 1 year_no FROM CAFINSUD WITH (NOLOCK) WHERE Ins_Pol=:p ORDER BY year_no DESC"),
        {"p": ins_pol}
    ).scalar()
    if total_year is None:
        return ""
    names = [r[0] for r in db.session.execute(
        text("SELECT DISTINCT cc.name FROM CAFINSUD_Clause xx WITH (NOLOCK) "
             "INNER JOIN mstCLAUSE cc WITH (NOLOCK) ON cc.code=xx.Clause "
             "WHERE xx.Ins_Pol=:p AND xx.Appl_No=:a AND xx.year_no=:y ORDER BY cc.name"),
        {"p": ins_pol, "a": applno, "y": total_year}
    ).all()]
    tlo_ar = db.session.execute(
        text("SELECT DISTINCT TOP 1 rr.[name] FROM CAFINSUD xx WITH (NOLOCK) "
             "INNER JOIN mstTLOAR rr WITH (NOLOCK) ON rr.code=xx.TLO_AR "
             "WHERE xx.Ins_Pol=:p AND xx.year_no=:y"),
        {"p": ins_pol, "y": total_year}
    ).scalar() or ""
    tpl_raw = db.session.execute(
        text("SELECT TOP 1 TPL_AMT FROM CAFINSUD WITH (NOLOCK) WHERE Ins_Pol=:p AND year_no=:y"),
        {"p": ins_pol, "y": total_year}
    ).scalar()
    tpl_amt = _f(tpl_raw) / 1000000 if tpl_raw else 0
    tpl_text = f"{tpl_amt:g}"
    if names:
        return f"{tlo_ar} + " + " + ".join(names) + f" + {tpl_text}"
    return f"{tlo_ar} + {tpl_text}"

def _report_cam_dealer_status(supp_code, create_date_raw):
    if not supp_code:
        return "NonSKB / NonPPN"
    row = db.session.execute(
        text("SELECT TFFrom, TFTo, DateStart, ppn FROM BeneficiaryTax WITH (NOLOCK) "
             "WHERE BeneficiaryID=:s AND CATEGORY='DEALER'"),
        {"s": supp_code}
    ).mappings().first() or {}

    skb = "NonSKB"
    tf_from, tf_to = row.get("TFFrom"), row.get("TFTo")
    if tf_from and tf_to and create_date_raw and tf_from <= create_date_raw <= tf_to:
        skb = "SKB"

    ppnn = "NonPPN"
    date_start = row.get("DateStart")
    if (date_start and date_start.strftime("%Y") != "1900" and row.get("ppn") == "1"
            and create_date_raw and date_start <= create_date_raw):
        ppnn = "PPN"

    return f"{skb} / {ppnn}"

def _report_cam_disb_accounts(applno):
    rows = db.session.execute(
        text("SELECT b.[DESC] AS bank_name, a.ACC_NO, a.ACC_NM FROM CAFDISBACC a WITH (NOLOCK) "
             "INNER JOIN UMFBANK b WITH (NOLOCK) ON a.BANK=b.BANK_CODE WHERE a.APPL_NO=:a"),
        {"a": applno}
    ).mappings().all()
    result = []
    for r in rows:
        acc_nm = r["ACC_NM"] or ""
        if acc_nm.strip().lower() == "ptmitsuileasingcapitalindonesia":
            continue
        result.append(f"{r['bank_name'] or ''} {r['ACC_NO'] or ''} - {acc_nm}")
    return result

def _report_cam_sales_commission(applno, create_date_raw):
    today = datetime.now()
    rows = db.session.execute(
        text("SELECT a.SALES_NO, a.GrossAmount, a.PPNAmount, a.TaxAmount, b.NAME, b.Sales_Type, "
             "c.ppn, c.NPWP_Type, c.NPWP_No, c.DateStart, c.TFFrom, c.TFTo "
             "FROM CAFKOMIS a WITH (NOLOCK) "
             "LEFT JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO=b.SALES_NO "
             "LEFT JOIN BeneficiaryTax c WITH (NOLOCK) ON a.SALES_NO=c.BeneficiaryID AND c.Category='SALES' "
             "WHERE a.APPL_NO=:a AND a.SD_TYPE='S' AND a.Incentive='1'"),
        {"a": applno}
    ).mappings().all()

    result = []
    for r in rows:
        sales_type = r.get("Sales_Type")
        npwp_type = r.get("NPWP_Type")
        has_npwp = r.get("NPWP_No") not in (None, "")
        ppn = r.get("ppn")
        no_tax = not r.get("TaxAmount")
        date_start = r.get("DateStart")
        in_tax_window = bool(r.get("TFFrom") and r.get("TFTo") and r["TFFrom"] <= today <= r["TFTo"])
        before_create = bool(date_start and create_date_raw and date_start <= create_date_raw)

        code = ""
        if sales_type == "PT":
            if npwp_type == "PT" and has_npwp:
                if ppn == "1" and before_create:
                    code = "B<sup>TVB</sup>" if no_tax else "B<sup>TV</sup>"
                else:
                    code = "B<sup>TB</sup>" if (no_tax and in_tax_window) else "B<sup>T</sup>"
            if npwp_type == "PR" and has_npwp:
                if ppn == "1" and before_create:
                    code = "B<sup>RVB</sup>" if no_tax else "B<sup>RV</sup>"
                else:
                    code = "B<sup>RB</sup>" if (no_tax and in_tax_window) else "B<sup>R</sup>"
            if npwp_type in ("PR", "00") and not has_npwp:
                code = "B"
        elif sales_type == "PR":
            code = "S" if (npwp_type in ("", "00", "PR", None) and not has_npwp) else "S<sup>N</sup>"

        result.append({
            "label": f"{code} {r['SALES_NO']} - {r.get('NAME') or ''}".strip(),
            "amount": _f(r["GrossAmount"]) + _f(r["PPNAmount"]),
        })

    total = db.session.execute(
        text("SELECT ISNULL(SUM(a.Amount),0) FROM CAFKOMISAcc a WITH (NOLOCK) "
             "INNER JOIN CAFKOMIS x WITH (NOLOCK) ON x.APPL_NO=a.APPL_No AND a.Sales_No=x.SALES_NO "
             "INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO=b.SALES_NO "
             "WHERE a.APPL_NO=:a AND a.SD_TYPE='S' AND x.Incentive='1'"),
        {"a": applno}
    ).scalar()
    return result, _f(total)

def _report_cam_installment_steps(applno):
    rows = db.session.execute(
        text("SELECT NO_STEP, PMT_STEP FROM CAFSTEP WITH (NOLOCK) WHERE APPL_NO=:a ORDER BY STEP"),
        {"a": applno}
    ).mappings().all()
    return [{"months": r["NO_STEP"], "amount": _f(r["PMT_STEP"])} for r in rows]

def _report_cam_equipment_detail(applno, fin_type):
    row = db.session.execute(
        text("SELECT a.CAFEQUIP_ID, a.USERUSAGE, a.PARK_LOC, a.PARK_ZIPCODE, pp.KABUPATEN AS CITY_PARK, "
             "g.name AS purpose, a.KAROSERI_SUPP, a.ACCESSORIES_SUPP, a.OTHER_SUPP, "
             "l.[NAME] AS karoseri_name, l.[ADDRESS] AS karoseri_address, "
             "m.[NAME] AS accessories_name, m.[ADDRESS] AS accessories_address, "
             "n.[NAME] AS other_name, n.[ADDRESS] AS other_address, o.Name AS BPKB_Area, "
             "a.ADD_COLLATERAL, a.FUND_PURPOSE, dd.desc_value AS fin_purpose_d, mm.desc_value AS fin_purpose_m, "
             "nn.DESC_VALUE AS ojk_fin_goods, oo.DESC_VALUE AS ojk_coll_goods "
             "FROM CAFEQUIP a WITH (NOLOCK) "
             "LEFT JOIN mstPurpose g WITH (NOLOCK) ON a.PURPOSE=g.Purpose "
             "LEFT JOIN CLFSUPP l WITH (NOLOCK) ON a.KAROSERI_SUPP=l.SUPP "
             "LEFT JOIN CLFSUPP m WITH (NOLOCK) ON a.ACCESSORIES_SUPP=m.SUPP "
             "LEFT JOIN CLFSUPP n WITH (NOLOCK) ON a.OTHER_SUPP=n.SUPP "
             "LEFT JOIN MSTINSURANCEAREA o WITH (NOLOCK) ON a.insurance_area=o.Code "
             "LEFT JOIN Cafequip_Detail xx WITH (NOLOCK) ON a.APPL_NO=xx.APPL_NO "
             "LEFT JOIN mstcombo dd WITH (NOLOCK) ON xx.FIN_PURPOSE=dd.value AND dd.cat_value='Fund_Facility' "
             "LEFT JOIN mstcombo mm WITH (NOLOCK) ON xx.FIN_PURPOSE=mm.value AND mm.cat_value='Business_Capital_Facility' "
             "LEFT JOIN mstcombo nn WITH (NOLOCK) ON xx.OJK_Fin_Goods_Detail=nn.VALUE "
             "AND nn.CAT_VALUE IN ('OJK_FIN_GOOD_P','OJK_FIN_GOOD_K','OJK_FIN_GOOD_J') "
             "LEFT JOIN mstcombo oo WITH (NOLOCK) ON xx.OJK_Coll_Goods_Detail=oo.VALUE "
             "AND oo.CAT_VALUE IN ('OJK_COL_GOOD_P','OJK_COL_GOOD_K') "
             "LEFT JOIN UMFAREA pp WITH (NOLOCK) ON a.CITY_PARK=pp.AREA_CD "
             "WHERE a.APPL_NO=:a"),
        {"a": applno}
    ).mappings().first()
    if not row or not row.get("CAFEQUIP_ID"):
        return None

    fin_purpose = ""
    if fin_type == "D":
        fin_purpose = row.get("fin_purpose_d") or ""
    elif fin_type in ("M", "W"):
        fin_purpose = row.get("fin_purpose_m") or ""

    karoseri_supp = (row.get("KAROSERI_SUPP") or "").strip()
    accessories_supp = (row.get("ACCESSORIES_SUPP") or "").strip()
    other_supp = (row.get("OTHER_SUPP") or "").strip()

    return {
        "user_usage": row.get("USERUSAGE") or "",
        "vehicle_purpose": row.get("purpose") or "",
        "show_financing_purpose": fin_type in ("D", "M", "W"),
        "financing_purpose": fin_purpose,
        "customer_purpose": row.get("FUND_PURPOSE") or "",
        "parking_address": f"{row.get('PARK_LOC') or ''}, {row.get('CITY_PARK') or ''}".strip(", "),
        "zip_code": row.get("PARK_ZIPCODE") or "",
        "insurance_area": row.get("BPKB_Area") or "",
        "additional_collateral": "Yes" if row.get("ADD_COLLATERAL") == "1" else "No",
        "ojk_financing_goods": row.get("ojk_fin_goods") or "",
        "ojk_collateral_goods": row.get("ojk_coll_goods") or "",
        "karoseri_name": (row.get("karoseri_name") or "-") if karoseri_supp else None,
        "karoseri_address": ((row.get("karoseri_address") or "").strip() or "-") if karoseri_supp else None,
        "accessories_name": (row.get("accessories_name") or "-") if accessories_supp else None,
        "accessories_address": ((row.get("accessories_address") or "").strip() or "-") if accessories_supp else None,
        "other_name": (row.get("other_name") or "-") if other_supp else None,
        "other_address": ((row.get("other_address") or "").strip() or "-") if other_supp else None,
    }

def _report_cam_org_period(applno, apless):
    row = db.session.execute(
        text("SELECT YEAR(CREATE_DATE) AS YEARS, MONTH(CREATE_DATE) AS MONTHS "
             "FROM CAFCONT WITH (NOLOCK) WHERE APLESS=:ap AND APPL_NO=:a"),
        {"ap": apless, "a": applno}
    ).mappings().first()
    if row and row.get("YEARS"):
        dates = f"{int(row['YEARS'])}{int(row['MONTHS']):02d}"
    else:
        now = datetime.now()
        dates = f"{now.year}{now.month:02d}"
    return db.session.execute(
        text("SELECT TOP 1 PERIOD FROM CAFORGSTRUCT WITH (NOLOCK) "
             "WHERE APLESS=:ap AND PERIOD <= :d GROUP BY PERIOD ORDER BY PERIOD DESC"),
        {"ap": apless, "d": dates}
    ).scalar()

def _org_position_label(os_code, pos_deedno):
    raw = "" if pos_deedno is None else str(pos_deedno)
    if raw.strip().isdigit():
        desc = db.session.execute(
            text("SELECT [DESC] FROM MSTOS_POSITION WITH (NOLOCK) "
                 "WHERE OS_CODE=:o AND ID_OS_POSITION=:p"),
            {"o": os_code, "p": raw}
        ).scalar()
        return desc or ""
    return raw

def _org_signer_label(apless, os_code, name, pos_deedno):
    if pos_deedno is None:
        rows = db.session.execute(
            text("SELECT POS_DEEDNO FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
                 "WHERE APLESS=:ap AND OS_CODE=:o AND MANAGEMENT_NM=:n AND POS_DEEDNO IS NULL"),
            {"ap": apless, "o": os_code, "n": name}
        ).all()
    else:
        rows = db.session.execute(
            text("SELECT POS_DEEDNO FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
                 "WHERE APLESS=:ap AND OS_CODE=:o AND MANAGEMENT_NM=:n"),
            {"ap": apless, "o": os_code, "n": name}
        ).all()

    label = ""
    for r in rows:
        raw = "" if r[0] is None else str(r[0])
        if len(raw) == 1:
            desc = db.session.execute(
                text("SELECT [DESC] FROM MSTOS_POSITION WITH (NOLOCK) "
                     "WHERE OS_CODE=:o AND ID_OS_POSITION=:p ORDER BY ID_OS_POSITION ASC"),
                {"o": os_code, "p": raw}
            ).scalar()
            label = desc if desc else ("" if pos_deedno is None else str(pos_deedno))
        elif len(raw) > 1:
            label = raw
        else:
            label = "Share Holder"
    return label

def _org_composition(apless, period, os_code, lookup):
    rows = db.session.execute(
        text("SELECT MANAGEMENT_NM, POS_DEEDNO, SIGNER, OWNER FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
             "WHERE APLESS=:ap AND PERIOD=:p AND OS_CODE=:o"),
        {"ap": apless, "p": period, "o": os_code}
    ).mappings().all()
    out = []
    for i, r in enumerate(rows, start=1):
        if lookup == "position":
            position = _org_position_label(os_code, r["POS_DEEDNO"])
        elif lookup == "join":
            desc = db.session.execute(
                text("SELECT MP.[DESC] FROM MSTOS_POSITION MP WITH (NOLOCK) WHERE MP.ID_OS_POSITION=:p"),
                {"p": r["POS_DEEDNO"]}
            ).scalar()
            position = desc or (r["POS_DEEDNO"] or "")
        else:
            position = r["POS_DEEDNO"] or ""
        out.append({
            "no": i,
            "name": r["MANAGEMENT_NM"] or "",
            "position": position,
            "owner": r["OWNER"] == "1",
        })
    return out

def _org_deed_simple(apless, period, os_code, cust_type):
    out = []
    for i, r in enumerate(db.session.execute(
        text("SELECT POS_DEEDNO, NOTARY_NM, CERTIFICATE, "
             "FORMAT(CAST(DATE_OF_DEED AS date), 'dd-MM-yyyy') AS DATE_OF_DEED "
             "FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
             "WHERE APLESS=:ap AND PERIOD=:p AND OS_CODE=:o"),
        {"ap": apless, "p": period, "o": os_code}
    ).mappings().all(), start=1):
        cert_raw = "" if r["CERTIFICATE"] is None else str(r["CERTIFICATE"])
        if cert_raw.strip().isdigit():
            certificate = db.session.execute(
                text("SELECT [DESC] FROM MSTOS_CERTIFICATE WITH (NOLOCK) "
                     "WHERE CUST_TYPE=:c AND ID_OS_CERTIFICATE=:i"),
                {"c": cust_type, "i": cert_raw}
            ).scalar() or ""
        else:
            certificate = cert_raw
        out.append({
            "no": i,
            "deed_no": r["POS_DEEDNO"] or "",
            "date_of_deed": r["DATE_OF_DEED"] or "",
            "notary_name": r["NOTARY_NM"] or "",
            "certificate": certificate,
        })
    return out

def _org_head(apless, period, cust_type, other_signer_id):
    row = db.session.execute(
        text("SELECT a.OTHER_SIGNER, a.PIC, b.ID_OS_SIGNER, b.[DESC] AS contract_signer "
             "FROM CAFORGSTRUCT a WITH (NOLOCK) "
             "LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER "
             "WHERE a.APLESS=:ap AND a.PERIOD=:p AND b.CUST_TYPE=:c"),
        {"ap": apless, "p": period, "c": cust_type}
    ).mappings().first() or {}
    contract_signer = row.get("contract_signer") or ""
    other_signer = row.get("OTHER_SIGNER") or ""
    shown = other_signer if str(row.get("ID_OS_SIGNER")) == other_signer_id else contract_signer
    return shown, (row.get("PIC") or shown)

def _org_signers(apless, period, os_codes, combined=False):
    signers, seen = [], []
    groups = [os_codes] if combined else [[c] for c in os_codes]
    for group in groups:
        clause = ",".join(f"'{c}'" for c in group)
        for r in db.session.execute(
            text("SELECT MANAGEMENT_NM, POS_DEEDNO, OS_CODE FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
                 f"WHERE APLESS=:ap AND OS_CODE IN ({clause}) AND SIGNER='1' AND PERIOD=:p "
                 "ORDER BY CONVERT(varchar, POS_DEEDNO) ASC, MANAGEMENT_NM ASC"),
            {"ap": apless, "p": period}
        ).mappings().all():
            name = r["MANAGEMENT_NM"]
            if name in seen:
                continue
            seen.append(name)
            signers.append({
                "name": name or "",
                "position": _org_position_label(r["OS_CODE"], r["POS_DEEDNO"]),
            })
    return signers

def _org_management(apless, period, code_prefix):
    out = []
    for i, r in enumerate(db.session.execute(
        text("SELECT DISTINCT ID_DETAIL, MANAGEMENT_NM, ID_CARD, [ADDRESS], "
             "CASE WHEN CITY='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY END AS CITY, IMAGES, "
             "r.Desc_Name AS Kecamatan, s.Desc_Name AS Kelurahan "
             "FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK) "
             "LEFT JOIN Mst_Kecamatan r WITH (NOLOCK) ON a.KECAMATAN=r.Kecamatan_CD "
             "LEFT JOIN Mst_Kelurahan s WITH (NOLOCK) ON a.KELURAHAN=s.Kelurahan_CD "
             "WHERE APLESS=:ap AND PERIOD=:p AND OS_CODE LIKE :pre "
             "AND MANAGEMENT_NM IS NOT NULL ORDER BY a.ID_DETAIL ASC"),
        {"ap": apless, "p": period, "pre": code_prefix + "%"}
    ).mappings().all(), start=1):
        out.append({
            "no": i,
            "name": r["MANAGEMENT_NM"] or "",
            "id_card": r["ID_CARD"] or "",
            "address": ", ".join(
                x for x in [r["ADDRESS"], r["Kelurahan"], r["Kecamatan"], r["CITY"]] if x
            ),
        })
    return out

def _report_cam_org_structure(applno, apless):
    lessee = db.session.execute(
        text("SELECT LESSEE_TP, Lessee_Cat FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:ap"),
        {"ap": apless}
    ).mappings().first()
    if not lessee or lessee.get("LESSEE_TP") != "PT":
        return None
    lessee_cat = (lessee.get("Lessee_Cat") or "").strip()
    if lessee_cat not in ("PT", "CO", "CV", "FD"):
        return None

    period = _report_cam_org_period(applno, apless)
    if not period:
        return None

    if lessee_cat == "CO":
        contract_signer_shown, pic = _org_head(apless, period, "CO", "14")
        return {
            "entity_type": "CO",
            "period": period,
            "board_of_management": _org_composition(apless, period, "CO01", "join"),
            "board_of_supervisor": _org_composition(apless, period, "CO02", "raw"),
            "deed": _org_deed_simple(apless, period, "CO03", "CO"),
            "deed_certificate_label": "Certificate of Ministry of Cooperative",
            "contract_signer": contract_signer_shown,
            "pic": pic,
            "signers": _org_signers(apless, period, ["CO01", "CO02"]),
            "management": _org_management(apless, period, "CO"),
        }

    if lessee_cat == "CV":
        contract_signer_shown, pic = _org_head(apless, period, "CV", "10")
        return {
            "entity_type": "CV",
            "period": period,
            "active_partner": _org_composition(apless, period, "CV01", "position"),
            "limited_partner": _org_composition(apless, period, "CV02", "position"),
            "deed": _org_deed_simple(apless, period, "CV03", "CV"),
            "deed_certificate_label": "Status Deed",
            "contract_signer": contract_signer_shown,
            "pic": pic,
            "signers": _org_signers(apless, period, ["CV01", "CV02"], combined=True),
            "management": _org_management(apless, period, "CV"),
        }

    if lessee_cat == "FD":
        contract_signer_shown, pic = _org_head(apless, period, "FD", "16")
        return {
            "entity_type": "FD",
            "period": period,
            "fostering_foundation": _org_composition(apless, period, "FD01", "raw"),
            "board_of_management": _org_composition(apless, period, "FD02", "join"),
            "board_of_supervisor": _org_composition(apless, period, "FD03", "raw"),
            "deed": _org_deed_simple(apless, period, "FD04", "FD"),
            "deed_certificate_label": "Certificate of Ministry of Cooperative",
            "contract_signer": contract_signer_shown,
            "pic": pic,
            "signers": _org_signers(apless, period, ["FD01", "FD02", "FD03"]),
            "management": _org_management(apless, period, "FD"),
        }

    head = db.session.execute(
        text("SELECT a.AUTHORIZED_CAPITAL, a.PAID_IN_CAPITAL, a.OTHER_SIGNER, a.PIC, "
             "b.ID_OS_SIGNER, b.[DESC] AS contract_signer "
             "FROM CAFORGSTRUCT a WITH (NOLOCK) "
             "LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER "
             "WHERE a.APLESS=:ap AND a.PERIOD=:p AND b.CUST_TYPE='PT'"),
        {"ap": apless, "p": period}
    ).mappings().first() or {}

    contract_signer = head.get("contract_signer") or ""
    other_signer = head.get("OTHER_SIGNER") or ""
    contract_signer_shown = other_signer if str(head.get("ID_OS_SIGNER")) == "5" else contract_signer
    pic = head.get("PIC") or contract_signer_shown

    shareholders = [
        {
            "no": i,
            "name": r["MANAGEMENT_NM"] or "",
            "status": r["DESC_VALUE"] or "",
            "total_shares": r["TOTOFSHARES"],
            "nominal_shares": _f(r["NOMOFSHARES"]),
        }
        for i, r in enumerate(db.session.execute(
            text("SELECT a.TOTOFSHARES, a.NOMOFSHARES, a.MANAGEMENT_NM, a.POS_DEEDNO, a.SIGNER, "
                 "b.DESC_VALUE FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK) "
                 "LEFT JOIN MSTCOMBO b WITH (NOLOCK) ON b.VALUE=a.SHAREHOLDER_STATUS "
                 "AND b.CAT_VALUE='SHAREHOLDER_STATUS' "
                 "WHERE a.APLESS=:ap AND a.PERIOD=:p AND a.OS_CODE='PT01'"),
            {"ap": apless, "p": period}
        ).mappings().all(), start=1)
    ]

    def composition(os_code):
        return [
            {
                "no": i,
                "name": r["MANAGEMENT_NM"] or "",
                "position": _org_position_label(os_code, r["POS_DEEDNO"]),
                "owner": r["OWNER"] == "1",
            }
            for i, r in enumerate(db.session.execute(
                text("SELECT a.MANAGEMENT_NM, a.POS_DEEDNO, a.SIGNER, a.OWNER "
                     "FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK) "
                     "WHERE a.APLESS=:ap AND a.PERIOD=:p AND a.OS_CODE=:o"),
                {"ap": apless, "p": period, "o": os_code}
            ).mappings().all(), start=1)
        ]

    deed = []
    for i, r in enumerate(db.session.execute(
        text("SELECT MANAGEMENT_NM, POS_DEEDNO, [DATE_OF_DEED], NOTARY_NM, CERTIFICATE "
             "FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
             "WHERE APLESS=:ap AND PERIOD=:p AND OS_CODE='PT04'"),
        {"ap": apless, "p": period}
    ).mappings().all(), start=1):
        cert_raw = "" if r["CERTIFICATE"] is None else str(r["CERTIFICATE"])
        if cert_raw.strip().isdigit():
            certificate = db.session.execute(
                text("SELECT [DESC] FROM MSTOS_CERTIFICATE WITH (NOLOCK) "
                     "WHERE CUST_TYPE='PT' AND ID_OS_CERTIFICATE=:c"),
                {"c": cert_raw}
            ).scalar() or ""
        else:
            certificate = cert_raw
        deed.append({
            "no": i,
            "state_gazette_no": r["MANAGEMENT_NM"] or "",
            "deed_no": r["POS_DEEDNO"] or "",
            "date_of_deed": _fmt_date(r["DATE_OF_DEED"]),
            "notary_name": r["NOTARY_NM"] or "",
            "certificate": certificate,
        })

    signers, seen = [], []
    for os_code in ("PT01", "PT02", "PT03"):
        for r in db.session.execute(
            text("SELECT MANAGEMENT_NM, POS_DEEDNO FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
                 "WHERE APLESS=:ap AND SIGNER='1' AND PERIOD=:p AND OS_CODE=:o"),
            {"ap": apless, "p": period, "o": os_code}
        ).mappings().all():
            name = r["MANAGEMENT_NM"]
            if name in seen:
                continue
            seen.append(name)
            signers.append({
                "name": name or "",
                "position": _org_signer_label(apless, os_code, name, r["POS_DEEDNO"]),
            })

    management = []
    for i, r in enumerate(db.session.execute(
        text("SELECT MIN(ID_DETAIL) AS ID_DETAIL, MANAGEMENT_NM, name, gender, "
             "r.Desc_Name AS kecamatan, s.Desc_Name AS kelurahan, PASSPORTNO, CITIZEN, "
             "NATIONALITY, ID_CARD, [ADDRESS], "
             "CASE WHEN CITY='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY END AS CITY, IMAGES "
             "FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK) "
             "LEFT JOIN Mst_Kecamatan r WITH (NOLOCK) ON a.KECAMATAN=r.Kecamatan_CD "
             "LEFT JOIN Mst_Kelurahan s WITH (NOLOCK) ON a.KELURAHAN=s.Kelurahan_CD "
             "WHERE APLESS=:ap AND OS_CODE IN ('PT01','PT02','PT03') "
             "AND PERIOD=:p AND PERIOD<>'' "
             "GROUP BY MANAGEMENT_NM, name, gender, r.Desc_Name, s.Desc_Name, PASSPORTNO, "
             "CITIZEN, NATIONALITY, ID_CARD, [ADDRESS], CITY, IMAGES "
             "ORDER BY MIN(a.ID_DETAIL) ASC"),
        {"ap": apless, "p": period}
    ).mappings().all(), start=1):
        detail = db.session.execute(
            text("SELECT SHAREHOLDER_STATUS, NPWP FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) "
                 "WHERE ID_DETAIL=:i"),
            {"i": r["ID_DETAIL"]}
        ).mappings().first() or {}
        id_card = r["ID_CARD"] or ""
        if detail.get("SHAREHOLDER_STATUS") == "1":
            id_card = detail.get("NPWP") or ""
        management.append({
            "no": i,
            "name": r["MANAGEMENT_NM"] or "",
            "id_card": id_card,
            "address": ", ".join(
                p for p in [r["ADDRESS"], r["kelurahan"], r["kecamatan"], r["CITY"]] if p
            ),
        })

    return {
        "entity_type": "PT",
        "period": period,
        "authorized_capital": _f(head.get("AUTHORIZED_CAPITAL")),
        "paid_in_capital": _f(head.get("PAID_IN_CAPITAL")),
        "shareholders": shareholders,
        "bod": composition("PT02"),
        "boc": composition("PT03"),
        "deed": deed,
        "contract_signer": contract_signer_shown,
        "pic": pic,
        "signers": signers,
        "management": management,
    }

def _report_cam_core(applno, apless):
    row = (db.session.execute(text("""
        SELECT
            a.APLESS, a.Cont_type, ISNULL(a.L_AMOUNT,0) AS L_AMOUNT, ISNULL(a.SECURITY,0) AS SECURITY,
            ISNULL(a.Otherloan,0) AS Otherloan, a.FLATRATE, a.AdmFee, a.PROVISION, a.RENTAL,
            a.TENOR, a.ADV_ARR, a.DECLRATE, a.Notary_no, a.OTHERFEE, a.L_TYPE, a.TENOR1000,
            a.FLATRATE1000, a.PAY_CYCLE, ISNULL(a.Refund_Supp,0) AS Refund_Supp,
            ISNULL(a.Subsidy_Supp,0) AS Subsidy_Supp, ISNULL(a.SUBSIDY,0) AS SUBSIDY, a.incentive,
            a.CREATE_DATE, a.G_PERIOD, a.G_INT_RATE, ISNULL(a.G_INT_AMT,0) AS G_INT_AMT,
            a.Notary, a.Fiduciary, a.Gross, a.Cons_Leas, a.FIX_FLOAT, a.DISC_CUST, a.FLAGCOM,
            ISNULL(a.BusinessTrip_Fee,0) AS BusinessTrip_Fee,
            a.NOTES, a.CAM_NOTES, ad.DESC_VALUE AS ContSts,
            n.[DESC] AS PURPOFFINC, b.LESSEE_NM, b.LESSEE_TP, b.ADDRESS1, b.CITY1, b.ADDRESS2, b.CITY2,
            b.PHONE1, b.PHONE2, b.Mobile_phone1 AS PHONE3, b.ADDRESS3 AS MAIL_ADDR, b.CITY3 AS MAIL_CITY,
            b.NPWP, b.Zipcode1, b.Zipcode2, b.Zipcode3, b.TGLBIRTH,
            DATEDIFF(yy, b.TGLBIRTH, a.CREATE_DATE)
                - CASE WHEN (MONTH(b.TGLBIRTH) > MONTH(a.CREATE_DATE)) THEN 1 ELSE 0 END AS umur,
            ISNULL(c.CREDITAMT,0) AS CREDITAMT, c.INS_POL, d.name AS amor_type, e.GROSS_PREM, e.NET_COM,
            ISNULL(e.ADMFEE,0) AS ADMFEE_DISB, ISNULL(e.FIRST_INST,0) AS FIRST_INST_DISB,
            ISNULL(e.DP,0) AS DP_DISB, ISNULL(e.Prov,0) AS PROVISION_DISB, ISNULL(e.DISB_INSC,0) AS DISB_INSC,
            ISNULL(e.SERVICE_AGENCY_FEE,0) AS SERVICE_AGENCY_FEE_DISB, ISNULL(e.BBN_FEE,0) AS BBN_FEE_DISB,
            ISNULL(e.SurveyFeeGross_Cigna,0) AS SurveyFeeGross_Cigna_DISB,
            f.INS_CO, g.Notary_nm, i.Name_Indo AS FIN_TYPE, j.BRANCH_NAME, k.USERNAME,
            l.MLCI_CODE, l.DESCRIP, m.name AS cont_type_ket, o.name AS col_type_ket,
            q.Fullname_Without_Title, q.Live_since AS years_live,
            s.DESC_VALUE AS RESTRUCTURING_CHANGE,
            p.RT, p.RW, u.Desc_name AS KECAMATAN, v.Desc_name AS KELURAHAN,
            ISNULL(w.Survey_Fee_Cigna,0) AS Survey_Fee_Cigna, ISNULL(w.Survey_Loan_Cigna,0) AS Survey_Loan_Cigna,
            ISNULL(w.Credit_Protection,0) AS Credit_Protection,
            CASE WHEN w.GuarantedAcceptance='1' THEN 'Yes' ELSE 'No' END AS GuarantedAcceptance,
            ac.Net_Finance, ISNULL(y.Prov_loan,0) AS Prov_loan
        FROM
            CAFCONT a WITH (NOLOCK)
            LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
            LEFT JOIN CAFINSU c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
            LEFT JOIN MSTAMORTYPE d WITH (NOLOCK) ON a.L_TYPE = d.L_Type
            LEFT JOIN VDISBURSE e WITH (NOLOCK) ON a.APPL_NO = e.APPL_NO
            LEFT JOIN UMFINSCD f WITH (NOLOCK) ON c.INS_CD = f.INS_CD
            LEFT JOIN UMFNOTARY g WITH (NOLOCK) ON a.Notary_no = g.Notary_no
            LEFT JOIN MSTCFFL i WITH (NOLOCK) ON a.Cons_Leas = i.Cons_Leas
            LEFT JOIN UMFBRANCH j WITH (NOLOCK) ON a.BRANCH_CD = j.BRANCH_CD
            LEFT JOIN APP_USRMST k WITH (NOLOCK) ON a.CMO = k.EMPLOYEE_ID
            LEFT JOIN MstIndustry_lbpp l WITH (NOLOCK) ON b.INDUS_CODE = l.MLCI_CODE AND b.INDUS_CODE <> ''
            LEFT JOIN MSTCONTTYPE m WITH (NOLOCK) ON a.Cont_type = m.Cont_type
            LEFT JOIN MSTPURPOFFINC n WITH (NOLOCK) ON a.PURPOFFINC = n.PURPOFFINC
            LEFT JOIN MSTCOLLTYPE o WITH (NOLOCK) ON a.COL_TYPE = o.Col_Type
            LEFT JOIN CAFLESS_DETAIL_ADDRESS p WITH (NOLOCK) ON b.APLESS = p.APLESS
            LEFT JOIN CAFLESS_DETAIL q WITH (NOLOCK) ON b.APLESS = q.APLESS
            LEFT JOIN CAFCONT_RESTRUCTURING r WITH (NOLOCK) ON a.APPL_NO = r.APPL_NO
            LEFT JOIN MSTCOMBO s WITH (NOLOCK) ON r.RESTRUCTURING_CHANGE = s.VALUE
                AND s.CAT_VALUE = 'RESTRUCTURING_CHANGE'
            LEFT JOIN Mst_Kecamatan u WITH (NOLOCK) ON u.Kecamatan_CD = p.Kecamatan
            LEFT JOIN MST_KELURAHAN v WITH (NOLOCK) ON v.Kelurahan_CD = p.Kelurahan
            LEFT JOIN CIGNA_FEE w WITH (NOLOCK) ON w.APPL_NO = a.APPL_NO
            LEFT JOIN V_NetFinance ac WITH (NOLOCK) ON a.APPL_NO = ac.APPL_NO
            LEFT JOIN Provision_Loan y WITH (NOLOCK) ON a.APPL_NO = y.APPL_NO
            LEFT JOIN MSTCOMBO ad WITH (NOLOCK) ON a.ContSts = ad.VALUE AND ad.CAT_VALUE = 'FINANCE_STATUS'
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).mappings().first() or {})
    if not row:
        return None

    lessee_tp = row.get("LESSEE_TP") or ""
    cons_leas = row.get("Cons_Leas") or ""
    cont_type = row.get("Cont_type") or ""
    l_type = row.get("L_TYPE") or ""
    amor_type = row.get("amor_type") or ""
    create_date_raw = row.get("CREATE_DATE")

    bbn = (db.session.execute(text("""
        SELECT bbnvia, paidby, serviceagencyNM, BBNloan, BBN_FEE, ServiceAgencyFee, NettServiceAgencyFee
        FROM BBN WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).mappings().first() or {})
    bbn_via = bbn.get("bbnvia") or ""
    paid_by = bbn.get("paidby") or ""

    notary_fee_asli = _f(row.get("Gross"))
    nf = db.session.execute(text(
        "SELECT ISNULL(Notary_Fee,0) AS v FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:a AND split='Dealer'"),
        {"a": applno}).scalar()
    notaryfeegross = _f(nf) if nf else notary_fee_asli

    eq = (db.session.execute(text("""
        SELECT a.TAHUN, a.BPKB_AN, a.BPKB_ADDR, a.CITY_BPKB, a.CONDITION, a.MODEL, a.KAROSERI,
               a.BPKB_AN_TP, a.TYPE_CD, b.NAME AS SUPP_NM, b.SUPP, b.ADDRESS, b.CITY,
               c.DESCRIPTION AS Supp_Type, b.Supp_Type AS Supp_Type_CD,
               d.TYPE_NM, e.BRAND_NM, g.MODEL_NM
        FROM CAFEQUIP a WITH (NOLOCK)
            LEFT JOIN CLFSUPP b WITH (NOLOCK) ON a.SUPP = b.SUPP
            LEFT JOIN UMFTYPE d WITH (NOLOCK) ON a.BRAND = d.BRAND AND a.TYPE = d.TYPE
            LEFT JOIN UMFBRAND e WITH (NOLOCK) ON a.BRAND = e.BRAND
            LEFT JOIN UMFMODEL g WITH (NOLOCK) ON a.MODEL = g.MODEL
            LEFT JOIN MSTDEALERTYPE c WITH (NOLOCK) ON b.Supp_Type = c.CODE
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).mappings().first() or {})

    kondisi = "New" if (eq.get("CONDITION") or "").strip() == "NEW" else "Used"
    karoseri_desc = db.session.execute(text(
        "SELECT KAROSERI_DESC FROM UMFKAROSERI WITH (NOLOCK) WHERE MODEL=:m AND KAROSERI=:k"),
        {"m": eq.get("MODEL"), "k": eq.get("KAROSERI")}).scalar()
    if karoseri_desc:
        isian_kondisi = f"{kondisi}/ {eq.get('MODEL_NM') or ''} + {karoseri_desc}/ {eq.get('TAHUN') or ''}"
    else:
        isian_kondisi = f"{kondisi}/ {eq.get('MODEL_NM') or ''}/ {eq.get('TAHUN') or ''}"

    if cons_leas == "W":
        bis_type = "Showroom Financing"
    elif (eq.get("TYPE_CD") or "") == "07":
        bis_type = "Retail Automotive Financing"
    else:
        bis_type = "Retail Equipment Financing"

    paid = (db.session.execute(text("""
        SELECT ISNULL(L_AMOUNT,0) AS L_AMOUNT, ISNULL(DP,0) AS DP, ISNULL(ADMFEE,0) AS ADMFEE,
               ISNULL(Notary_Fee,0) AS Notary_Fee, ISNULL(PROV,0) AS PROV,
               ISNULL(BusinessTrip_Fee,0) AS BusinessTrip_Fee, ISNULL(DISB_INSC,0) AS DISB_INSC,
               ISNULL(FIRST_INST,0) AS FIRST_INST, ISNULL(SERVICE_AGENCY_FEE,0) AS SERVICE_AGENCY_FEE,
               ISNULL(BBN_FEE,0) AS BBN_FEE
        FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno AND split = 'Company'
    """), {"applno": applno}).mappings().first() or {})

    security_mlci = _f(paid.get("DP"))
    admfee_mlci = _f(paid.get("ADMFEE"))
    notaryfeegross_mlci = _f(paid.get("Notary_Fee"))
    provfee_mlci = _f(paid.get("PROV"))
    business_trip_mlci = _f(paid.get("BusinessTrip_Fee"))
    creditamt_mlci = _f(paid.get("DISB_INSC"))
    rental_mlci = _f(paid.get("FIRST_INST"))
    birja_hitung_mlci = _f(paid.get("SERVICE_AGENCY_FEE"))
    total_bbn_birja_mlci = _f(paid.get("BBN_FEE"))

    split_amounts = {
        r["split"]: _f(r["L_AMOUNT"])
        for r in db.session.execute(text(
            "SELECT split, ISNULL(L_AMOUNT,0) AS L_AMOUNT FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:a"),
            {"a": applno}).mappings().all()
    }
    l_amount_disb = (split_amounts.get("Dealer", 0.0) + split_amounts.get("Karoseri", 0.0)
                     + split_amounts.get("Accessories", 0.0) + split_amounts.get("Other", 0.0))

    adv = (db.session.execute(text(
        "SELECT Advance_Grace_Month, ISNULL(Advance_Grace_Amount,0) AS Advance_Grace_Amount "
        "FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:a AND split='Dealer'"),
        {"a": applno}).mappings().first() or {})
    adv_gperiod_m = adv.get("Advance_Grace_Month") or 0
    adv_gperiod_a = _f(adv.get("Advance_Grace_Amount"))

    birja_hitung_disb = 0.0
    bbn_hitung_disb = 0.0
    if paid_by == "Deduct from disbursement":
        birja_hitung_disb = _f(row.get("SERVICE_AGENCY_FEE_DISB"))
        bbn_hitung_disb = _f(row.get("BBN_FEE_DISB"))

    security_disb = _f(row.get("DP_DISB")) - security_mlci
    admfee_disb = _f(row.get("ADMFEE_DISB")) + _f(row.get("SurveyFeeGross_Cigna_DISB"))
    admfee_disb = (admfee_disb - admfee_mlci) if admfee_disb > 0 else ((admfee_disb * -1) - admfee_mlci)
    provfee_disb = _f(row.get("PROVISION_DISB")) - provfee_mlci
    creditamt_disb = _f(row.get("DISB_INSC")) - creditamt_mlci
    rental_disb = _f(row.get("FIRST_INST_DISB")) - rental_mlci
    business_trip = _f(row.get("BusinessTrip_Fee")) - business_trip_mlci
    birja_hitung_disb = birja_hitung_disb - birja_hitung_mlci

    refund_supp = _f(row.get("Refund_Supp"))
    subsidy_supp = _f(row.get("Subsidy_Supp"))
    subsidy_dealer = _f(row.get("SUBSIDY"))

    disb_dealer = (l_amount_disb - security_disb - admfee_disb - provfee_disb - creditamt_disb
                   - rental_disb - business_trip - birja_hitung_disb - notaryfeegross
                   - bbn_hitung_disb + refund_supp - subsidy_supp)

    comm_dealer_row = (db.session.execute(text(
        "SELECT FEE, GrossAmount, PPNAmount FROM CAFKOMIS WITH (NOLOCK) WHERE APPL_NO=:a AND SD_TYPE='D'"),
        {"a": applno}).mappings().first() or {})
    comm_dealer = _f(comm_dealer_row.get("GrossAmount")) + _f(comm_dealer_row.get("PPNAmount"))
    tot_pmt_dealer = disb_dealer + comm_dealer

    commission_sales, tot_comm_sls = _report_cam_sales_commission(applno, create_date_raw)

    calc_dt = db.session.execute(text(
        "SELECT TOP 1 ASOF FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a GROUP BY ASOF ORDER BY ASOF DESC"),
        {"a": applno}).scalar()
    outs_labels = {1: "Disburse", 2: "UnDisburse", 3: "UnApprove", 4: "Group", 5: "Guarantor"}
    outstanding_rows, fl_tot_unit, fl_tot = [], 0, 0.0
    amounts = {}
    if calc_dt:
        ot = db.session.execute(text("""
            SELECT TYPE, ISNULL(SUM(UNIT),0) AS UNIT, ISNULL(SUM(OUTS),0) AS OUTS
            FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:a AND ASOF=:asof GROUP BY TYPE ORDER BY TYPE
        """), {"a": applno, "asof": calc_dt}).mappings().all()
        amounts = {r["TYPE"]: (r["UNIT"], _f(r["OUTS"])) for r in ot}
    for t in (1, 2, 3, 4, 5):
        unit, amt = amounts.get(t, (0, 0.0))
        outstanding_rows.append({"label": outs_labels[t], "unit": unit, "amount": amt})
        fl_tot_unit += unit
        fl_tot += amt

    cross_contract_numbers, cross_no_atasan, cross_no_atasd = _report_cam_cross_numbers(applno)
    lease_no, lessee_no = _report_cam_contract_no(applno)
    jfg = db.session.execute(text(
        "SELECT IIF(lease_no<>'', '(JFG)', '') AS JFG FROM JF_GANESHA WITH (NOLOCK) WHERE lease_no=:l"),
        {"l": lease_no}).scalar() if lease_no else ""

    bank_rows = db.session.execute(text("""
        SELECT a.BANK, a.BANK_BRANCH, a.ACC_NO, a.ACC_NM, a.AMOUNT, b.[DESC] AS bank_name
        FROM CAFDISBACC a WITH (NOLOCK)
        LEFT JOIN UMFBANK b WITH (NOLOCK) ON a.Bank = b.BANK_CODE
        WHERE a.APPL_NO = :a
    """), {"a": applno}).mappings().all()
    bank_accounts = [
        {
            "bank_branch": f"{r.get('bank_name') or r.get('BANK') or ''} - {r.get('BANK_BRANCH') or ''}".strip(" -"),
            "account_no": (r.get("ACC_NO") or "").strip(),
            "account_name": r.get("ACC_NM") or "",
            "amount": _f(r.get("AMOUNT")),
        }
        for r in bank_rows
    ]

    appr_rows = db.session.execute(text("""
        SELECT a.APPR_DATE, a.APPR_ID_TO, b.FULLNAME
        FROM MCMOCAMStatus a WITH (NOLOCK)
        INNER JOIN APP_USRMST b ON b.USERNAME = a.APPR_ID
        WHERE a.APPL_NO = :a AND a.APPR_STS IN ('F','A')
        ORDER BY a.APPR_DATE, a.[No]
    """), {"a": applno}).mappings().all()
    approval_history = [
        {
            "full_name": r.get("FULLNAME") or "",
            "date": r["APPR_DATE"].strftime("%d-%m-%Y %H:%M:%S") if r.get("APPR_DATE") else "",
            "sent_to_admin": r.get("APPR_ID_TO") == "Admin",
        }
        for r in appr_rows
    ]

    ref_rows = db.session.execute(text("""
        SELECT REF_NAME, REF_PHONE, REMARK FROM CAFREF WITH (NOLOCK)
        WHERE APLESS = :a ORDER BY INPUT_DT DESC
    """), {"a": apless}).mappings().all()
    references = [
        {"name": r.get("REF_NAME") or "", "phone": r.get("REF_PHONE") or "", "remark": r.get("REMARK") or ""}
        for r in ref_rows
    ]

    irr_val = db.session.execute(text(
        "SELECT IRR_Actual FROM CAFCONT_IRR WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}).scalar()

    var_dp_label = "Down Payment" if cons_leas not in ("S", "F") else "Security Deposit"
    l_amount = _f(row.get("L_AMOUNT"))
    security = _f(row.get("SECURITY"))
    security_pct = round((security * 100) / l_amount, 2) if l_amount else 0
    net_finance = _f(row.get("Net_Finance"))
    loan_to_value = round((net_finance / l_amount) * 100, 2) if l_amount else 0
    fix_float_label = "Fixed Rate" if row.get("FIX_FLOAT") == "X" else "Float Rate"
    adv_arr_label = "Advance" if row.get("ADV_ARR") == "V" else "Arrears"
    npwp = row.get("NPWP") or ""
    npwp_fmt = _npwp_format(npwp) if npwp else ""

    years_live = row.get("years_live")
    address_full = (f"{row.get('ADDRESS1') or ''}, RT. {row.get('RT') or ''}/{row.get('RW') or ''}, "
                    f"{row.get('KELURAHAN') or ''}, {row.get('KECAMATAN') or ''}, "
                    f"{row.get('CITY1') or ''} {row.get('Zipcode1') or ''}")
    if lessee_tp == "PR":
        if years_live is not None:
            address_full += f"<br/>Live here for {datetime.now().year - int(years_live)} year (s)"
    else:
        address_full = (f"{row.get('ADDRESS2') or ''}, RT. {row.get('RT') or ''}/{row.get('RW') or ''}, "
                        f"{row.get('KELURAHAN') or ''}, {row.get('KECAMATAN') or ''}, "
                        f"{row.get('CITY2') or ''} {row.get('Zipcode2') or ''}")

    has_guarantor = bool(db.session.execute(text(
        "SELECT 1 FROM CAFGUARN WITH (NOLOCK) WHERE APPL_NO=:a AND APLESS=:ap"),
        {"a": applno, "ap": apless}).first())

    ind_cor_inferred = "1" if lessee_tp == "PR" else "2"

    strrevisi, revisi_note = _report_cam_revision_note(applno)
    str_multiple = _report_cam_multiple_flag(applno)

    org_structure = _report_cam_org_structure(applno, apless)

    internal_disbursement, internal_total = _financing_internal_disbursement(applno)
    external_disbursement, external_total = _financing_external_disbursement(applno, ind_cor_inferred)

    flagcom = row.get("FLAGCOM")
    incent = row.get("incentive")

    return {
        "header": {
            "cam_no": f"{applno}{strrevisi}{str_multiple}/{apless}",
            "appl_no": applno,
            "cont_type": f"{row.get('cont_type_ket') or ''} {cross_no_atasan}".strip(),
            "contsts": f"{row.get('ContSts') or ''} {jfg or ''}".strip(),
            "contract_no": f"{lease_no}/{lessee_no}" if (lease_no or lessee_no) else "",
            "cross_disbursement_no": cross_no_atasd,
            "bis_type": bis_type,
            "purpose_finc": row.get("PURPOFFINC") or "",
            "fin_type": row.get("FIN_TYPE") or "",
            "branch_name": row.get("BRANCH_NAME") or "",
            "create_date": _fmt_date(create_date_raw, "%d-%m-%Y %I:%M:%S"),
            "print_date": datetime.now().strftime("%d-%m-%Y %I:%M:%S"),
            "cmo_name": row.get("USERNAME") or "",
            "corporate_finance": _report_cam_corporate_finance(apless),
            "cross_contract_numbers": cross_contract_numbers,
        },
        "customer": {
            "name_in_label": "ID Card" if lessee_tp == "PR" else "Akta",
            "name_in_id": row.get("LESSEE_NM") or "",
            "customer_name_label": "Customer Name Without Title" if lessee_tp == "PR" else "Customer Name",
            "customer_name": (f"{row.get('Fullname_Without_Title') or ''} ({row.get('umur')} years old)"
                              if lessee_tp == "PR" else (row.get("Fullname_Without_Title") or "")),
            "address": address_full,
            "phone1": row.get("PHONE1") or "",
            "phone2": row.get("PHONE2") or "",
            "phone3": row.get("PHONE3") or "",
            "mail_address": f"{row.get('MAIL_ADDR') or ''}, {row.get('MAIL_CITY') or ''} {row.get('Zipcode3') or ''}".strip(),
            "npwp": npwp_fmt,
            "guarantor": "Available" if has_guarantor else "Not Available",
            "industry": _report_cam_industry(row.get("MLCI_CODE"), row.get("DESCRIP")),
        },
        "finance": {
            "asset_value": l_amount,
            "dp_label": var_dp_label,
            "dp_percent": security_pct,
            "security": security,
            "insurance_loan": _f(row.get("CREDITAMT")),
            "bbn_loan": _f(bbn.get("BBNloan")),
            "provision_loan": _f(row.get("Prov_loan")),
            "others_loan": _f(row.get("Otherloan")) + _f(row.get("Survey_Loan_Cigna")),
            "net_finance": net_finance,
            "loan_to_value": loan_to_value,
            "type_of_finance": f"{fix_float_label} / {amor_type}".strip(" /"),
            "payment_method": row.get("col_type_ket") or "",
            "tenor": row.get("TENOR"),
            "adv_arr_label": adv_arr_label,
            "irr": float(irr_val) if irr_val is not None else None,
            "selling_rate_flat": f"{round(_f(row.get('FLATRATE')), 4):g}",
            "decl_rate": f"{_f(row.get('DECLRATE')):.7f}",
            "survey_fee_gross": _f(row.get("AdmFee")) + _f(row.get("Survey_Fee_Cigna")),
            "notary_fee_gross": notary_fee_asli,
            "provision_fee": _f(row.get("PROVISION")),
            "business_trip_fee": _f(row.get("BusinessTrip_Fee")),
            "installment": _f(row.get("RENTAL")),
            "installment_steps": _report_cam_installment_steps(applno) if str(l_type) == "3" else [],
            "is_step_1000": amor_type == "Step 1000",
            "customer_flat_rate": str(row.get("FLATRATE1000") or ""),
            "customer_tenor": row.get("TENOR1000"),
            "grace_period_month": row.get("G_PERIOD"),
            "grace_int_rate": _truncate_decimal(row.get("G_INT_RATE"), 4),
            "grace_int_amount": _f(row.get("G_INT_AMT")),
            "show_restructuring": cont_type in ("RS1", "RS0"),
            "restructuring_change": row.get("RESTRUCTURING_CHANGE") or "",
        },
        "insurance": {
            "name": row.get("INS_CO") or "",
            "type": _report_cam_insurance_type(applno, row.get("INS_POL")),
            "gross_premium": _f(row.get("GROSS_PREM")),
            "net_premium": _f(row.get("NET_COM")),
        },
        "notary": {
            "vendor": f"{row.get('Notary_no') or ''} {row.get('Notary_nm') or ''}".strip(),
            "fiducia_deed": _f(row.get("Notary")),
            "fiducia_cert": _f(row.get("Fiduciary")),
        },
        "agency": {
            "bbn_via": bbn_via,
            "paid_by": paid_by,
            "agency_name": bbn.get("serviceagencyNM") or "",
            "agency_fee_gross": _f(bbn.get("ServiceAgencyFee")),
            "bbn_fee": _f(bbn.get("BBN_FEE")),
            "nett_agency_fee": _f(bbn.get("NettServiceAgencyFee")),
        },
        "asset": {
            "condition_label": "Condition/ Model/ Year",
            "condition_model_year": isian_kondisi,
            "brand_name": f"{eq.get('BRAND_NM') or ''} {eq.get('TYPE_NM') or ''}".strip(),
            "name_in_bpkb": eq.get("BPKB_AN") or "",
            "purpose_of_finance": row.get("PURPOFFINC") or "",
            "bpkb_address": f"{eq.get('BPKB_ADDR') or ''}, {eq.get('CITY_BPKB') or ''}".strip(", "),
        },
        "dealer": {
            "name": eq.get("SUPP_NM") or "",
            "type": eq.get("Supp_Type") or "",
            "address": f"{eq.get('ADDRESS') or ''}, {eq.get('CITY') or ''}".strip(", "),
            "disb_accounts": _report_cam_disb_accounts(applno),
            "status": _report_cam_dealer_status(eq.get("SUPP"), create_date_raw),
        },
        "disbursement": {
            "paid_to_company": {
                "dp": security_mlci,
                "survey_fee_gross": admfee_mlci,
                "notary_fee_gross": notaryfeegross_mlci,
                "provision_fee": provfee_mlci,
                "business_trip_fee": business_trip_mlci,
                "insurance": creditamt_mlci,
                "first_installment": rental_mlci,
                "agency_fee_gross": birja_hitung_mlci,
                "bbn_fee": total_bbn_birja_mlci,
            },
            "to_dealer": {
                "asset_value": l_amount_disb,
                "dp": security_disb,
                "survey_fee_gross": admfee_disb,
                "notary_fee_gross": notaryfeegross,
                "provision_fee": provfee_disb,
                "business_trip_fee": business_trip,
                "insurance": creditamt_disb,
                "first_installment": rental_disb,
                "advance_grace_period": adv_gperiod_a,
                "agency_fee_gross": birja_hitung_disb,
                "bbn_fee": bbn_hitung_disb,
                "subsidy_from_dealer": subsidy_supp,
                "refund_to_dealer": refund_supp,
                "disbursement_to_dealer": disb_dealer,
                "commission_to_dealer_gross": comm_dealer,
                "total_payment_to_dealer": tot_pmt_dealer,
            },
            "advance_grace_month": adv_gperiod_m,
            "show_commission_to_dealer": flagcom in ("1", 1, 0, "0", None),
            "apm_label": "Incentive from APM" if str(incent) == "1" else "Subsidy from APM",
            "apm_amount": subsidy_dealer,
            "commission_sales": commission_sales,
            "total_gross_commission": tot_comm_sls,
            "credit_protection": _f(row.get("Credit_Protection")),
            "guaranteed_acceptance": row.get("GuarantedAcceptance") or "No",
            "signoff_roles": SIGNOFF_ROLES,
            "related_survey_cam": _report_cam_related_survey(applno, apless),
        },
        "outstanding": {
            "process_date": calc_dt.strftime("%d/%m/%Y") if calc_dt else "",
            "rows": outstanding_rows,
            "total_unit": fl_tot_unit,
            "total_amount": fl_tot,
        },
        "equipment_detail": _report_cam_equipment_detail(applno, cons_leas),
        "org_structure": org_structure,
        "lessee_name": row.get("LESSEE_NM") or "",
        "internal_disbursement": {"rows": internal_disbursement, "total": internal_total},
        "external_disbursement": {"rows": external_disbursement, "total": external_total},
        "bank_accounts": bank_accounts,
        "approval_history": approval_history,
        "references": references,
        "cam_notes": row.get("CAM_NOTES") or "",
        "notes": row.get("NOTES") or "",
        "revised_note": revisi_note,
        "pending_notes": _report_cam_pending_notes(applno),
        "beneficial_owner_availability": _report_cam_bo_availability(applno),
        "customer_data": _report_cam_customer_data(applno, apless, ind_cor_inferred),
        "customer_survey": _report_cam_customer_survey(applno, apless, ind_cor_inferred),
        "financial_review": _report_cam_financial_review(applno, apless, ind_cor_inferred),
        "apu_ppt": _apu_ppt_data(applno),
        "omitted_sections": [
            x for x in OMITTED_REPORT_SECTIONS
            if not (org_structure and x.startswith("Business Profile"))
        ],
    }

def _report_cam_credit_scoring(applno):
    try:
        rows = db.session.execute(text("EXEC USP_S_ScoringCAM :a"), {"a": applno}).mappings().all()
    except Exception:
        return None
    if not rows:
        return None
    items = [
        {"description": r.get("Description") or "", "result": r.get("Result") or "", "score": r.get("SCORE")}
        for r in rows
    ]
    total = rows[-1].get("Total") if rows else None
    return {"items": items, "total_score": total}

def _apu_ppt_data(applno):
    main_row = _apu_ppt_main_row(applno)
    if main_row is None:
        return None

    edd_customer, edd_bo = _apu_ppt_edd_flags(applno)
    bon = main_row.get("BO_Name") or "-"
    has_bo = bon != "-"

    return {
        "customer": {
            "name": main_row.get("LESSEE_NM") or "-",
            "type": f"{main_row.get('lesse_tp', '')} / {main_row.get('NAME', '')}" if main_row.get("lesse_tp") else "-",
            "occupation_business_type": main_row.get("DESC_VALUE") or "-",
            "apu_ppt_status": main_row.get("status") or "-",
            "identification_verification": main_row.get("identity_Cus") or "-",
        },
        "show_edd_customer": edd_customer == "1",
        "edd_customer_questions": _apu_ppt_questionnaire("EDD_CustomerEng") if edd_customer == "1" else [],
        "show_beneficial_owner": has_bo,
        "beneficial_owner": {
            "name": bon,
            "type": f"{main_row.get('lesse_tp2', '')} / {main_row.get('NAME2', '')}" if main_row.get("lesse_tp2") else "-",
            "occupation_business_type": main_row.get("DESC_VALUE2") or "-",
            "apu_ppt_status": main_row.get("status2") or "-",
            "identification_verification": main_row.get("identity_BO") or "-",
        },
        "show_edd_bo": has_bo and edd_bo == "1",
        "edd_bo_questions": _apu_ppt_questionnaire("EDD_BOEng") if (has_bo and edd_bo == "1") else [],
    }

def _report_cam_customer_data(applno, apless, ind_cor):
    if ind_cor != "2":
        return None

    row = db.session.execute(
        text("SELECT a.Business_size, a.APLESS, a.LESSEE_NM, a.Lessee_Cat, a.ADDRESS1, "
             "a.ADDRESS2, a.CITY2, a.PHONE2, a.ZipCode2, a.Fax2, "
             "a.ADDRESS3, a.CITY3, a.PHONE3, a.ZipCode3, a.Fax3, "
             "a.ADDRESS4, a.CITY4, a.PHONE4, a.ZipCode4, a.Fax4, "
             "a.Address5, a.City5, a.Phone5, a.ZipCode5, a.Fax5, "
             "a.CITY1, a.ZipCode1, a.PHONE1, a.Mobile_phone1, a.Mobile_phone2, a.Mobile_phone3, "
             "a.EMAIL1, a.EMAIL2, a.NPWP, a.Fax1, a.TGLBIRTH, a.REVIEW, a.Contact, "
             "a.Occupation AS position, a.LOB, b.name AS officestatus, c.NAME AS custtype, "
             "CASE WHEN d.FLGDEL='1' THEN '-' ELSE d.GrpName END AS GrpName, "
             "i.MLCI_Desc, mi.Descrip, a.PLACEBIRTH, e.NumberOfEmployee "
             "FROM CAFLESS a WITH (NOLOCK) "
             "LEFT JOIN MSTADDRESSSTATUS b WITH (NOLOCK) ON a.Address_Status=b.AddressStatus "
             "LEFT JOIN MSTLESSEETYPE c WITH (NOLOCK) ON a.Lessee_Cat=c.CUST_TYPE AND c.LESSEE_TP='PT' "
             "LEFT JOIN MstIndustry_lbpp mi WITH (NOLOCK) ON a.INDUS_CODE=mi.MLCI_CODE AND a.INDUS_CODE<>'' "
             "LEFT JOIN CLFGROUP d WITH (NOLOCK) ON a.GrpCode=d.GrpCode "
             "LEFT JOIN UMFBITYP_LBPP i WITH (NOLOCK) ON a.Cust_Type=i.OJK_Code "
             "LEFT JOIN CAFLESS_DETAIL e WITH (NOLOCK) ON a.apless=e.apless "
             "WHERE a.APLESS=:ap"),
        {"ap": apless}
    ).mappings().first()
    if not row:
        return None

    detail = db.session.execute(
        text("SELECT q.Fullname_Without_Title, "
             "b.OTHER_PHONE1, b.OTHER_PHONE2, b.OTHER_PHONENOTES1, b.OTHER_PHONENOTES2, "
             "b.Area_CD, b.CITY2, "
             "p.Address_NPWP, p.Area_CD_NPWP, p.Zipcode_NPWP, p.RT, p.RW, "
             "aa.DESC_VALUE AS BUSINESS_ENTITY, "
             "IIF(q.GO_PUBLIC=1,'Yes','No') AS GO_PUBLIC, "
             "ww.DESC_VALUE AS RELATIONSHIP, "
             "u.Desc_name AS KECAMATAN, v.Desc_name AS KELURAHAN, "
             "u1.Desc_name AS Kecamatan_NPWP, v1.Desc_name AS Kelurahan_NPWP, "
             "x.PROPINSI AS PROPINSI_NPWP, x.KABUPATEN AS KABUPATEN_NPWP, "
             "ar.Propinsi AS PROPINSI "
             "FROM CAFLESS b WITH (NOLOCK) "
             "LEFT JOIN CAFLESS_DETAIL q WITH (NOLOCK) ON b.APLESS=q.APLESS "
             "LEFT JOIN CAFLESS_DETAIL_ADDRESS p WITH (NOLOCK) ON b.APLESS=p.APLESS "
             "LEFT JOIN MSTCOMBO ww WITH (NOLOCK) ON q.RELATIONSHIP=ww.VALUE "
             "AND ww.CAT_VALUE='RELATIONSHIP_MLCI' "
             "LEFT JOIN MSTCOMBO aa WITH (NOLOCK) ON q.BUSINESS_ENTITY=aa.VALUE "
             "AND aa.CAT_VALUE='BUSINESS_ENTITY' "
             "LEFT JOIN Mst_Kecamatan u WITH (NOLOCK) ON u.kecamatan_CD=p.kecamatan "
             "LEFT JOIN MST_KELURAHAN v WITH (NOLOCK) ON v.kelurahan_CD=p.kelurahan "
             "LEFT JOIN Mst_Kecamatan u1 WITH (NOLOCK) ON u1.kecamatan_CD=p.Kecamatan_NPWP "
             "LEFT JOIN MST_KELURAHAN v1 WITH (NOLOCK) ON v1.kelurahan_CD=p.Kelurahan_NPWP "
             "LEFT JOIN UMFAREA x WITH (NOLOCK) ON x.AREA_CD=p.AREA_CD_NPWP "
             "LEFT JOIN UMFAREA ar WITH (NOLOCK) ON ar.AREA_CD=b.Area_CD "
             "WHERE b.APLESS=:ap"),
        {"ap": apless}
    ).mappings().first() or {}

    business_size = db.session.execute(
        text("SELECT DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) "
             "WHERE CAT_VALUE='BUSINESS_SIZE' AND VALUE=:v"),
        {"v": row.get("Business_size")}
    ).scalar() or ""

    def dash(v):
        v = (v or "") if isinstance(v, str) else v
        return v if v not in (None, "") else "-"

    def block(address, city, zipcode, phone, fax):
        if not address and not city and not zipcode and not phone and not fax:
            return "-"
        out = f"{address or ''}<br>{city or ''}, {zipcode or ''}"
        if phone:
            out += f"<br>(P) {phone}"
            if fax:
                out += f" - (F) {fax}"
        return out

    def additional(address, city, zipcode, phone, fax):
        if not address:
            return "-"
        out = f"{address}<br>{city or ''}, {zipcode or ''}<br>(P) {phone or ''}"
        if fax:
            out += f" - (F) {fax}"
        return out

    mobile = ", ".join(
        x for x in [row.get("Mobile_phone1"), row.get("Mobile_phone2"), row.get("Mobile_phone3")] if x
    ) or "-"
    email = ", ".join(x for x in [row.get("EMAIL1"), row.get("EMAIL2")] if x) or "-"

    npwp = row.get("NPWP") or ""
    npwp_shown = _npwp_format(npwp) if npwp else "-"

    npwp_addr = f"{detail.get('Address_NPWP') or ''} {detail.get('KABUPATEN_NPWP') or ''},{detail.get('Zipcode_NPWP') or ''}"

    return {
        "is_corporate": True,
        "name_in_akta": row.get("LESSEE_NM") or "",
        "customer_name": f"{detail.get('Fullname_Without_Title') or ''} / {apless}",
        "business_size": business_size,
        "address_sk_domisili": block(row.get("ADDRESS2"), row.get("CITY2"), row.get("ZipCode2"),
                                     row.get("PHONE1"), row.get("Fax1")),
        "correspondence": block(row.get("ADDRESS3"), row.get("CITY3"), row.get("ZipCode3"),
                                row.get("PHONE3"), row.get("Fax3")),
        "additional1": additional(row.get("ADDRESS4"), row.get("CITY4"), row.get("ZipCode4"),
                                  row.get("PHONE4"), row.get("Fax4")),
        "additional2": additional(row.get("Address5"), row.get("City5"), row.get("ZipCode5"),
                                  row.get("Phone5"), row.get("Fax5")),
        "province": detail.get("PROPINSI") or "",
        "district_city": detail.get("CITY2") or "",
        "kecamatan": detail.get("KECAMATAN") or "",
        "kelurahan": detail.get("KELURAHAN") or "",
        "rt_rw": f"{detail.get('RT') or ''} / {detail.get('RW') or ''}",
        "office_status": dash(row.get("officestatus")),
        "type": dash(row.get("custtype")),
        "whatsapp_no": row.get("Mobile_phone1") or "",
        "mobile": mobile,
        "other_phone1": detail.get("OTHER_PHONE1") or "",
        "other_phone_notes1": detail.get("OTHER_PHONENOTES1") or "",
        "other_phone2": detail.get("OTHER_PHONE2") or "",
        "other_phone_notes2": detail.get("OTHER_PHONENOTES2") or "",
        "email": email,
        "npwp": npwp_shown,
        "address_npwp": npwp_addr,
        "npwp_province": detail.get("PROPINSI_NPWP") or "",
        "npwp_district_city": detail.get("KABUPATEN_NPWP") or "",
        "npwp_kecamatan": detail.get("Kecamatan_NPWP") or "",
        "npwp_kelurahan": detail.get("Kelurahan_NPWP") or "",
        "business_entity": detail.get("BUSINESS_ENTITY") or "",
        "go_public": detail.get("GO_PUBLIC") or "",
        "relationship_with_company": detail.get("RELATIONSHIP") or "",
        "group": dash(row.get("GrpName")),
        "contact": dash(row.get("Contact")),
        "position": dash(row.get("position")),
        "establishment_place_date": f"{row.get('PLACEBIRTH') or ''} / {_fmt_date(row.get('TGLBIRTH'))}",
        "line_of_business": dash(row.get("LOB")),
        "occupation": dash(row.get("custtype")),
        "industry": row.get("Descrip") or "-",
        "bi_customer_type": row.get("MLCI_Desc") or "",
        "number_of_employee": f"{row.get('NumberOfEmployee')} people(s)" if row.get("NumberOfEmployee") is not None else "",
        "review_date": _fmt_date(row.get("REVIEW")),
    }

def _report_cam_customer_survey(applno, apless, ind_cor):
    tenor = db.session.execute(
        text("SELECT TENOR FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a AND APLESS=:ap"),
        {"a": applno, "ap": apless}
    ).scalar()
    credit_period = _survey_credit_period(tenor)

    inst_row = db.session.execute(
        text("SELECT rental, ContSts FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}
    ).first()
    installment = _f(inst_row[0]) if inst_row else 0.0
    contsts = inst_row[1] if inst_row else None

    condition_raw = db.session.execute(
        text("SELECT CONDITION FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO=:a"), {"a": applno}
    ).scalar()
    kondisi = "New" if (condition_raw or "").strip() == "NEW" else "Used"

    data = (
        _survey_individual(applno, apless, installment, contsts, kondisi) if ind_cor == "1"
        else _survey_corporate(applno, apless, installment, contsts, kondisi)
    )

    if data is None:
        character, capital, capacity, collateral, condition = {}, {}, {}, {}, {}
        note_sid = ""
    else:
        character, capital, capacity = data["character"], data["capital"], data["capacity"]
        collateral, condition = data["collateral"], data["condition"]
        note_sid = data.get("note_sid") or ""

    cont_row = db.session.execute(
        text("""SELECT a.HAS_GUARANTOR, ISNULL(a.L_AMOUNT,0) as L_AMOUNT, ISNULL(a.SECURITY,0) as SECURITY,
                    ISNULL(a.Otherloan,0) as Otherloan, ISNULL(b.CREDITAMT,0) as CREDITAMT,
                    ISNULL(c.Survey_Loan_Cigna,0) as Survey_Loan_Cigna, ISNULL(d.BBNLoan,0) as BBNLoan,
                    ISNULL(e.Prov_loan,0) as Prov_loan
                FROM CAFCONT a WITH (NOLOCK)
                    LEFT JOIN CAFINSU b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    LEFT JOIN Cigna_fee c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                    LEFT JOIN BBN d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
                    LEFT JOIN Provision_Loan e WITH (NOLOCK) ON a.APPL_NO = e.APPL_NO
                WHERE a.APPL_NO=:a"""),
        {"a": applno}
    ).mappings().first()

    loan_to_value, guarantor_label = 0.0, "Not Available"
    if cont_row:
        l_amount = _f(cont_row["L_AMOUNT"])
        totnetfinance = (
            l_amount - _f(cont_row["SECURITY"]) + _f(cont_row["CREDITAMT"]) + _f(cont_row["Otherloan"])
            + _f(cont_row["Survey_Loan_Cigna"]) + _f(cont_row["BBNLoan"]) + _f(cont_row["Prov_loan"])
        )
        loan_to_value = round(totnetfinance / l_amount * 100, 2) if l_amount else 0.0
        guarantor_label = "Available" if cont_row["HAS_GUARANTOR"] == "1" else "Not Available"

    job_hist_rows = db.session.execute(
        text("""
            SELECT ch.[FROM], ch.UNTIL, ch.Company, ch.Company_Address, ch.Phone,
                   ch.Employee_ID, ua.KABUPATEN, ua.PROPINSI, ch.Postcode,
                   CONCAT(mc.DESC_VALUE, IIF(ch.Position_Other<>'', CONCAT(' (', ch.Position_Other, ')'), '')) AS PositionLabel
            FROM CAFLESS_History ch WITH (NOLOCK)
                INNER JOIN UMFAREA ua ON ua.Area_Cd = ch.AREA_CD
                INNER JOIN MSTCOMBO mc ON mc.VALUE = ch.Position AND mc.CAT_VALUE = 'HISTORY_POSITION'
            WHERE ch.APLESS = :ap
        """), {"ap": apless}
    ).mappings().all()

    job_history = []
    for r in job_hist_rows:
        from_raw, until_raw = str(r["FROM"] or ""), str(r["UNTIL"] or "")
        job_history.append({
            "from": f"{from_raw[4:6]}-{from_raw[0:4]}" if len(from_raw) >= 6 else "",
            "until": "Present" if until_raw == "000000" else (f"{until_raw[4:6]}-{until_raw[0:4]}" if len(until_raw) >= 6 else ""),
            "company": r["Company"] or "", "address": r["Company_Address"] or "",
            "city": r["KABUPATEN"] or "", "province": r["PROPINSI"] or "",
            "postal_code": r["Postcode"] or "", "employee_id": r["Employee_ID"] or "",
            "position": r["PositionLabel"] or "", "phone": r["Phone"] or "",
        })

    sid_checking = [
        {
            "subject": s["subject"], "credit_bureau": s["credit_bureau"], "status": s["status"],
            "score": s["score"], "grade": s["grade"],
            "file_label": "Download" if s.get("pefindo_download_url") else None,
            "file_url": s.get("pefindo_download_url"),
        }
        for s in _survey_sid_checking(applno)
    ]

    return {
        "is_corporate": ind_cor == "2",
        "credit_history": character.get("credit_history_label"),
        "reference": character.get("reference"),
        "work_experience": character.get("work_experience"),
        "business_size": db.session.execute(
            text("SELECT c.DESC_VALUE FROM CAFLESS a WITH (NOLOCK) "
                 "LEFT JOIN MSTCOMBO c WITH (NOLOCK) ON c.VALUE=a.Business_size "
                 "AND c.CAT_VALUE='BUSINESS_SIZE' WHERE a.APLESS=:ap"),
            {"ap": apless}
        ).scalar() or "",
        "company_status": character.get("company_status"),
        "scale_of_business": character.get("scale_of_business"),
        "living": capital.get("living_label"),
        "living_status": capital.get("living_status_label"),
        "car_ownership": capital.get("car_ownership"),
        "business_location": capital.get("business_location"),
        "office_status": capital.get("office_status"),
        "total_unit_owned": capital.get("total_unit_owned"),
        "unit_free_from_finance": capital.get("unit_free_from_finance"),
        "estimated_total_assets": capital.get("estimated_total_assets_label"),
        "estimated_total_assets_as_of": capital.get("estimated_total_assets_asof"),
        "job_customer": capacity.get("job_occupation_customer"),
        "fixed_monthly_income": capacity.get("fixed_monthly_income"),
        "income_source_note": capacity.get("fixed_income_source_label"),
        "spouse_income": capacity.get("spouse_income_per_month"),
        "other_income": capacity.get("total_other_income"),
        "other_income_note": capacity.get("total_other_income_status"),
        "total_income": capacity.get("total_income_per_month"),
        "total_income_note": capacity.get("total_income_status"),
        "average_income_per_year": capacity.get("average_income_per_year"),
        "monthly_profit": capacity.get("monthly_profit"),
        "monthly_profit_note": capacity.get("monthly_profit_status"),
        "monthly_profit_source": capacity.get("monthly_profit_source_label"),
        "sales_per_month": capacity.get("sales_per_month"),
        "net_profit_ratio": capacity.get("net_profit_to_sales"),
        "unit_type": collateral.get("unit_type"),
        "loan_to_value": loan_to_value,
        "insurance_payment": collateral.get("insurance"),
        "guarantor_available": guarantor_label,
        "payment_method": collateral.get("payment_method"),
        "credit_period": credit_period,
        "total_outstanding_bucket": condition.get("total_outstanding_label"),
        "dealer_status": condition.get("dealer_status"),
        "usage_of_car": condition.get("usage_of_car"),
        "job_history": job_history,
        "sid_checking": sid_checking,
        "sid_checking_notes": note_sid,
    }
    
def _report_cam_financial_review(applno, apless, ind_cor):
    date_row = db.session.execute(
        text("SELECT CONVERT(VARCHAR(6), CREATE_DATE, 112) AS YEARS FROM CAFCONT WITH (NOLOCK) "
             "WHERE APLESS=:apless AND APPL_NO=:applno"),
        {"apless": apless, "applno": applno}
    ).mappings().first()
    dates = (date_row["YEARS"] if date_row else None) or datetime.now().strftime("%Y")

    bank_statements = [
        {
            "bank_name": b["bank_name"], "branch": b["branch"], "account_no": b["account_no"],
            "account_name": b["account_name"], "currency": b["currency"], "notes": b["notes"],
            "rows": [
                {"period": s["period_label"], "beginning_balance": s["beginning_balance"],
                 "debit": s["debet"], "credit": s["credit"], "ending_balance": s["ending_balance"],
                 "notes": s["notes"]}
                for s in b["statements"]
            ],
        }
        for b in _bank_accounts(apless, applno) if b["statements"]
    ]

    if ind_cor == "1":
        section = _individual_finance(apless, applno)
        if section.get("no_data"):
            return {
                "currency": "IDR",
                "period_label": None,
                "liabilities": [],
                "total_liabilities": 0,
                "monthly_income": [],
                "total_income": 0,
                "net_saving": 0,
                "assets": [],
                "total_assets": 0,
                "dscr": 0,
                "bank_statements": bank_statements,
            }
        return {
            "currency": section.get("currency"),
            "period_label": section.get("period_label"),
            "liabilities": [
                {"description": r["description"], "amount": r["amount"], "notes": r.get("category")}
                for r in section["liabilities"]["rows"]
            ],
            "total_liabilities": section["liabilities"]["total"],
            "monthly_income": [
                {"description": r["label"], "amount": r["amount"]}
                for r in section["income"]["income_items"]
            ],
            "total_income": section["income"]["total_income"],
            "net_saving": section["income"]["net_saving"],
            "assets": [
                {"description": r["description"], "amount": r["amount"], "notes": r.get("notes")}
                for r in section["assets"]["rows"]
            ],
            "total_assets": section["assets"]["total"],
            "dscr": float(section.get("dscr") or 0),
            "bank_statements": bank_statements,
        }

    section = _corporate_finance(apless, applno, dates)
    if section.get("no_data"):
        return {
            "currency": None,
            "period_label": None,
            "balance_sheet": [],
            "profit_loss": [],
            "dscr": 0,
            "bank_statements": bank_statements,
        }

    bs = section["balance_sheet"]
    balance_sheet_rows = []
    for sec in bs["asset_sections"] + bs["liability_sections"]:
        if sec["header"]:
            balance_sheet_rows.append({"label": sec["header"], "period1": None, "period2": None})
        for r in sec["rows"]:
            balance_sheet_rows.append({"label": r["label"], "period1": r["amount_a"], "period2": r["amount_b"]})
        if sec["show_subtotal"]:
            balance_sheet_rows.append({
                "label": f"TOTAL {sec['header']}", "period1": sec["subtotal_a"],
                "period2": sec["subtotal_b"], "is_total": True,
            })

    return {
        "currency": None,
        "period_label": f"{bs.get('period_label_1', '')} / {bs.get('period_label_2', '')}",
        "balance_sheet": balance_sheet_rows,
        "profit_loss": [
            {"label": r["label"], "period1": r["amount"], "is_total": r["bold"]}
            for r in section["profit_loss"]["rows"]
        ],
        "dscr": float(section.get("dscr") or 0),
        "bank_statements": bank_statements,
    }
    
@cam_view_bp.route("/report-cam")
@login_required
def get_report_cam():
    applno = request.args.get("applno", "")
    apless = request.args.get("apless", "")
    if not applno or not apless:
        return jsonify({"error": "Missing applno/apless"}), 400
    try:
        data = _report_cam_core(applno, apless)
        if data is None:
            return jsonify({"error": "Not found"}), 404

        access_level = session.get("accesslevel", "")
        if access_level not in ("CMO", "CMH", "BM"):
            data["credit_scoring"] = _report_cam_credit_scoring(applno)
        else:
            data["credit_scoring"] = None

        return jsonify(data)
    except Exception:
        current_app.logger.exception("Report CAM error")
        return jsonify({"error": "Failed to load data"}), 500

@cam_view_bp.route("/files/download")
@login_required
def download_file():
    key = request.args.get("key", "")
    name = request.args.get("name", "")
    if not key:
        return jsonify({"error": "Missing key"}), 400
    url = _aws_presign(key, name)
    if not url:
        return jsonify({"error": "Failed to generate download URL"}), 500
    return redirect(url)

@cam_view_bp.route("/credit-recommendation")
@login_required
def get_credit_recommendation():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "Missing applno"}), 400

    try:
        row = db.session.execute(
            text(
                "SELECT Strength, Weakness, Tbo FROM CAFCONT_DETAIL WITH (NOLOCK) "
                "WHERE APPL_NO = :applno"
            ),
            {"applno": applno},
        ).mappings().first()

        if not row or not (row["Strength"] or "").strip():
            return jsonify({"has_data": False})

        return jsonify({
            "has_data": True,
            "strength": row["Strength"] or "",
            "weakness": row["Weakness"] or "",
            "tbo": row["Tbo"] or "",
        })

    except Exception:
        current_app.logger.exception("CAM credit recommendation error")
        return jsonify({"error": "Failed to load data"}), 500

CATEGORY_LABELS = {
    'CO': 'KOPERASI',
    'CV': 'CV',
    'FD': 'YAYASAN',
    'PT': 'PT',
}

CATEGORY_DOCUMENT_SECTIONS = {
    'CO': [
        ('corp-structure', 'Susunan Pengurus & Pengawas Koperasi'),
        ('corp-ktp-pengawas', 'KTP a/n Pengawas Penanda Tangan Kontrak'),
        ('corp-siup', 'SIUP'),
        ('corp-nib', 'NIB'),
    ],
    'CV': [
        ('corp-siup', 'SIUP'),
        ('corp-nib', 'NIB'),
    ],
    'FD': [
        ('corp-ktp-pengawas', 'KTP an. Pengawas'),
        ('corp-nib', 'NIB'),
    ],
    'PT': [
        ('corp-siup', 'SIUP'),
        ('corp-nib', 'NIB'),
        ('corp-sk-director', 'Surat Kuasa Asli dari Direktur'),
    ],
}

BPKB_DOCUMENT_SECTIONS = [
    ('corp-ktp-bpkb', 'KTP an. BPKB'),
    ('corp-kk-bpkb', 'Kartu Keluarga an. BPKB'),
    ('corp-other', 'Other'),
]

COMPANY_DOCUMENT_SECTIONS_TOP = [
    ('corp-akta', 'Akta Pendirian'),
    ('corp-sk-akta', 'SK Kemenkumham Akta Pendirian'),
    ('corp-akta-terakhir', 'Akta Perubahan Terakhir'),
    ('corp-sk-akta-terakhir', 'SK Kemenkumham atas Akta Perubahan Terakhir'),
]

COMPANY_DOCUMENT_SECTIONS_BOTTOM = [
    ('corp-npwp', 'NPWP Perusahaan'),
    ('corp-spk', 'SPK'),
]

def _blank(value):
    if value is None:
        return '-'
    value = str(value).strip()
    return value if value else '-'

def format_npwp(npwp):
    if not npwp:
        return '-'
    npwp = str(npwp)
    if len(npwp) < 15:
        return npwp
    return (
        f"{npwp[0:2]}.{npwp[2:5]}.{npwp[5:8]}.{npwp[8:9]}"
        f"-{npwp[9:12]}.{npwp[12:15]}"
    )

def join_nonempty(*values, sep=', '):
    parts = [str(v) for v in values if v not in (None, '')]
    return sep.join(parts) if parts else '-'

def build_address_block(address, city, zipcode, phone, fax, extra_line=None):
    if not address:
        return None
    line = address if not extra_line else f"{address}, {extra_line}"
    line = f"{line}, {join_nonempty(city, zipcode, sep=' ')}"
    contact_parts = []
    if phone:
        contact_parts.append(f"(P) {phone}")
    if fax:
        contact_parts.append(f"(F) {fax}")
    return {
        "address_line": line,
        "contact_line": " - ".join(contact_parts) if contact_parts else '-',
    }

def build_id_card_address(address2, rt, rw, kelurahan2, kecamatan2, city2, zipcode2, phone1, fax1):
    if not address2:
        return None
    extra = f"RT. {rt or '-'}/{rw or '-'}, {join_nonempty(kelurahan2, kecamatan2)}"
    line = f"{address2}, {extra}, {join_nonempty(city2, zipcode2, sep=' ')}"
    contact_parts = []
    if phone1:
        contact_parts.append(f"(P) {phone1}")
    if fax1:
        contact_parts.append(f"(F) {fax1}")
    return {
        "address_line": line,
        "contact_line": " - ".join(contact_parts) if contact_parts else '-',
    }

def format_date(value):
    if value is None:
        return '-'
    try:
        return value.strftime('%d-%m-%Y')
    except AttributeError:
        return str(value)

def lookup_combo_description(cat_value, value):
    if not value:
        return value
    row = db.session.execute(
        text(
            "SELECT DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) "
            "WHERE CAT_VALUE = :cat_value AND [VALUE] = :value"
        ),
        {"cat_value": cat_value, "value": value},
    ).mappings().first()
    return row["DESC_VALUE"] if row else value

@cam_view_bp.route('/corporate-detail')
@login_required
def get_corporate_detail():
    apless = request.args.get('apless')
    applno = request.args.get('applno')

    if not apless:
        return jsonify({"error": "apless is required"}), 400

    try:
        customer = _fetch_customer(apless)
        if customer is None:
            return jsonify({"error": "Customer not found"}), 404

        customer["references"] = _fetch_references(apless)

        doc_files = _fetch_document_files(apless, applno)
        customer["document_groups"] = _build_document_groups_corp(customer.pop("_lessee_cat"), doc_files)
        customer["show_documents"] = any(g["rows"] and any(r["files"] for r in g["rows"]) for g in customer["document_groups"])

        return jsonify(customer)

    except Exception:
        current_app.logger.exception("Corporate detail error (apless=%s)", apless)
        return jsonify({"error": "Failed to load corporate detail"}), 500

def _fetch_customer(apless):
    row = db.session.execute(
        text("""
            SELECT a.LESSEE_NM, a.Lessee_Cat, a.ADDRESS1, a.ADDRESS2, a.CITY2, a.PHONE2, a.ZipCode2, a.Fax2,
                a.ADDRESS3, a.CITY3, a.PHONE3, a.ZipCode3, a.Fax3, a.ADDRESS4, a.CITY4, a.PHONE4, a.ZipCode4, a.Fax4,
                a.Address5, a.City5, a.Phone5, a.ZipCode5, a.Fax5, a.CITY1, a.ZipCode1, a.PHONE1, a.Mobile_phone1,
                a.Mobile_phone2, a.Mobile_phone3, a.OTHER_PHONE1, a.OTHER_PHONE2, a.OTHER_PHONENOTES1, a.OTHER_PHONENOTES2,
                a.EMAIL1, a.EMAIL2, a.NPWP, a.Fax1, a.PLACEBIRTH, a.TGLBIRTH, a.Contact, a.Occupation AS position,
                a.LOB, b.name AS officestatus, c.NAME AS custtype,
                CASE WHEN d.FLGDEL = '1' THEN '-' ELSE d.GrpName END AS GrpName,
                i.MLCI_Desc, mi.Descrip, j.CONFIRM_STS, l.EMERGENCY_NAME, l.EMERGENCY_ADDRESS, l.EMERGENCY_PHONE,
                l.EMERGENCY_RELATION, l.SIUP_NO, l.DOMICILE_NO, l.Address_NPWP, n.KABUPATEN AS Area_CD_NPWP,
                q.Desc_Name AS Kecamatan_NPWP, r.Desc_Name AS Kelurahan_NPWP, l.Zipcode_NPWP, m.Fullname_Without_Title,
                m.BUSINESS_ENTITY, CASE WHEN m.GO_PUBLIC='0' THEN 'No' WHEN m.GO_PUBLIC='1' THEN 'Yes' ELSE '-' END AS GO_PUBLIC,
                m.RELATIONSHIP, o.Desc_Name AS kecamatan2, p.Desc_Name AS kelurahan2, l.RT, l.RW, m.NumberOfEmployee
            FROM CAFLESS a WITH (NOLOCK)
                LEFT JOIN MSTADDRESSSTATUS b WITH (NOLOCK) ON a.Address_Status = b.AddressStatus
                LEFT JOIN MSTLESSEETYPE c WITH (NOLOCK) ON a.Lessee_Cat = c.CUST_TYPE AND c.LESSEE_TP = 'PT'
                LEFT JOIN MstIndustry_lbpp mi WITH (NOLOCK) ON a.INDUS_CODE = mi.MLCI_CODE
                LEFT JOIN CLFGROUP d WITH (NOLOCK) ON a.GrpCode = d.GrpCode
                LEFT JOIN UMFBITYP_lbpp i WITH (NOLOCK) ON a.Cust_Type = i.OJK_Code
                LEFT JOIN MCMOCRSURVEY j WITH (NOLOCK) ON a.APLESS = j.APLESS
                LEFT JOIN CAFLESS_DETAIL_ADDRESS l WITH (NOLOCK) ON a.APLESS = l.APLESS
                LEFT JOIN CAFLESS_DETAIL m WITH (NOLOCK) ON m.APLESS = a.APLESS
                LEFT JOIN UMFAREA n WITH (NOLOCK) ON n.Area_CD = l.Area_CD_NPWP
                LEFT JOIN Mst_Kecamatan o WITH (NOLOCK) ON l.KECAMATAN = o.Kecamatan_CD
                LEFT JOIN Mst_Kelurahan p WITH (NOLOCK) ON l.KELURAHAN = p.Kelurahan_CD
                LEFT JOIN Mst_Kecamatan q WITH (NOLOCK) ON l.Kecamatan_NPWP = q.Kecamatan_CD
                LEFT JOIN Mst_Kelurahan r WITH (NOLOCK) ON l.Kelurahan_NPWP = r.Kelurahan_CD
            WHERE a.APLESS = :apless
        """),
        {"apless": apless},
    ).mappings().first()

    if row is None:
        return None

    lessee_cat = row["Lessee_Cat"]
    relationship = lookup_combo_description('RELATIONSHIP_MLCI', row["RELATIONSHIP"])
    business_entity = lookup_combo_description('BUSINESS_ENTITY', row["BUSINESS_ENTITY"])

    npwp_address = row["Address_NPWP"]
    npwp_address_display = (
        '-' if not npwp_address else
        f"{npwp_address}, {join_nonempty(row['Kelurahan_NPWP'], row['Kecamatan_NPWP'], row['Area_CD_NPWP'])} "
        f"{row['Zipcode_NPWP'] or ''}".strip()
    )

    return {
        "_lessee_cat": lessee_cat,
        "lessee_nm": row["LESSEE_NM"] or '-',
        "idcard_name": row["Fullname_Without_Title"] or '-',
        "cust_type": _blank(row["custtype"]),

        "id_address": build_id_card_address(
            row["ADDRESS2"], row["RT"], row["RW"], row["kelurahan2"], row["kecamatan2"],
            row["CITY2"], row["ZipCode2"], row["PHONE1"], row["Fax1"],
        ),
        "whatsapp": row["Mobile_phone1"] or '-',
        "mobile": join_nonempty(row["Mobile_phone1"], row["Mobile_phone2"], row["Mobile_phone3"]),
        "email": join_nonempty(row["EMAIL1"], row["EMAIL2"]),
        "npwp_formatted": format_npwp(row["NPWP"]),
        "correspondence": build_address_block(
            row["ADDRESS3"], row["CITY3"], row["ZipCode3"], row["PHONE3"], row["Fax3"],
        ),
        "npwp_address": npwp_address_display,

        "additional1": build_address_block(
            row["ADDRESS4"], row["CITY4"], row["ZipCode4"], row["PHONE4"], row["Fax4"],
        ),
        "group_name": _blank(row["GrpName"]),
        "contact": _blank(row["Contact"]),
        "position": _blank(row["position"]),

        "additional2": build_address_block(
            row["Address5"], row["City5"], row["ZipCode5"], row["Phone5"], row["Fax5"],
        ),
        "establishment_place": row["PLACEBIRTH"] or '-',
        "establishment_date": format_date(row["TGLBIRTH"]),
        "line_of_business": _blank(row["LOB"]),
        "industrial_code": row["Descrip"] or '-',

        "other_phone1": row["OTHER_PHONE1"] or '-',
        "other_phone1_notes": row["OTHER_PHONENOTES1"] or '-',
        "other_phone2": row["OTHER_PHONE2"] or '-',
        "other_phone2_notes": row["OTHER_PHONENOTES2"] or '-',
        "bi_customer_type": row["MLCI_Desc"] or '-',
        "number_of_employee": row["NumberOfEmployee"],
        "office_status": _blank(row["officestatus"]),
        "siup_no": row["SIUP_NO"] or '-',
        "domicile_no": row["DOMICILE_NO"] or '-',
        "business_entity": business_entity or '-',
        "go_public": row["GO_PUBLIC"] or '-',
        "relationship": relationship or '-',
        "emergency": {
            "name": row["EMERGENCY_NAME"] or '-',
            "address": row["EMERGENCY_ADDRESS"] or '-',
            "phone": row["EMERGENCY_PHONE"] or '-',
            "relation": row["EMERGENCY_RELATION"] or '-',
        },
    }

def _fetch_references(apless):
    result = db.session.execute(
        text("""
            SELECT ID, REF_NAME, REF_PHONE, REMARK
            FROM CAFREF WITH (NOLOCK)
            WHERE APLESS = :apless
            ORDER BY ID
        """),
        {"apless": apless},
    ).mappings().all()

    return [
        {
            "no": idx,
            "name": r["REF_NAME"] or '-',
            "phone": r["REF_PHONE"] or '-',
            "remark": r["REMARK"] or '-',
        }
        for idx, r in enumerate(result, start=1)
    ]

def _fetch_document_files(apless, applno):
    files_by_type = {}
    if not applno:
        return files_by_type
    result = db.session.execute(
        text("""
            SELECT a.id_customer_document, a.AWSKey, a.file_document, a.DocumentType
            FROM CUSTOMER_DOCUMENT a WITH (NOLOCK)
                LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.appl_no = b.APPL_NO
            WHERE a.doc_type = 'non' AND a.APPL_NO = :applno AND a.APLESS = :apless
                AND a.APLESS IS NOT NULL
            ORDER BY a.DocumentType, a.Upload_Dt DESC
        """),
        {"applno": applno, "apless": apless},
    ).mappings().all()

    for row in result:
        file_name = row["file_document"]
        if not file_name or file_name == '-':
            continue
        files_by_type.setdefault(row["DocumentType"] or "", []).append({
            "id": row["id_customer_document"],
            "name": file_name,
            "download_url": _aws_presign(row["AWSKey"], file_name),
        })

    return files_by_type

def _doc_row(key, label, files_by_type):
    return {"key": key, "label": label, "files": files_by_type.get(key, [])}

def _build_document_groups_corp(lessee_cat, files_by_type):
    groups = []

    category_sections = CATEGORY_DOCUMENT_SECTIONS.get(lessee_cat, [])
    if category_sections:
        groups.append({
            "header": f"Customer Type: {CATEGORY_LABELS.get(lessee_cat, lessee_cat)}",
            "rows": [_doc_row(key, label, files_by_type) for key, label in category_sections],
        })

    groups.append({
        "header": "Dokumen BPKB",
        "rows": [_doc_row(key, label, files_by_type) for key, label in BPKB_DOCUMENT_SECTIONS],
    })

    company_rows = [_doc_row(key, label, files_by_type) for key, label in COMPANY_DOCUMENT_SECTIONS_TOP]
    ktp_pengurus_files = []
    for doc_type, files in files_by_type.items():
        if doc_type.startswith('corp-ocr-ktp_') or doc_type.startswith('wna-corp-board_'):
            ktp_pengurus_files.extend(files)
    company_rows.append({
        "key": "ktp-pengurus",
        "label": "KTP Pengurus pada Akta Perubahan Terakhir",
        "files": ktp_pengurus_files,
    })

    company_rows += [_doc_row(key, label, files_by_type) for key, label in COMPANY_DOCUMENT_SECTIONS_BOTTOM]
    groups.append({"header": "Dokumen Data Perusahaan", "rows": company_rows})

    return groups

ORG_TYPE_BY_CATEGORY = {
    'CO': 'KOPERASI',
    'CV': 'CV',
    'FD': 'YAYASAN',
    'PT': 'PT',
}

def format_number(value):
    if value is None:
        return '-'
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return str(value)

def _lookup_position_desc(os_code, pos_deedno):
    if not pos_deedno:
        return None
    row = db.session.execute(
        text("SELECT [DESC] FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE=:os_code AND ID_OS_POSITION=:pos"),
        {"os_code": os_code, "pos": pos_deedno},
    ).mappings().first()
    return row["DESC"] if row and row["DESC"] else None

def _lookup_or_literal(os_code, pos_deedno):
    return _lookup_position_desc(os_code, pos_deedno) or pos_deedno or '-'

def _pt_position(os_code, pos_deedno):
    if pos_deedno and str(pos_deedno).isdigit():
        return _lookup_position_desc(os_code, pos_deedno) or str(pos_deedno)
    return pos_deedno or 'Share Holder'

def _lookup_certificate_desc(cust_type, certificate_id):
    if not certificate_id:
        return certificate_id or '-'
    row = db.session.execute(
        text("SELECT [DESC] FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE=:ct AND ID_OS_CERTIFICATE=:cid"),
        {"ct": cust_type, "cid": certificate_id},
    ).mappings().first()
    return (row["DESC"] if row and row["DESC"] else None) or certificate_id or '-'

def _resolve_period(apless, applno):
    row = db.session.execute(
        text("""
            SELECT YEAR(CREATE_DATE) AS YEARS, MONTH(CREATE_DATE) AS MONTHS
            FROM CAFCONT WITH (NOLOCK) WHERE APLESS=:apless AND APPL_NO=:applno
        """),
        {"apless": apless, "applno": applno},
    ).mappings().first()

    if row and row["YEARS"]:
        dates = f"{row['YEARS']}{int(row['MONTHS']):02d}"
    else:
        dates = datetime.now().strftime('%Y%m')

    period_row = db.session.execute(
        text("""
            SELECT TOP 1 PERIOD FROM CAFORGSTRUCT WITH (NOLOCK)
            WHERE APLESS=:apless AND PERIOD <= :dates
            GROUP BY PERIOD ORDER BY PERIOD DESC
        """),
        {"apless": apless, "dates": dates},
    ).mappings().first()

    return period_row["PERIOD"] if period_row else None

def _fetch_signers(apless, period, os_codes, position_resolver):
    seen = set()
    rows = []
    for os_code in os_codes:
        result = db.session.execute(
            text("""
                SELECT MANAGEMENT_NM, POS_DEEDNO FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
                WHERE APLESS=:apless AND OS_CODE=:os_code AND SIGNER='1' AND PERIOD=:period
            """),
            {"apless": apless, "os_code": os_code, "period": period},
        ).mappings().all()
        for r in result:
            name = r["MANAGEMENT_NM"]
            if not name or name in seen:
                continue
            seen.add(name)
            rows.append([name, position_resolver(os_code, r["POS_DEEDNO"])])
    return rows

def _fetch_board_rows(apless, period, os_code, lookup_position):
    result = db.session.execute(
        text("""
            SELECT MANAGEMENT_NM, POS_DEEDNO, OWNER FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
            WHERE APLESS=:apless AND PERIOD=:period AND OS_CODE=:os_code
        """),
        {"apless": apless, "period": period, "os_code": os_code},
    ).mappings().all()
    rows = []
    for idx, r in enumerate(result, start=1):
        if lookup_position:
            label = _lookup_or_literal(os_code, r["POS_DEEDNO"])
        else:
            label = r["POS_DEEDNO"] or '-'
        rows.append([str(idx), r["MANAGEMENT_NM"] or '-', label, 'Yes' if r["OWNER"] == '1' else 'No'])
    return rows

def _fetch_deeds(apless, period, os_code, cust_type, pt_style=False):
    if pt_style:
        query = """
            SELECT MANAGEMENT_NM AS STATE_NO, POS_DEEDNO, DATE_OF_DEED, NOTARY_NM, CERTIFICATE
            FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
            WHERE APLESS=:apless AND PERIOD=:period AND OS_CODE=:os_code
        """
    else:
        query = """
            SELECT POS_DEEDNO, NOTARY_NM, CERTIFICATE,
                FORMAT(CAST(DATE_OF_DEED AS DATE), 'dd-MM-yyyy') AS DATE_OF_DEED
            FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
            WHERE APLESS=:apless AND PERIOD=:period AND OS_CODE=:os_code
        """
    result = db.session.execute(text(query), {"apless": apless, "period": period, "os_code": os_code}).mappings().all()
    rows = []
    for idx, r in enumerate(result, start=1):
        certificate = _lookup_certificate_desc(cust_type, r["CERTIFICATE"])
        if pt_style:
            rows.append([
                str(idx), r["STATE_NO"] or '-', r["POS_DEEDNO"] or '-',
                format_date(r["DATE_OF_DEED"]), r["NOTARY_NM"] or '-', certificate,
            ])
        else:
            rows.append([
                str(idx), r["POS_DEEDNO"] or '-', r["DATE_OF_DEED"] or '-',
                r["NOTARY_NM"] or '-', certificate,
            ])
    return rows

def _fetch_management_detail_generic(apless, period, os_code_like, skip_blank_names=False):
    result = db.session.execute(
        text("""
            SELECT DISTINCT ID_DETAIL, MANAGEMENT_NM, ID_CARD, ADDRESS,
                CASE WHEN CITY='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY END AS CITY,
                r.Desc_Name AS Kecamatan, s.Desc_Name AS Kelurahan
            FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK)
                LEFT JOIN Mst_Kecamatan r WITH (NOLOCK) ON a.KECAMATAN = r.Kecamatan_CD
                LEFT JOIN Mst_Kelurahan s WITH (NOLOCK) ON a.KELURAHAN = s.Kelurahan_CD
            WHERE APLESS=:apless AND OS_CODE LIKE :os_like AND PERIOD=:period
            ORDER BY ID_DETAIL ASC
        """),
        {"apless": apless, "os_like": os_code_like, "period": period},
    ).mappings().all()

    rows = []
    for idx, r in enumerate(result, start=1):
        name = r["MANAGEMENT_NM"]
        if skip_blank_names and not name:
            continue
        rows.append({
            "no": idx,
            "name": name or '-',
            "id_card": r["ID_CARD"] or '-',
            "address": join_nonempty(r["ADDRESS"], r["Kelurahan"], r["Kecamatan"], r["CITY"]),
            "detail_params": {"management_nm": name, "share_status": ""} if name else None,
        })
    return rows

def _fetch_documents(apless, applno, org_type):
    if not applno:
        return []
    result = db.session.execute(
        text("""
            SELECT id_customer_document, AWSKey, a.file_document, DocumentType
            FROM CUSTOMER_DOCUMENT a WITH (NOLOCK)
                LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.appl_no = b.APPL_NO
            WHERE a.organization_type=:org_type AND a.doc_type='non' AND a.APPL_NO=:applno
                AND a.APLESS=:apless AND a.APLESS IS NOT NULL
            ORDER BY DocumentType, Upload_Dt DESC
        """),
        {"org_type": org_type, "applno": applno, "apless": apless},
    ).mappings().all()

    files = []
    for row in result:
        file_name = row["file_document"]
        doc_type = row["DocumentType"] or ''
        if not file_name or file_name == '-':
            continue
        if not (doc_type.startswith('corp-ocr-ktp_') or doc_type.startswith('wna-corp-board_')):
            continue
        files.append({
            "id": row["id_customer_document"],
            "name": file_name,
            "download_url": _aws_presign(row["AWSKey"], file_name),
        })
    return files

def _build_co_blocks(apless, period, lessee_nm):
    signers = _fetch_signers(apless, period, ['CO01', 'CO02'], _lookup_or_literal)
    bom = _fetch_board_rows(apless, period, 'CO01', lookup_position=True)
    bos = _fetch_board_rows(apless, period, 'CO02', lookup_position=False)
    deeds = _fetch_deeds(apless, period, 'CO03', cust_type='CO')

    signer_row = db.session.execute(
        text("""
            SELECT a.OTHER_SIGNER, a.PIC, b.ID_OS_SIGNER, b.[DESC] AS contract_signer
            FROM CAFORGSTRUCT a WITH (NOLOCK)
                LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER
            WHERE APLESS=:apless AND PERIOD=:period AND b.CUST_TYPE='CO'
        """),
        {"apless": apless, "period": period},
    ).mappings().first() or {}
    contract_signer_tampil = (
        signer_row.get("OTHER_SIGNER") if signer_row.get("ID_OS_SIGNER") == '14' else signer_row.get("contract_signer")
    ) or '-'
    pic = signer_row.get("PIC") or contract_signer_tampil or '-'

    return [
        {"type": "table", "title": "A. COMPOSITION OF BOARD OF MANAGEMENT",
         "columns": ["No.", "Name in ID Card", "Position", "Owner"], "rows": bom},
        {"type": "table", "title": "B. COMPOSITION OF BOARD OF SUPERVISOR",
         "columns": ["No.", "Name in ID Card", "Position", "Owner"], "rows": bos},
        {"type": "table", "title": "C. DEED OF ESTABLISHMENT",
         "columns": ["No.", "Deed No.", "Date of Deed", "Notary Name", "Certificate of Ministry of Cooperative"], "rows": deeds},
        {"type": "text", "title": "D. CONTRACT SIGN FOLLOW THE ARTICLE: BOARD OF MANAGEMENT ROLES AND AUTHORITY", "content": contract_signer_tampil},
        {"type": "text", "title": "E. PERSON IN CHARGE TO SIGN CONTRACT", "content": pic},
        {"type": "table", "title": "SIGNER", "columns": ["Name", "Position"], "rows": signers},
        {"type": "management_detail", "title": "F. MANAGEMENT DETAIL INFORMATION",
         "columns": ["No.", "Name in ID Card", "ID Card", "Address", "Detail"],
         "rows": _fetch_management_detail_generic(apless, period, 'CO%', skip_blank_names=True)},
    ]

def _build_cv_blocks(apless, period, lessee_nm):
    signers = _fetch_signers(apless, period, ['CV01', 'CV02'], _lookup_or_literal)
    active_partner = _fetch_board_rows(apless, period, 'CV01', lookup_position=True)
    limited_partner = _fetch_board_rows(apless, period, 'CV02', lookup_position=True)
    deeds = _fetch_deeds(apless, period, 'CV03', cust_type='CV')

    signer_row = db.session.execute(
        text("""
            SELECT a.OTHER_SIGNER, a.PIC, b.ID_OS_SIGNER, b.[DESC] AS contract_signer
            FROM CAFORGSTRUCT a WITH (NOLOCK)
            LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER
            WHERE APLESS=:apless AND PERIOD=:period AND b.CUST_TYPE='CV'
        """),
        {"apless": apless, "period": period},
    ).mappings().first() or {}
    contract_signer_tampil = (
        signer_row.get("OTHER_SIGNER") if signer_row.get("ID_OS_SIGNER") == '10' else signer_row.get("contract_signer")
    ) or '-'
    pic = signer_row.get("PIC") or contract_signer_tampil or '-'

    return [
        {"type": "table", "title": "A. COMPOSITION ACTIVE PARTNER & LIMITED PARTNER",
         "columns": ["No.", "Name in ID Card", "Active Partner", "Owner"], "rows": active_partner},
        {"type": "table", "title": None,
         "columns": ["No.", "Name in ID Card", "Limited Partner", "Owner"], "rows": limited_partner},
        {"type": "table", "title": "B. DEED OF ESTABLISHMENT",
         "columns": ["No.", "Deed No.", "Date of Deed", "Notary Name", "Status Deed"], "rows": deeds},
        {"type": "text", "title": "C. CONTRACT SIGNER ACCORDING DEED OF ESTABLISHMENT THE ARTICLE: BOARD OF DIRECTOR'S ROLES AND AUTHORITY", "content": contract_signer_tampil},
        {"type": "text", "title": "D. PERSON IN CHARGE TO SIGN CONTRACT", "content": pic},
        {"type": "table", "title": "SIGNER", "columns": ["Name", "Position"], "rows": signers},
        {"type": "management_detail", "title": "E. MANAGEMENT DETAIL INFORMATION",
         "columns": ["No.", "Name in ID Card", "ID Card", "Address", "Detail"],
         "rows": _fetch_management_detail_generic(apless, period, 'CV%', skip_blank_names=True)},
    ]

def _build_fd_blocks(apless, period, lessee_nm):
    signers = _fetch_signers(apless, period, ['FD01', 'FD02', 'FD03'], _lookup_or_literal)
    foundation = _fetch_board_rows(apless, period, 'FD01', lookup_position=False)
    bom = _fetch_board_rows(apless, period, 'FD02', lookup_position=True)
    bos = _fetch_board_rows(apless, period, 'FD03', lookup_position=False)
    deeds = _fetch_deeds(apless, period, 'FD04', cust_type='FD')

    signer_row = db.session.execute(
        text("""
            SELECT a.OTHER_SIGNER, a.PIC, b.ID_OS_SIGNER, b.[DESC] AS contract_signer
            FROM CAFORGSTRUCT a WITH (NOLOCK)
                LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER
            WHERE APLESS=:apless AND PERIOD=:period AND b.CUST_TYPE='FD'
        """),
        {"apless": apless, "period": period},
    ).mappings().first() or {}
    contract_signer_tampil = (
        signer_row.get("OTHER_SIGNER") if signer_row.get("ID_OS_SIGNER") == '16' else signer_row.get("contract_signer")
    ) or '-'
    pic = signer_row.get("PIC") or contract_signer_tampil or '-'

    return [
        {"type": "table", "title": "A. COMPOSITION OF FOSTERING FOUNDATION",
         "columns": ["No.", "Name in ID Card", "Position", "Owner"], "rows": foundation},
        {"type": "table", "title": "B. COMPOSITION OF BOARD OF MANAGEMENT",
         "columns": ["No.", "Name in ID Card", "Position", "Owner"], "rows": bom},
        {"type": "table", "title": "C. COMPOSITION OF BOARD OF SUPERVISOR",
         "columns": ["No.", "Name in ID Card", "Position", "Owner"], "rows": bos},
        {"type": "table", "title": "D. DEED OF ESTABLISHMENT",
         "columns": ["No.", "Deed No.", "Date of Deed", "Notary Name", "Certificate of Ministry of Cooperative"], "rows": deeds},
        {"type": "text", "title": "E. CONTRACT SIGN FOLLOW THE ARTICLE: BOARD OF MANAGEMENT ROLES AND AUTHORITY", "content": contract_signer_tampil},
        {"type": "text", "title": "F. PERSON IN CHARGE TO SIGN CONTRACT", "content": pic},
        {"type": "table", "title": "SIGNER", "columns": ["Name", "Position"], "rows": signers},
        {"type": "management_detail", "title": "G. MANAGEMENT DETAIL INFORMATION",
         "columns": ["No.", "Name in ID Card", "ID Card", "Address", "Detail"],
         "rows": _fetch_management_detail_generic(apless, period, 'FD%', skip_blank_names=True)},
    ]

def _build_pt_blocks(apless, period, lessee_nm):
    cap_row = db.session.execute(
        text("""
            SELECT a.AUTHORIZED_CAPITAL, a.PAID_IN_CAPITAL, a.OTHER_SIGNER, a.PIC,
                b.ID_OS_SIGNER, b.[DESC] AS contract_signer
            FROM CAFORGSTRUCT a WITH (NOLOCK)
            LEFT JOIN MSTOS_SIGNER b WITH (NOLOCK) ON a.CONTRACT_SIGNER=b.ID_OS_SIGNER
            WHERE a.APLESS=:apless AND a.PERIOD=:period AND b.CUST_TYPE='PT'
        """),
        {"apless": apless, "period": period},
    ).mappings().first() or {}
    contract_signer_tampil = (
        cap_row.get("OTHER_SIGNER") if cap_row.get("ID_OS_SIGNER") == '5' else cap_row.get("contract_signer")
    ) or '-'
    pic = cap_row.get("PIC") or contract_signer_tampil or '-'

    signers = _fetch_signers(apless, period, ['PT01', 'PT02', 'PT03'], _pt_position)

    sh_result = db.session.execute(
        text("""
            SELECT a.MANAGEMENT_NM, a.TOTOFSHARES, a.NOMOFSHARES, b.DESC_VALUE
            FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK)
                LEFT JOIN MSTCOMBO b WITH (NOLOCK) ON b.[VALUE]=a.SHAREHOLDER_STATUS AND b.CAT_VALUE='SHAREHOLDER_STATUS'
            WHERE a.APLESS=:apless AND a.PERIOD=:period AND a.OS_CODE='PT01'
        """),
        {"apless": apless, "period": period},
    ).mappings().all()
    shareholders = [
        [str(i), r["MANAGEMENT_NM"] or '-', r["DESC_VALUE"] or '-', r["TOTOFSHARES"] or '-', format_number(r["NOMOFSHARES"])]
        for i, r in enumerate(sh_result, start=1)
    ]

    bod = _fetch_board_rows_pt(apless, period, 'PT02')
    boc = _fetch_board_rows_pt(apless, period, 'PT03')
    deeds = _fetch_deeds(apless, period, 'PT04', cust_type='PT', pt_style=True)

    blocks = [
        {"type": "key_value", "title": "A. CAPITAL", "rows": [
            ["Authorized Capital", format_number(cap_row.get("AUTHORIZED_CAPITAL"))],
            ["Paid-In Capital", format_number(cap_row.get("PAID_IN_CAPITAL"))],
        ]},
        {"type": "table", "title": "B. SHAREHOLDER",
         "columns": ["No.", "Name in ID Card / Akta", "Status", "Total of Shares (Pieces)", "Nominal of Shares (Rp.)"],
         "rows": shareholders},
        {"type": "table", "title": "C. COMPOSITION THE BOARD OF DIRECTORS (BOD) & BOARD OF COMMISSIONERS (BOC)",
         "columns": ["No.", "Name in ID Card", "BOD", "Owner"], "rows": bod},
        {"type": "table", "title": None,
         "columns": ["No.", "Name in ID Card", "BOC", "Owner"], "rows": boc},
        {"type": "table", "title": "D. DEED OF ESTABLISHMENT",
         "columns": ["No.", "State Gazette No.", "Deed No.", "Date of Deed / State Gazette", "Notary Name",
                     "Certificate of Ministry of Law & Human Rights"], "rows": deeds},
        {"type": "text", "title": "E. CONTRACT SIGNER ACCORDING DEED OF ESTABLISHMENT THE ARTICLE: BOARD OF DIRECTOR'S ROLES AND AUTHORITY", "content": contract_signer_tampil},
        {"type": "text", "title": "F. PERSON IN CHARGE TO SIGN CONTRACT", "content": pic},
        {"type": "table", "title": "SIGNER", "columns": ["Name", "Position"], "rows": signers},
        {"type": "management_detail", "title": "G. MANAGEMENT DETAIL INFORMATION",
         "columns": ["No.", "Name in ID Card / Akta", "ID Card", "Address in ID Card / SK. Domisili", "Detail"],
         "rows": _fetch_pt_management_detail(apless, period)},
    ]
    return blocks

def _fetch_board_rows_pt(apless, period, os_code):
    result = db.session.execute(
        text("""
            SELECT MANAGEMENT_NM, POS_DEEDNO, OWNER FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
            WHERE APLESS=:apless AND PERIOD=:period AND OS_CODE=:os_code
        """),
        {"apless": apless, "period": period, "os_code": os_code},
    ).mappings().all()
    rows = []
    for idx, r in enumerate(result, start=1):
        label = _pt_position(os_code, r["POS_DEEDNO"])
        rows.append([str(idx), r["MANAGEMENT_NM"] or '-', label, 'Yes' if r["OWNER"] == '1' else 'No'])
    return rows

def _fetch_pt_management_detail(apless, period):
    result = db.session.execute(
        text("""
            SELECT MIN(ID_DETAIL) AS ID_DETAIL, MANAGEMENT_NM, name, PASSPORTNO, CITIZEN,
                ID_CARD, [ADDRESS], CASE WHEN CITY='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY END AS CITY,
                r.Desc_name AS kecamatan, s.Desc_name AS kelurahan
            FROM CAFORGSTRUCT_DETAIL a WITH (NOLOCK)
                LEFT JOIN Mst_Kecamatan r WITH (NOLOCK) ON a.KECAMATAN = r.Kecamatan_CD
                LEFT JOIN Mst_Kelurahan s WITH (NOLOCK) ON a.KELURAHAN = s.Kelurahan_CD
            WHERE APLESS=:apless AND OS_CODE IN ('PT01','PT02','PT03') AND PERIOD=:period
            GROUP BY MANAGEMENT_NM, name, PASSPORTNO, CITIZEN, ID_CARD, [ADDRESS], CITY, r.Desc_name, s.Desc_name
            ORDER BY MIN(ID_DETAIL) ASC
        """),
        {"apless": apless, "period": period},
    ).mappings().all()

    rows = []
    for idx, r in enumerate(result, start=1):
        status_row = db.session.execute(
            text("SELECT TOP 1 SHAREHOLDER_STATUS, NPWP FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK) WHERE APLESS=:apless AND MANAGEMENT_NM=:nm AND PERIOD=:period"),
            {"apless": apless, "nm": r["MANAGEMENT_NM"], "period": period},
        ).mappings().first() or {}
        share_status = status_row.get("SHAREHOLDER_STATUS")

        if share_status == '1':
            id_card = status_row.get("NPWP") or '-'
        elif share_status != '1' and r["CITIZEN"] == 'WNA':
            id_card = r["PASSPORTNO"] or '-'
        else:
            id_card = r["ID_CARD"] or '-'

        rows.append({
            "no": idx,
            "name": r["MANAGEMENT_NM"] or '-',
            "id_card": id_card,
            "address": join_nonempty(r["ADDRESS"], r["kelurahan"], r["kecamatan"], r["CITY"]),
            "detail_params": (
                None if share_status == '3' else
                {"management_nm": r["MANAGEMENT_NM"], "share_status": share_status or ""}
            ),
        })
    return rows

BLOCK_BUILDERS = {
    'CO': _build_co_blocks,
    'CV': _build_cv_blocks,
    'FD': _build_fd_blocks,
    'PT': _build_pt_blocks,
}

@cam_view_bp.route('/business-profile')
@login_required
def get_business_profile():
    apless = request.args.get('apless')
    applno = request.args.get('applno')

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    try:
        lessee_row = db.session.execute(
            text("SELECT a.Lessee_Cat, a.LESSEE_NM FROM CAFLESS a WITH (NOLOCK) WHERE a.APLESS=:apless"),
            {"apless": apless},
        ).mappings().first()
        if lessee_row is None:
            return jsonify({"error": "Customer not found"}), 404

        lessee_cat = lessee_row["Lessee_Cat"]
        lessee_nm = lessee_row["LESSEE_NM"]

        period = _resolve_period(apless, applno)
        if not period:
            return jsonify({"error": "No organization structure data available for this period."}), 404

        builder = BLOCK_BUILDERS.get(lessee_cat)
        if builder is None:
            return jsonify({"error": f"Unsupported lessee category: {lessee_cat}"}), 400

        blocks = builder(apless, period, lessee_nm)

        doc_files = _fetch_documents(apless, applno, ORG_TYPE_BY_CATEGORY.get(lessee_cat, ''))
        blocks.append({"type": "documents", "title": "MANAGEMENT DETAIL FILES", "rows": doc_files})

        return jsonify({
            "lessee_cat": lessee_cat,
            "lessee_nm": lessee_nm or '-',
            "period": period,
            "blocks": blocks,
        })

    except Exception:
        current_app.logger.exception("Business profile error (apless=%s, applno=%s)", apless, applno)
        return jsonify({"error": "Failed to load business profile"}), 500

@cam_view_bp.route('/management-detail')
@login_required
def get_management_detail():
    apless = request.args.get('apless')
    period = request.args.get('period')
    management_nm = request.args.get('management_nm')
    share_status = request.args.get('share_status', '')

    if not apless or not period or not management_nm:
        return jsonify({"error": "apless, period, and management_nm are required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT DISTINCT MANAGEMENT_NM, ID_CARD, ADDRESS,
                    CASE WHEN CITY='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY END AS CITY,
                    cod.name, cod.gender, cod.PASSPORTNO, cod.CITIZEN, cod.NATIONALITY,
                    mc.Name AS NationalityName,
                    ua.Propinsi, ua.Kabupaten, ue.Propinsi AS PropinsiNPWP, ue.Kabupaten AS KabupatenNPWP,
                    NAME_NPWP, ADD_NPWP,
                    CASE WHEN CITY_NPWP='9999' THEN 'Di Luar Wilayah Indonesia' ELSE CITY_NPWP END AS CITY_NPWP,
                    kc.Desc_Name AS Kecamatan, kl.Desc_Name AS Kelurahan,
                    kcn.Desc_Name AS KecamatanNPWP, kln.Desc_Name AS KelurahanNPWP,
                    PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
                    PostCode_NPWP, MobilePhone, Email
                FROM CAFORGSTRUCT_DETAIL cod WITH (NOLOCK)
                    LEFT JOIN UMFAREA ua WITH (NOLOCK) ON ua.KABUPATEN = cod.CITY
                    LEFT JOIN UMFAREA ue WITH (NOLOCK) ON ue.KABUPATEN = cod.CITY_NPWP
                    LEFT JOIN Mst_Kecamatan kc WITH (NOLOCK) ON cod.KECAMATAN = kc.Kecamatan_CD
                    LEFT JOIN Mst_Kelurahan kl WITH (NOLOCK) ON cod.KELURAHAN = kl.Kelurahan_CD
                    LEFT JOIN Mst_Kecamatan kcn WITH (NOLOCK) ON cod.KECAMATAN_NPWP = kcn.Kecamatan_CD
                    LEFT JOIN Mst_Kelurahan kln WITH (NOLOCK) ON cod.KELURAHAN_NPWP = kln.Kelurahan_CD
                    LEFT JOIN Mst_Country mc WITH (NOLOCK) ON mc.ID2digit = cod.NATIONALITY
                WHERE cod.APLESS=:apless AND cod.PERIOD=:period AND cod.MANAGEMENT_NM=:nm
            """),
            {"apless": apless, "period": period, "nm": management_nm},
        ).mappings().first()

        if row is None:
            return jsonify({"error": "Detail not found"}), 404

        raw_no_expire = row["NoExpireDate"]
        is_no_expire = raw_no_expire in (1, '1', True)
        validity_type = 'No Expire Date' if is_no_expire else 'Certain Period'
        validity_until = None if is_no_expire else format_date(row["ValidityCertainPeriod"])

        area = join_nonempty(row["Propinsi"], row["Kabupaten"], sep=' - ')
        area_npwp = join_nonempty(row["PropinsiNPWP"], row["KabupatenNPWP"], sep=' - ')

        payload = {"management_nm": management_nm, "share_status": share_status}

        if share_status == '1':
            payload["entity"] = {
                "name_in_akta": row["MANAGEMENT_NM"] or '-',
                "name_in_npwp": row["NAME_NPWP"] or '-',
                "name_without_title": row["name"] or '-',
                "establishment_place": row["PlaceOfBirth"] or '-',
                "establishment_date": format_date(row["DateOfBirth"]),
                "address": row["ADDRESS"] or '-',
                "area": area,
                "province": row["Propinsi"] or '-',
                "city": row["CITY"] or '-',
                "kecamatan": row["Kecamatan"] or '-',
                "kelurahan": row["Kelurahan"] or '-',
                "id_type": row["IDType"] or 'NPWP',
                "npwp_formatted": format_npwp(row["ID_CARD"]),
                "validity_type": validity_type,
                "validity_until": validity_until,
                "address_npwp": row["ADD_NPWP"] or '-',
                "area_npwp": area_npwp,
                "province_npwp": row["PropinsiNPWP"] or '-',
                "city_npwp": row["CITY_NPWP"] or '-',
                "kecamatan_npwp": row["KecamatanNPWP"] or '-',
                "kelurahan_npwp": row["KelurahanNPWP"] or '-',
                "postcode_npwp": row["PostCode_NPWP"] or '-',
                "mobile_phone": row["MobilePhone"] or '-',
                "email": row["Email"] or '-',
            }
        else:
            payload["individual"] = {
                "name_in_id_card": row["MANAGEMENT_NM"] or '-',
                "name_without_title": row["name"] or '-',
                "gender": 'Male' if row["gender"] == 'M' else ('Female' if row["gender"] == 'F' else '-'),
                "place_of_birth": row["PlaceOfBirth"] or '-',
                "date_of_birth": format_date(row["DateOfBirth"]),
                "address": row["ADDRESS"] or '-',
                "area": area,
                "province": row["Propinsi"] or '-',
                "city": row["CITY"] or '-',
                "kecamatan": row["Kecamatan"] or '-',
                "kelurahan": row["Kelurahan"] or '-',
                "postcode": row["PostCode"] or '-',
                "mobile_phone": row["MobilePhone"] or '-',
                "email": row["Email"] or '-',
                "citizenship": row["CITIZEN"] or '-',
                "nationality": row["NationalityName"] or row["NATIONALITY"] or '-',
                "id_type": row["IDType"] or ('Paspor' if row["CITIZEN"] == 'WNA' else 'KTP'),
                "id_card_no": row["ID_CARD"] or '-',
                "validity_type": validity_type,
                "validity_until": validity_until,
                "passport_no": row["PASSPORTNO"] or '-',
            }

        return jsonify(payload)

    except Exception:
        current_app.logger.exception("Management detail error (apless=%s, nm=%s)", apless, management_nm)
        return jsonify({"error": "Failed to load management detail"}), 500