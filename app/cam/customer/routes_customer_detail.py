from app import db
from flask import Blueprint, request, jsonify, current_app, redirect
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import datetime
from botocore.client import Config
import boto3

customer_detail_bp = Blueprint('customer_detail', __name__, url_prefix='/CAM/CustomerDetail')

def format_date_for_display(date_value):
    if not date_value:
        return ""
    try:
        if isinstance(date_value, datetime):
            return date_value.strftime("%d-%m-%Y")
        return str(date_value)
    except:
        return ""

def parse_phone_number(phone_value):
    if not phone_value:
        return {"code": "62", "area": "", "number": ""}
    
    parts = str(phone_value).split("-")
    if len(parts) >= 3:
        return {"code": parts[0] or "62", "area": parts[1], "number": parts[2]}
    elif len(parts) == 2:
        return {"code": parts[0] or "62", "area": "", "number": parts[1]}
    else:
        return {"code": "62", "area": "", "number": str(phone_value)}

def format_npwp_display(npwp_value):
    if not npwp_value:
        return ""
    
    clean = ''.join(filter(str.isdigit, str(npwp_value)))
    if len(clean) != 15:
        return npwp_value
    
    return f"{clean[0:2]}.{clean[2:5]}.{clean[5:8]}.{clean[8:9]}-{clean[9:12]}.{clean[12:16]}"

@customer_detail_bp.route('/detail', methods=['GET'])
@login_required
def get_customer_detail():
    apless = request.args.get('apless', '').strip()

    if not apless:
        return jsonify({"success": False, "message": "APLESS parameter is required"}), 400

    try:
        query = text("""
            SELECT
                cld.PASSPORTNO, 
                ca.LESSEE_NM, 
                ca.Lessee_Cat, 
                ca.ADDRESS1, 
                ca.SPOUSE_INCOME,
                cda.KECAMATAN,
                cda.KELURAHAN,
                cda.RT,
                cda.RW,
                cda.EMERGENCY_NAME,
                cda.EMERGENCY_ADDRESS,
                cda.EMERGENCY_PHONE,
                cda.EMERGENCY_RELATION, 
                ca.CITY1, 
                ca.Address_Status, 
                ca.ZipCode1,
                ca.PHONE2, 
                ca.Mobile_phone1, 
                ca.Mobile_phone2, 
                ca.Mobile_phone3, 
                ca.EMAIL1, 
                ca.EMAIL2, 
                ca.NPWP, 
                ca.Area_CD, 
                ca.Fax1, 
                ca.Send_SMS,
                ca.Spouse, 
                ca.Mother, 
                ca.GrpCode, 
                ca.PLACEBIRTH, 
                ca.TGLBIRTH, 
                ca.GENDER, 
                ca.MARITAL, 
                ca.RELIGION, 
                ca.Citizen, 
                ca.Nationality, 
                ca.Cust_Type,
                ca.ID_CARD, 
                ca.Id_Card_Valid,
                ca.FAM_CARD, 
                ca.INDUS_CODE, 
                ca.OTHER_PHONE1, 
                ca.OTHER_PHONE2, 
                ca.OTHER_PHONENOTES1, 
                ca.OTHER_PHONENOTES2, 
                ca.ALIAS_NAME,
                cld.BUSINESS_TYPE, 
                cld.Fullname_Without_Title, 
                cld.LAST_EDUCATION, 
                cld.CAREER_FIELD, 
                cld.SPOUSE_PLACEBIRTH, 
                cld.SPOUSE_TGLBIRTH, 
                cld.SPOUSE_CITIZEN,
                cld.SPOUSE_NATIONALITY, 
                cld.SPOUSE_ID_CARD, 
                cld.SPOUSE_Id_CARD_VALID, 
                cld.SPOUSE_PASSPORTNO, 
                cld.SPOUSE_MARRIAGE, 
                cld.SPOUSE_DEPENDENT,
                ISNULL(cld.RELATIONSHIP,'e3') as RELATIONSHIP, 
                cld.SPOUSE_Fullname_Without_Title as SPOUSE_Fullname_Without_Title, 
                cda.Address_NPWP, 
                cda.Area_CD_NPWP,
                cda.Kecamatan_NPWP, 
                cda.Kelurahan_NPWP, 
                cda.zipcode_NPWP, 
                cda.Spouse_Address, 
                cda.Spouse_Area_CD, 
                cda.Spouse_City, 
                cda.Spouse_Kecamatan, 
                cda.Spouse_Kelurahan,
                cda.Spouse_RT, 
                cda.Spouse_RW, 
                cda.Spouse_Zipcode, 
                cld.Live_since, 
                cld.SPOUSE_MobilePhone, 
                cld.SPOUSE_Email 
            FROM CAFLESS ca WITH(NOLOCK)
                LEFT JOIN CAFLESS_DETAIL_ADDRESS cda WITH(NOLOCK) ON ca.APLESS = cda.APLESS
                LEFT JOIN CAFLESS_DETAIL cld WITH(NOLOCK) ON ca.APLESS = cld.APLESS
            WHERE ca.APLESS = :apless
        """)
        
        params = {"apless": apless}
        result = db.session.execute(query, params)
        row = result.fetchone()
        
        if not row:
            return jsonify({"success": False, "message": "Customer not found"}), 404
        
        phone_parsed = parse_phone_number(row.PHONE2)
        fax_parsed = parse_phone_number(row.Fax1)
        mobile1_parsed = parse_phone_number(row.Mobile_phone1)
        mobile2_parsed = parse_phone_number(row.Mobile_phone2)
        mobile3_parsed = parse_phone_number(row.Mobile_phone3)
        other1_parsed = parse_phone_number(row.OTHER_PHONE1)
        other2_parsed = parse_phone_number(row.OTHER_PHONE2)
        
        customer_data = {
            "APLESS": apless,
            "LESSEE_NM": row.LESSEE_NM or "",
            "LESSEE_CAT": row.Lessee_Cat or "",
            "ALIAS_NAME": row.ALIAS_NAME or "",
            "ID_CARD_NAME": row.Fullname_Without_Title or "",
            "PLACEBIRTH": row.PLACEBIRTH or "",
            "TGLBIRTH": format_date_for_display(row.TGLBIRTH),
            "GENDER": row.GENDER or "",
            "RELIGION": row.RELIGION or "",
            "CITIZEN": row.Citizen or "",
            "NATIONALITY": row.Nationality or "",
            "PASSPORT_NO": row.PASSPORTNO or "",
            "ID_CARD": row.ID_CARD or "",
            "ID_CARD_VALID": format_date_for_display(row.Id_Card_Valid),
            "FAM_CARD": row.FAM_CARD or "",
            "MOTHER_NAME": row.Mother or "",
            "MARITAL": row.MARITAL or "",
            "SPOUSE_NAME": row.Spouse or "",
            "SPOUSE_NAME_WT": row.SPOUSE_Fullname_Without_Title or "",
            "SPOUSE_PLACEBIRTH": row.SPOUSE_PLACEBIRTH or "",
            "SPOUSE_TGLBIRTH": format_date_for_display(row.SPOUSE_TGLBIRTH),
            "SPOUSE_CITIZEN": row.SPOUSE_CITIZEN or "",
            "SPOUSE_NATIONALITY": row.SPOUSE_NATIONALITY or "",
            "SPOUSE_ID_CARD": row.SPOUSE_ID_CARD or "",
            "SPOUSE_ID_CARD_VALID": format_date_for_display(row.SPOUSE_Id_CARD_VALID),
            "SPOUSE_PASSPORT": row.SPOUSE_PASSPORTNO or "",
            "SPOUSE_MARRIAGE_AGREE": row.SPOUSE_MARRIAGE or "",
            "SPOUSE_DEPENDENT": row.SPOUSE_DEPENDENT or "",
            "RELATIONSHIP_MLCI": row.RELATIONSHIP or "",
            
            "ADDRESS1": row.ADDRESS1 or "",
            "AREA_CD": row.Area_CD or "",
            "PROVINCE": "",
            "CITY": row.CITY1 or "",
            "KECAMATAN": row.KECAMATAN or "",
            "KELURAHAN": row.KELURAHAN or "",
            "RT": row.RT or "",
            "RW": row.RW or "",
            "ZIPCODE": row.ZipCode1 or "",
            "YEAR_LIVE": row.Live_since or "",
            
            "ADDRESS_NPWP": row.Address_NPWP or "",
            "AREA_CD_NPWP": row.Area_CD_NPWP or "",
            "PROVINCE_NPWP": "",
            "CITY_NPWP": "",
            "KECAMATAN_NPWP": row.Kecamatan_NPWP or "",
            "KELURAHAN_NPWP": row.Kelurahan_NPWP or "",
            "ZIPCODE_NPWP": row.zipcode_NPWP or "",
            
            "SPOUSE_ADDRESS": row.Spouse_Address or "",
            "SPOUSE_AREA_CD": row.Spouse_Area_CD or "",
            "SPOUSE_PROVINCE": "",
            "SPOUSE_CITY": row.Spouse_City or "",
            "SPOUSE_KECAMATAN": row.Spouse_Kecamatan or "",
            "SPOUSE_KELURAHAN": row.Spouse_Kelurahan or "",
            "SPOUSE_RT": row.Spouse_RT or "",
            "SPOUSE_RW": row.Spouse_RW or "",
            "SPOUSE_ZIPCODE": row.Spouse_Zipcode or "",
            
            "PHONE_CODE": phone_parsed["code"],
            "PHONE_AREA": phone_parsed["area"],
            "PHONE_NUMBER": phone_parsed["number"],
            "FAX_CODE": fax_parsed["code"],
            "FAX_AREA": fax_parsed["area"],
            "FAX_NUMBER": fax_parsed["number"],
            "MOBILE1_CODE": mobile1_parsed["code"],
            "MOBILE1_NUMBER": mobile1_parsed["number"],
            "MOBILE2_CODE": mobile2_parsed["code"],
            "MOBILE2_NUMBER": mobile2_parsed["number"],
            "MOBILE3_CODE": mobile3_parsed["code"],
            "MOBILE3_NUMBER": mobile3_parsed["number"],
            "OTHER_PHONE1_CODE": other1_parsed["code"],
            "OTHER_PHONE1_AREA": other1_parsed["area"],
            "OTHER_PHONE1_NUMBER": other1_parsed["number"],
            "OTHER_PHONE1_NOTES": row.OTHER_PHONENOTES1 or "",
            "OTHER_PHONE2_CODE": other2_parsed["code"],
            "OTHER_PHONE2_AREA": other2_parsed["area"],
            "OTHER_PHONE2_NUMBER": other2_parsed["number"],
            "OTHER_PHONE2_NOTES": row.OTHER_PHONENOTES2 or "",
            "SEND_SMS": row.Send_SMS == "1" if row.Send_SMS else False,
            "EMAIL1": row.EMAIL1 or "",
            "EMAIL2": row.EMAIL2 or "",
            
            "OCCUPATION_TYPE": row.BUSINESS_TYPE or "",
            "LAST_EDUCATION": row.LAST_EDUCATION or "",
            "CAREER_FIELD": row.CAREER_FIELD or "",
            "INDUS_CODE": row.INDUS_CODE or "",
            "MLCL_CODE": row.INDUS_CODE or "", 
            
            "NPWP": format_npwp_display(row.NPWP),
            "NPWP_AREA_CD": row.Area_CD or "",
            
            "CUST_TYPE": row.Cust_Type or "",
            "GRP_CODE": row.GrpCode or "",
            
            "EMERGENCY_NAME": row.EMERGENCY_NAME or "",
            "EMERGENCY_ADDRESS": row.EMERGENCY_ADDRESS or "",
            "EMERGENCY_PHONE": row.EMERGENCY_PHONE or "",
            "EMERGENCY_RELATION": row.EMERGENCY_RELATION or "",
        }
        
        return jsonify({"success": True, "data": customer_data})

    except Exception as e:
        current_app.logger.exception(f"Customer detail fetch error for APLESS: {apless}")
        return jsonify({"success": False, "message": "Failed to fetch customer detail"}), 500
    
@customer_detail_bp.route('/download_aws', methods=['GET'])
@login_required
def download_aws():
    aws_key = request.args.get('aws_key')
    profile = request.args.get('profile', 'default')
    bucket = request.args.get('bucket')
    file_name = request.args.get('file_name')

    if not aws_key or not bucket:
        current_app.logger.error("Missing aws_key or bucket")
        return jsonify({"error": "Missing aws_key or bucket"}), 400

    try:
        current_app.logger.info(f"Generating presigned URL - Bucket: {bucket}, Key: {aws_key}, Profile: {profile}")

        session = boto3.Session(profile_name=profile)
        s3_client = session.client('s3', config=Config(signature_version='s3v4'))

        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': aws_key
            },
            ExpiresIn=1800
        )

        current_app.logger.info(f"Presigned URL generated successfully for key: {aws_key}")
        return redirect(signed_url)

    except Exception as e:
        current_app.logger.exception(f"Presigned URL failed - Key: {aws_key}, Error: {str(e)}")
        
        error_msg = str(e)
        if "NoSuchKey" in error_msg or "not found" in error_msg.lower():
            return jsonify({"error": f"File not found in S3: {aws_key}"}), 404
        elif "Access Denied" in error_msg or "403" in error_msg:
            return jsonify({"error": "Access Denied - Check IAM permissions or bucket policy"}), 403
        elif "profile" in error_msg.lower() or "credentials" in error_msg.lower():
            return jsonify({"error": f"Credentials error with profile '{profile}'. Check ~/.aws/credentials"}), 500
        else:
            return jsonify({"error": f"Failed to generate link: {error_msg}"}), 500