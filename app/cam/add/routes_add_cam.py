import re

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import copy_object, _aws_presign
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text

cam_bp = Blueprint('cam', __name__, url_prefix='/CAM')

_USED_ONLY_FIN_TYPES = ('S', 'D', 'M', 'W')
_CONTRACT_TYPE_FIN_TYPES = ('D', 'M', 'W')

def _truthy_bit(value) -> bool:
    return value not in (None, "", 0, "0", False)

def _clean_db_value(value):
    if isinstance(value, str) and value.strip().upper() == "NULL":
        return None
    return value

def _clean_row(mapping) -> dict:
    return {k: _clean_db_value(v) for k, v in dict(mapping).items()}

_MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

def _fmt_display_date(value) -> str:
    if not value:
        return ""
    return f"{value.day:02d}-{_MONTHS_SHORT[value.month - 1]}-{value.year}"

_WNI_ID_DOC_TYPES = ("cust-ktp", "cust-spouse-ktp", "cust-wna-spouse-ktp")
_WNA_ID_DOC_TYPES = ("cust-kitas", "cust-kitap", "cust-spouse-kitas", "cust-spouse-kitap")

def _fetch_identity_documents(prechecking_id, citizen: str) -> list:

    if not prechecking_id:
        return []

    doc_types = _WNA_ID_DOC_TYPES if (citizen or "").strip().upper() == "WNA" else _WNI_ID_DOC_TYPES

    placeholders = ", ".join(f":dtype_{i}" for i in range(len(doc_types)))
    params = {"pid": prechecking_id}
    params.update({f"dtype_{i}": t for i, t in enumerate(doc_types)})

    rows = db.session.execute(
        text(f"""
            SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT WITH (NOLOCK)
            WHERE Prechecking_Id = :pid
                AND DocumentType IN ({placeholders})
            ORDER BY DocumentType, CreatedDate DESC
        """),
        params,
    ).fetchall()

    return [
        {
            "id":       r.CustomerDocumentId,
            "name":     r.DocumentName,
            "type":     r.DocumentType,
            "key":      r.AWSKey,
            "view_url": _aws_presign(r.AWSKey, r.DocumentName) if r.AWSKey else None,
        }
        for r in rows
    ]

_RATE_FIELD_MAP = {
    "idCardNo": "NIK", "name": "Nama", "placeOfBirth": "Tempat_Lahir",
    "dateOfBirth": "Tgl_Lahir", "gender": "Jenis_Kelamin", "bloodType": "Golongan_Darah",
    "address": "Alamat", "rt": "RT", "rw": "RW", "subdistrict": "Kelurahan",
    "district": "Kecamatan", "city": "Kota", "province": "Provinsi",
    "religion": "Agama", "job": "Pekerjaan",
}

_DUKCAPIL_FIELD_MAP = {
    "idCardNo": "NIK", "name": "Nama", "placeOfBirth": "Tempat_Lahir",
    "dateOfBirth": "Tgl_Lahir", "gender": "Jenis_Kelamin", "address": "Alamat",
    "rt": "RT", "rw": "RW", "subdistrict": "Kelurahan", "district": "Kecamatan",
    "city": "Kota", "province": "Provinsi", "job": "Pekerjaan",
}

_OCR_SELECT_COLUMNS = """
    Id,
    Prechecking_Id,
    OCR_For,
    Citizen,
    Id_Type,
    NIK,
    Nama,
    Tempat_Lahir,
    Tgl_Lahir,
    Jenis_Kelamin,
    Golongan_Darah,
    Alamat,
    RT,
    RW,
    Kelurahan,
    Kecamatan,
    Kota,
    Provinsi,
    Agama,
    Pekerjaan,
    Status_Perkawinan,
    Kewarnegaraan,
    Foto,
    Tanda_Tangan,
    UpdatedDate
"""

def _ocr_row_to_dict(row: dict) -> dict:
    tgl_lahir = row.get("Tgl_Lahir")
    return {
        "id": row.get("Id"),
        "nik": row.get("NIK") or "",
        "nama": row.get("Nama") or "",
        "tempatLahir": row.get("Tempat_Lahir") or "",
        "tglLahir": tgl_lahir.strftime("%d-%m-%Y") if tgl_lahir else "",
        "jenisKelamin": row.get("Jenis_Kelamin") or "",
        "golonganDarah": row.get("Golongan_Darah") or "",
        "alamat": row.get("Alamat") or "",
        "rtRw": f"{row.get('RT') or ''} / {row.get('RW') or ''}".strip(" /"),
        "kelurahan": row.get("Kelurahan") or "",
        "kecamatan": row.get("Kecamatan") or "",
        "kota": row.get("Kota") or "",
        "provinsi": row.get("Provinsi") or "",
        "agama": row.get("Agama") or "",
        "pekerjaan": row.get("Pekerjaan") or "",
        "status_perkawinan": row.get("Status_Perkawinan") or "",
        "kewarnegaraan": row.get("Kewarnegaraan") or "",
        "idType": row.get("Id_Type") or "",
        "foto": row.get("Foto") or "",
        "tandaTangan": row.get("Tanda_Tangan") or ""
    }

def _confidence_from_rate(rate_row) -> dict:
    if not rate_row:
        return {}
    out = {}
    for js_key, col in _RATE_FIELD_MAP.items():
        val = rate_row.get(col)
        if val is not None:
            out[js_key] = f"{val}%"
    return out

def _verification_from_dukcapil(dukcapil_row) -> tuple:
    if not dukcapil_row:
        return {}, {"checked": False, "status": None, "reason": ""}

    verified = {}
    any_field = False
    all_match = True
    for js_key, col in _DUKCAPIL_FIELD_MAP.items():
        val = dukcapil_row.get(col)
        if val is None:
            continue
        any_field = True
        if _truthy_bit(val):
            verified[js_key] = "True"
        else:
            verified[js_key] = "False"
            all_match = False

    dukcapil = {
        "checked": any_field,
        "status": all_match if any_field else None,
        "reason": "",
    }
    return verified, dukcapil

def _fetch_supporting_documents(apless: str, prechecking_id) -> dict:
    documents: dict = {}

    if not documents and prechecking_id:
        document_query = text("""
            SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT WITH (NOLOCK)
            WHERE Prechecking_Id = :prechecking_id
            ORDER BY DocumentType, CreatedDate
        """)
        rows = db.session.execute(document_query, {"prechecking_id": prechecking_id}).fetchall()
        for row in rows:
            name = row.DocumentName
            if not name:
                continue
            documents.setdefault(row.DocumentType, []).append({
                "customerDocumentId": row.CustomerDocumentId,
                "fileName": name,
                "fileExt": name.split(".")[-1] if "." in name else "",
                "awsKey": row.AWSKey,
                "readonly": True,
            })

    return documents

def _copy_temp_document_to_final(aws_key_old: str, aws_key_new: str) -> bool:
    return copy_object(aws_key_old, aws_key_new)

@cam_bp.route('/check', methods=['POST'])
@login_required
def check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        id_card = (data.get('idCard') or '').strip()
        lessee_tp = (data.get('customerType') or '').strip()

        query = """
            SELECT LESSEE_NM, APLESS, LESSEE_TP
            FROM CAFLESS WITH (NOLOCK)
            WHERE (ID_CARD = :id_card OR NPWP = :id_card) AND LESSEE_TP = :lessee_tp
        """

        result = db.session.execute(db.text(query), {"id_card": id_card, "lessee_tp": lessee_tp})

        data = result.fetchone()
        if data:
            return jsonify({
                "customerName": data[0],
                "APLESS": data[1],
                "LESSEE_TP": data[2]
            })
        else:
            return jsonify({"customerName": ""})

    except Exception:
        current_app.logger.exception("CAM check error")
        return jsonify({"message": "Failed to check customer"}), 500

@cam_bp.route('/lookup-ocr-by-nik', methods=['POST'])
@login_required
def lookup_ocr_by_nik():
    data = request.get_json(silent=True) or {}
    nik = re.sub(r"\D", "", data.get("nik") or "")
    exclude_pid = (data.get("exclude_prechecking_id") or "").strip()

    if len(nik) != 16:
        return jsonify({"found": False, "message": "NIK harus 16 digit"}), 400

    try:
        row = db.session.execute(
            text(f"""
                SELECT TOP 1 {_OCR_SELECT_COLUMNS}
                FROM TEMP_CAFLESS_OCR WITH (NOLOCK)
                WHERE NIK = :nik
                    AND (:exclude_pid = '' OR Prechecking_Id <> :exclude_pid)
                ORDER BY ISNULL(UpdatedDate, CAST('1900-01-01' AS datetime)) DESC, Id DESC
            """),
            {"nik": nik, "exclude_pid": exclude_pid},
        ).fetchone()

        if not row:
            return jsonify({"found": False, "message": "Data KTP tidak ditemukan"})

        ocr = _clean_row(row._mapping)
        ocr_id = ocr.get("Id")

        rate_row = db.session.execute(
            text("SELECT * FROM TEMP_CAFLESS_OCR_Rate WITH (NOLOCK) WHERE Id = :id"),
            {"id": ocr_id},
        ).fetchone()
        dukcapil_row = db.session.execute(
            text("SELECT * FROM TEMP_CAFLESS_OCR_Dukcapil WITH (NOLOCK) WHERE Id = :id"),
            {"id": ocr_id},
        ).fetchone()

        verified, dukcapil = _verification_from_dukcapil(
            _clean_row(dukcapil_row._mapping) if dukcapil_row else None
        )

        payload = _ocr_row_to_dict(ocr)
        payload["confidence"] = _confidence_from_rate(
            _clean_row(rate_row._mapping) if rate_row else None
        )
        payload["verified"] = verified
        payload["dukcapil"] = dukcapil

        documents = _fetch_identity_documents(
            ocr.get("Prechecking_Id"),
            ocr.get("Citizen") or ocr.get("Kewarnegaraan"),
        )

        return jsonify({
            "found": True,
            "sourcePrecheckingId": ocr.get("Prechecking_Id") or "",
            "sourceOcrFor": ocr.get("OCR_For") or "",
            "lastOCROn": _fmt_display_date(ocr.get("UpdatedDate")),
            "ocr": payload,
            "documents": documents,
        })

    except Exception:
        current_app.logger.exception("lookup_ocr_by_nik error")
        return jsonify({"found": False, "message": "Database error"}), 500

@cam_bp.route('/get_data_customer', methods=['POST'])
@login_required
def get_data_customer():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        id_card = (data.get('idCard') or '').strip()
        lessee_tp = (data.get('customerType') or '').strip().upper()

        if not id_card or not lessee_tp:
            return jsonify({"message": "Missing idCard or customerType"}), 400

        cafless_query = text("""
            SELECT LESSEE_NM AS customerName, APLESS
            FROM CAFLESS WITH (NOLOCK)
            WHERE (ID_CARD = :id_card OR NPWP = :id_card) AND LESSEE_TP = :lessee_tp
        """)
        cafless_result = db.session.execute(cafless_query, {
            "id_card": id_card,
            "lessee_tp": lessee_tp
        }).fetchone()

        if not cafless_result:
            return jsonify({
                "customerName": "",
                "apless": "",
                "previous_prechecking_id": "",
                "precheckingData": {
                    "corporate": [],
                    "customer": {},
                    "spouse": {},
                    "lastOCROn": "Not found",
                    "ocrRateData": []
                },
                "documents": {},
            })

        cafless_row = _clean_row(cafless_result._mapping)
        customer_name = cafless_row.get("customerName") or ""
        apless = cafless_row.get("APLESS") or ""

        temp_cafless_query = text("""
            SELECT TOP 1 *
            FROM TEMP_CAFLESS WITH (NOLOCK)
            WHERE (IdCardNo = :id_card OR NPWP = :id_card) AND CustomerType = :lessee_tp
            ORDER BY CreatedDate DESC
        """)
        temp_cafless_result = db.session.execute(temp_cafless_query, {
            "id_card": id_card,
            "lessee_tp": lessee_tp
        }).fetchone()

        temp_row = _clean_row(temp_cafless_result._mapping) if temp_cafless_result else {}
        prechecking_id = temp_row.get("Prechecking_Id")

        documents = _fetch_supporting_documents(apless, prechecking_id)

        if not temp_cafless_result:
            return jsonify({
                "customerName": customer_name,
                "apless": apless,
                "previous_prechecking_id": "",
                "precheckingData": {
                    "corporate": [],
                    "customer": {},
                    "spouse": {},
                    "lastOCROn": "No precheck data",
                    "ocrRateData": []
                },
                "documents": documents,
            })

        meta = {
            "maritalStatus": temp_row.get("MaritalStatus") or "",
            "isCarro": _truthy_bit(temp_row.get("Carro")),
            "workAddress": temp_row.get("WorkAddress") or "",
        }

        ocr_query = text(f"""
            SELECT {_OCR_SELECT_COLUMNS}
            FROM TEMP_CAFLESS_OCR WITH (NOLOCK)
            WHERE Prechecking_Id = :prechecking_id
        """)
        ocr_rows = db.session.execute(ocr_query, {
            "prechecking_id": prechecking_id
        }).fetchall()

        corporate_ocr_list = []
        customer_ocr = {}
        spouse_ocr = {}
        last_ocr_date = None
        ocr_ids = []

        for raw_row in ocr_rows:
            row = _clean_row(raw_row._mapping)
            ocr_ids.append(row.get("Id"))

            ocr_dict = _ocr_row_to_dict(row)

            updated_date = row.get("UpdatedDate")
            if updated_date and (not last_ocr_date or updated_date > last_ocr_date):
                last_ocr_date = updated_date

            ocr_for = row.get("OCR_For")
            if ocr_for == 'C':
                customer_ocr = ocr_dict
            elif ocr_for == 'S':
                spouse_ocr = ocr_dict
            elif ocr_for == 'P':
                corporate_ocr_list.append(ocr_dict)

        last_ocr_str = _fmt_display_date(last_ocr_date) or "Unknown"

        ocr_rate_data = []
        rate_by_id = {}
        dukcapil_by_id = {}
        if ocr_ids:
            placeholders = ', '.join(f':id_{i}' for i in range(len(ocr_ids)))
            params = {f"id_{i}": oid for i, oid in enumerate(ocr_ids)}

            ocr_rate_query = text(f"""
                SELECT *
                FROM TEMP_CAFLESS_OCR_Rate WITH (NOLOCK)
                WHERE Id IN ({placeholders})
            """)
            ocr_rate_rows = db.session.execute(ocr_rate_query, params).fetchall()
            for r in ocr_rate_rows:
                rd = _clean_row(r._mapping)
                rate_by_id[rd.get("Id")] = rd
            ocr_rate_data = list(rate_by_id.values())

            ocr_dukcapil_query = text(f"""
                SELECT *
                FROM TEMP_CAFLESS_OCR_Dukcapil WITH (NOLOCK)
                WHERE Id IN ({placeholders})
            """)
            ocr_dukcapil_rows = db.session.execute(ocr_dukcapil_query, params).fetchall()
            for r in ocr_dukcapil_rows:
                rd = _clean_row(r._mapping)
                dukcapil_by_id[rd.get("Id")] = rd

        if customer_ocr:
            verified, dukcapil = _verification_from_dukcapil(dukcapil_by_id.get(customer_ocr.get("id")))
            customer_ocr["confidence"] = _confidence_from_rate(rate_by_id.get(customer_ocr.get("id")))
            customer_ocr["verified"] = verified
            customer_ocr["dukcapil"] = dukcapil
        if spouse_ocr:
            verified, dukcapil = _verification_from_dukcapil(dukcapil_by_id.get(spouse_ocr.get("id")))
            spouse_ocr["confidence"] = _confidence_from_rate(rate_by_id.get(spouse_ocr.get("id")))
            spouse_ocr["verified"] = verified
            spouse_ocr["dukcapil"] = dukcapil

        for officer in corporate_ocr_list:
            verified, dukcapil = _verification_from_dukcapil(dukcapil_by_id.get(officer.get("id")))
            officer["confidence"] = _confidence_from_rate(rate_by_id.get(officer.get("id")))
            officer["verified"] = verified
            officer["dukcapil"] = dukcapil

        if lessee_tp == "PR":
            prechecking_data = {
                "customer": customer_ocr,
                "spouse": spouse_ocr,
                "corporate": [],
                "meta": meta,
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }
        elif lessee_tp == "PT":
            prechecking_data = {
                "customer": {},
                "spouse": {},
                "corporate": corporate_ocr_list,
                "meta": meta,
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }
        else:
            prechecking_data = {
                "customer": {},
                "spouse": {},
                "corporate": [],
                "meta": meta,
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }

        return jsonify({
            "customerName": customer_name,
            "apless": apless,
            "previous_prechecking_id": prechecking_id,
            "precheckingData": prechecking_data,
            "documents": documents,
        })

    except Exception:
        current_app.logger.exception("Error in get_data_customer")
        return jsonify({
            "customerName": "",
            "apless": "",
            "previous_prechecking_id": "",
            "precheckingData": {
                "corporate": [],
                "customer": {},
                "spouse": {},
                "lastOCROn": "Error",
                "ocrRateData": []
            },
            "documents": {},
        }), 500

@cam_bp.route('/init', methods=['GET'])
def init_cam():
   
    try:
        purpose_result = db.session.execute(
            text("SELECT PURPOFFINC, [DESC] FROM MSTPURPOFFINC WITH (NOLOCK) WHERE Flag_Active = '1'")
        )
        purposes = [
            {"code": row.PURPOFFINC, "desc": row.DESC}
            for row in purpose_result.mappings()
        ]

        finance_result = db.session.execute(
            text("SELECT Cons_Leas, name FROM MSTCFFL WITH (NOLOCK)")
        )
        finance_types = [
            {"code": row.Cons_Leas, "name": row.name}
            for row in finance_result.mappings()
        ]

        return jsonify({
            "purposes": purposes,
            "financeTypes": finance_types
        })
    except Exception:
        current_app.logger.exception("Error in CAM /init")
        return jsonify({"error": "Failed to load form options"}), 500

@cam_bp.route('/finance-types', methods=['GET'])
@login_required
def finance_types():
   
    purpoffinc = (request.args.get('purpoffinc') or '').strip()
    lessee_tp = (request.args.get('lesseeTp') or '').strip().upper()

    if not purpoffinc:
        return jsonify([])

    try:
        rows = db.session.execute(text("""
            SELECT Cons_Leas, name
            FROM MSTCFFL WITH (NOLOCK)
            ORDER BY name
        """)).mappings().all()

        return jsonify([{"value": r["Cons_Leas"], "label": r["name"]} for r in rows])
    except Exception:
        current_app.logger.exception("Error in CAM /finance-types")
        return jsonify({"message": "Failed to load finance types"}), 500

@cam_bp.route('/contract-types', methods=['GET'])
@login_required
def contract_types():
    
    fin_type = (request.args.get('finType') or '').strip().upper()

    if not fin_type:
        return jsonify([])

    if fin_type not in _CONTRACT_TYPE_FIN_TYPES:
        return jsonify([{"value": "NEW", "label": "NEW FINANCING", "selected": True}])

    return jsonify([{"value": "NEW", "label": "NEW FINANCING", "selected": True}])

@cam_bp.route('/dp-confirmation', methods=['GET'])
@login_required
def dp_confirmation():
    
    current_app.logger.warning("CAM /dp-confirmation is not implemented yet")
    return jsonify({"message": "DP confirmation is not available"}), 501

@cam_bp.route('/submit', methods=['POST'])
@login_required
def submit():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        apless = (data.get('apless') or '').strip()
        prechecking_id = data.get('precheckingId')
        lessee_tp = (data.get('lesseeTp') or '').strip()
        purpoffinc = (data.get('purpoffinc') or '').strip()
        fin_type = (data.get('finType') or '').strip()
        guarantor = (data.get('guarantor') or '').strip()
        new_car = (data.get('newCar') or '').strip()
        public = (data.get('publicStatus') or '').strip()
        boa = (data.get('boa') or '').strip()
        bot = (data.get('bot') or '').strip()

        if not apless:
            return jsonify({"message": "Customer data not found"}), 400

        ind_cor = '1' if lessee_tp == 'PR' else '2'

        cont_type = 'NEW'

        if fin_type in _USED_ONLY_FIN_TYPES:
            new_car = '1'

        errors = {}
        if not purpoffinc:
            errors['purpoffinc'] = "Purpose of Finance must not be empty"
        if not fin_type:
            errors['finType'] = "Finance Type must not be empty"
        if not guarantor:
            errors['guarantor'] = "Guarantor availability must not be empty"
        if not new_car:
            errors['newCar'] = "Vehicle condition must not be empty"

        if lessee_tp == 'PT' and fin_type != 'D' and not public:
            errors['publicStatus'] = "Go Public must not be empty"

        if not boa:
            errors['boa'] = "Beneficial Owner Availability must not be empty"
        if boa == '2' and not bot:
            errors['bot'] = "Beneficial Owner Type must not be empty"

        if errors:
            return jsonify({"message": "Validation failed", "errors": errors}), 400

        emp_id = session.get('emp_id')
        branch_cd = session.get('branchcode')

        applno_cmo = f"APPL_NO{emp_id[-4:]}"

        seq_row = db.session.execute(text("""
            SELECT NextNumber, CONVERT(varchar(7), [LastUpdate], 126) AS LastUpdate
            FROM TANUMBER WITH (NOLOCK)
            WHERE PropertyGroupName = :prop
        """), {"prop": applno_cmo}).fetchone()

        if not seq_row:
            return jsonify({"message": "Cannot create CAM, please call helpdesk"}), 500

        this_month_ym = datetime.now().strftime('%Y-%m')
        applno_seq = seq_row.NextNumber if seq_row.LastUpdate == this_month_ym else 1
        applno_padded = str(applno_seq).zfill(3)
        applno = f"{emp_id[-4:]}{datetime.now().strftime('%y%m')}{applno_padded}"

        db.session.execute(text("""
            UPDATE TANUMBER SET NextNumber = :next_val, LastUpdate = GETDATE()
            WHERE PropertyGroupName = :prop
        """), {"next_val": applno_seq + 1, "prop": applno_cmo})

        has_guarantor = 1 if guarantor == '2' else 0
        condition = 'NEW' if new_car == '2' else 'USED'
        tahun = datetime.now().strftime('%Y') if new_car == '2' else ''

        db.session.execute(text("""
            INSERT INTO CAFCONT (APPL_NO, APLESS, CREATE_DATE, Disc_Cust, CURR_CODE, Cons_Leas,
                                  BRANCH_CD, CMO, HAS_GUARANTOR, purpoffinc, Cont_type, prechecking_id)
            VALUES (:applno, :apless, GETDATE(), '0', 'IDR', :fin_type,
                    :branch_cd, :emp_id, :has_guarantor, :purpoffinc, :cont_type, :prechecking_id)
        """), {
            "applno": applno, "apless": apless, "fin_type": fin_type,
            "branch_cd": branch_cd, "emp_id": emp_id, "has_guarantor": has_guarantor,
            "purpoffinc": purpoffinc, "cont_type": cont_type, "prechecking_id": prechecking_id,
        })

        equip_row = db.session.execute(text("""
            SELECT NextNumber FROM TANUMBER WITH (NOLOCK) WHERE PropertyGroupName = 'CAFEQUIP_ID'
        """)).fetchone()
        cafequip_id = equip_row.NextNumber

        db.session.execute(text("""
            INSERT INTO CAFEQUIP (CAFEQUIP_ID, APPL_NO, CONDITION, TAHUN)
            VALUES (:cafequip_id, :applno, :condition, :tahun)
        """), {"cafequip_id": cafequip_id, "applno": applno, "condition": condition, "tahun": tahun})

        db.session.execute(text("""
            UPDATE TANUMBER SET NextNumber = :next_val, LastUpdate = GETDATE()
            WHERE PropertyGroupName = 'CAFEQUIP_ID'
        """), {"next_val": cafequip_id + 1})

        db.session.execute(
            text("EXEC USP_Copy_Document :prechecking_id, :applno"),
            {"prechecking_id": prechecking_id, "applno": applno},
        )

        try:
            db.session.execute(
                text("EXEC USP_CAM_REQUEST_MOVESIKDOC :prechecking_id, :applno"),
                {"prechecking_id": prechecking_id, "applno": applno},
            )
        except Exception:
            current_app.logger.exception("USP_CAM_REQUEST_MOVESIKDOC failed for %s -> %s", prechecking_id, applno)

        doc_rows = db.session.execute(text("""
            SELECT DISTINCT cd.Apless, cd.Prechecking_Id, cd.DocumentName, cd.AWSKey, cl.FINAL_APLESS
            FROM TEMP_CUSTOMER_DOCUMENT cd
            INNER JOIN TEMP_CAFLESS cl
                ON cl.Apless = cd.Apless AND cd.Prechecking_Id = cl.Prechecking_Id
            WHERE cd.Prechecking_Id = :prechecking_id
        """), {"prechecking_id": prechecking_id}).fetchall()

        for row in doc_rows:
            aws_key_old = row.AWSKey
            if not aws_key_old:
                continue
            aws_key_new = aws_key_old.replace(row.Apless, row.FINAL_APLESS).replace(str(prechecking_id), applno)
            _copy_temp_document_to_final(aws_key_old, aws_key_new)

        db.session.commit()

        return jsonify({
            "applno": applno,
            "id1": fin_type,
            "id2": ind_cor,
            "id3": '1',
            "id4": guarantor,
            "id5": new_car,
            "id6": "New",
            "id7": purpoffinc,
            "id9": cont_type,
            "id11": boa,
            "id12": bot,
            "id13": public,
            "apless": apless,
        })

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error in CAM submit")
        return jsonify({"message": "Failed to submit CAM"}), 500