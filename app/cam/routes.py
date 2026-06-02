from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
from app import db

cam_bp = Blueprint('cam', __name__, url_prefix='/CAM')

@cam_bp.route('/check', methods=['POST'])
def check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400
        
        id_card = (data.get('idCard') or '').strip()
        lessee_tp = (data.get('customerType') or '').strip()

        query = """
            SELECT LESSEE_NM, APLESS, Prechecking_id, LESSEE_TP
            FROM CAFLESS
            WHERE (ID_CARD = :id_card OR NPWP = :id_card) AND LESSEE_TP = :lessee_tp
        """
        
        result = db.session.execute(db.text(query), {"id_card": id_card, "lessee_tp": lessee_tp})

        data = result.fetchone()
        if data:
            return jsonify({
                "customerName": data[0],
                "APLESS": data[1],
                "Prechecking_id": data[2],
                "LESSEE_TP": data[3]
            })
        else:
            return jsonify({"customerName": ""})
        
    except Exception as e:
        current_app.logger.exception("CAM check error")
        
        return jsonify([])

@cam_bp.route('/get_data_customer', methods=['POST'])
def get_data_customer():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        id_card = (data.get('idCard') or '').strip()
        lessee_tp = (data.get('customerType') or '').strip().upper()  # Normalize case

        if not id_card or not lessee_tp:
            return jsonify({"message": "Missing idCard or customerType"}), 400

        cafless_query = text("""
            SELECT LESSEE_NM AS customerName
            FROM CAFLESS
            WHERE (ID_CARD = :id_card OR NPWP = :id_card) AND LESSEE_TP = :lessee_tp
        """)
        cafless_result = db.session.execute(cafless_query, {
            "id_card": id_card,
            "lessee_tp": lessee_tp
        }).fetchone()

        if not cafless_result:
            return jsonify({
                "customerName": "",
                "precheckingData": {
                    "corporate": [],
                    "customer": {},
                    "spouse": {},
                    "lastOCROn": "Not found",
                    "ocrRateData": []
                },
                "documents": {}
            })

        customer_name = cafless_result.customerName

        temp_cafless_query = text("""
            SELECT TOP 1 Prechecking_Id
            FROM TEMP_CAFLESS
            WHERE (IdCardNo = :id_card OR NPWP = :id_card) AND LesseeType = :lessee_tp
            ORDER BY CreatedDate DESC
        """)
        temp_cafless_result = db.session.execute(temp_cafless_query, {
            "id_card": id_card,
            "lessee_tp": lessee_tp
        }).fetchone()

        if not temp_cafless_result:
            return jsonify({
                "customerName": customer_name,
                "precheckingData": {
                    "corporate": [],
                    "customer": {},
                    "spouse": {},
                    "lastOCROn": "No precheck data",
                    "ocrRateData": []
                },
                "documents": {}
            })

        prechecking_id = temp_cafless_result.Prechecking_Id

        ocr_query = text("""
            SELECT 
                Id,
                OCR_For,
                Citizen,
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
            FROM TEMP_CAFLESS_OCR
            WHERE Prechecking_Id = :prechecking_id
        """)
        ocr_rows = db.session.execute(ocr_query, {
            "prechecking_id": prechecking_id
        }).fetchall()

        corporate_ocr_list = []
        customer_ocr = {}
        spouse_ocr = {}
        last_ocr_date = None

        for row in ocr_rows:
            tgl_lahir_str = row.Tgl_Lahir.strftime("%d %b %Y") if row.Tgl_Lahir else ""
            rt_rw = f"{row.RT or ''} / {row.RW or ''}".strip(" /")

            ocr_dict = {
                "id": row.Id,
                "nik": row.NIK or "",
                "nama": row.Nama or "",
                "tempatLahir": row.Tempat_Lahir or "",
                "tglLahir": tgl_lahir_str,
                "jenisKelamin": row.Jenis_Kelamin or "",
                "golonganDarah": row.Golongan_Darah or "",
                "alamat": row.Alamat or "",
                "rtRw": rt_rw,
                "kelurahan": row.Kelurahan or "",
                "kecamatan": row.Kecamatan or "",
                "kota": row.Kota or "",
                "provinsi": row.Provinsi or "",
                "agama": row.Agama or "",
                "pekerjaan": row.Pekerjaan or "",
                "status_perkawinan": row.Status_Perkawinan or "",
                "kewarnegaraan": row.Kewarnegaraan or "",
                "foto": row.Foto or "",
                "tandaTangan": row.Tanda_Tangan or ""
            }

            if row.UpdatedDate and (not last_ocr_date or row.UpdatedDate > last_ocr_date):
                last_ocr_date = row.UpdatedDate

            if row.OCR_For == 'C':
                customer_ocr = ocr_dict
            elif row.OCR_For == 'S':
                spouse_ocr = ocr_dict
            elif row.OCR_For == 'P':
                corporate_ocr_list.append(ocr_dict)

        last_ocr_str = last_ocr_date.strftime("%d %b %Y") if last_ocr_date else "Unknown"

        ocr_rate_data = []
        ocr_ids = [row.Id for row in ocr_rows]
        if ocr_ids:
            placeholders = ', '.join(f':id_{i}' for i in range(len(ocr_ids)))
            ocr_rate_query = text(f"""
                SELECT *
                FROM TEMP_CAFLESS_OCR_Rate
                WHERE Id IN ({placeholders})
            """)
            params = {f"id_{i}": oid for i, oid in enumerate(ocr_ids)}
            ocr_rate_rows = db.session.execute(ocr_rate_query, params).fetchall()
            ocr_rate_data = [dict(row._mapping) for row in ocr_rate_rows]

        if lessee_tp == "PR":
            prechecking_data = {
                "customer": customer_ocr,
                "spouse": spouse_ocr,
                "corporate": [],
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }
        elif lessee_tp == "PT":
            prechecking_data = {
                "customer": {},
                "spouse": {},
                "corporate": corporate_ocr_list,
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }
        else:
            prechecking_data = {
                "customer": {},
                "spouse": {},
                "corporate": [],
                "lastOCROn": last_ocr_str,
                "ocrRateData": ocr_rate_data
            }

        document_query = text("""
            SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT WITH (NOLOCK)
            WHERE Prechecking_Id = :prechecking_id
            ORDER BY DocumentType, CreatedDate
        """)
        document_rows = db.session.execute(document_query, {
            "prechecking_id": prechecking_id
        }).fetchall()

        documents = {}
        for row in document_rows:
            doc_id = row.CustomerDocumentId
            name = row.DocumentName
            doc_type = row.DocumentType
            aws_key = row.AWSKey

            if not name:
                continue

            if doc_type not in documents:
                documents[doc_type] = []

            ext = name.split('.')[-1] if '.' in name else ''
            documents[doc_type].append({
                'customerDocumentId': doc_id,
                'fileName': name,
                'fileExt': ext,
                'awsKey': aws_key
            })

        return jsonify({
            "customerName": customer_name,
            "precheckingData": prechecking_data,
            "documents": documents,
        })

    except Exception as e:
        current_app.logger.exception("Error in get_data_customer")
        return jsonify({
            "customerName": "",
            "precheckingData": {
                "corporate": [],
                "customer": {},
                "spouse": {},
                "lastOCROn": "Error",
                "ocrRateData": []
            },
            "documents": {}
        }), 500

@cam_bp.route('/init', methods=['GET'])
def init_cam():
    try:
        purpose_result = db.session.execute(
            text("SELECT PURPOFFINC, [DESC] FROM MSTPURPOFFINC WHERE Flag_Active = '1'")
        )
        purposes = [
            {"code": row.PURPOFFINC, "desc": row.DESC}
            for row in purpose_result.mappings()
        ]

        finance_result = db.session.execute(
            text("SELECT Cons_Leas, name FROM MSTCFFL")
        )
        finance_types = [
            {"code": row.Cons_Leas, "name": row.name}
            for row in finance_result.mappings()
        ]

        return jsonify({
            "purposes": purposes,
            "financeTypes": finance_types
        })
    except Exception as e:
        current_app.logger.exception("Error in CAM /init")
        return jsonify({"error": "Failed to load form options"}), 500