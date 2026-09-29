from sqlalchemy import text
from app import db

def dukcapil_flag(val) -> str:
    if val is None:
        return ""
    return "True" if int(val) == 1 else "False"

def load_person_ocr(prechecking_id: str, ocr_for: str):
    ocr = db.session.execute(text("""
        SELECT Citizen, NIK, Nama, Tempat_Lahir,
               FORMAT(Tgl_Lahir,'dd-MM-yyyy') AS Tgl_Lahir,
               Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
               Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
               Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan
        FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchone()
    if not ocr:
        return None

    rate = db.session.execute(text("""
        SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
               Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
               Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan
        FROM TEMP_CAFLESS_OCR_Rate WITH(NOLOCK)
        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                    WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for)
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchone()

    duc = db.session.execute(text("""
        SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
               Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan
        FROM TEMP_CAFLESS_OCR_Dukcapil WITH(NOLOCK)
        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                    WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for)
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchone()

    def field(val, cr_val, duc_val=None, has_duc_column=True):
        return {
            "value": val or "",
            "confidence": f"{cr_val}%" if cr_val not in (None, "") else "",
            "verified": dukcapil_flag(duc_val) if has_duc_column and duc_val is not None else "",
        }

    return {
        "citizen": ocr.Citizen or "",
        "idCardNo":    field(ocr.NIK,          rate.NIK if rate else None,          duc.NIK if duc else None),
        "name":        field(ocr.Nama,         rate.Nama if rate else None,         duc.Nama if duc else None),
        "pob":         field(ocr.Tempat_Lahir, rate.Tempat_Lahir if rate else None, duc.Tempat_Lahir if duc else None),
        "dob":         field(ocr.Tgl_Lahir,    rate.Tgl_Lahir if rate else None,    duc.Tgl_Lahir if duc else None),
        "gender":      field(ocr.Jenis_Kelamin, rate.Jenis_Kelamin if rate else None, duc.Jenis_Kelamin if duc else None),
        "bloodType":   field(ocr.Golongan_Darah, rate.Golongan_Darah if rate else None, None, has_duc_column=False),
        "address":     field(ocr.Alamat,       rate.Alamat if rate else None,       duc.Alamat if duc else None),
        "rt":          field(ocr.RT,           rate.RT if rate else None,           duc.RT if duc else None),
        "rw":          field(ocr.RW,           rate.RW if rate else None,           duc.RW if duc else None),
        "subdistrict": field(ocr.Kelurahan,    rate.Kelurahan if rate else None,    duc.Kelurahan if duc else None),
        "district":    field(ocr.Kecamatan,    rate.Kecamatan if rate else None,    duc.Kecamatan if duc else None),
        "city":        field(ocr.Kota,         rate.Kota if rate else None,         duc.Kota if duc else None),
        "province":    field(ocr.Provinsi,     rate.Provinsi if rate else None,     duc.Provinsi if duc else None),
        "religion":    field(ocr.Agama,        rate.Agama if rate else None,        None, has_duc_column=False),
        "job":         field(ocr.Pekerjaan,    rate.Pekerjaan if rate else None,    duc.Pekerjaan if duc else None),
        "photo":       ocr.Foto or "",
        "signature":   ocr.Tanda_Tangan or "",
    }