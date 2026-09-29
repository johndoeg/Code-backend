
from app import db
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import _aws_presign

corporate_detail_bp = Blueprint('corporate_detail', __name__, url_prefix='/CAM/CorporteDetail')

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
        f"-{npwp[9:12]}.{npwp[12:16]}"
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

@corporate_detail_bp.route('/corporate-detail')
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
        customer["document_groups"] = _build_document_groups(customer.pop("_lessee_cat"), doc_files)
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
    ).mappings()

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
    ).mappings()

    for row in result:
        file_name = row["file_document"]
        if not file_name or file_name == '-':
            continue
        files_by_type.setdefault(row["DocumentType"], []).append({
            "id": row["id_customer_document"],
            "name": file_name,
            "download_url": _aws_presign(row["AWSKey"], file_name),
        })

    return files_by_type

def _doc_row(key, label, files_by_type):
    return {"key": key, "label": label, "files": files_by_type.get(key, [])}

def _build_document_groups(lessee_cat, files_by_type):
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