import math
import re
from datetime import date, datetime
from flask import current_app, session
from sqlalchemy import text
from typing import Optional

from app import db
from app.utils.helpers.aws_helpers import _aws_delete
from app.utils.helpers.base_format import _access_level, _branch, _emp_id, fetch_subordinate_ids, fmt_date, format_threshold, num

def _apless_for_prechecking(prechecking_id: str) -> str:
    if not prechecking_id:
        return ""
    row = db.session.execute(
        text("""
            SELECT TOP 1 Apless FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND ISNULL(Apless, '') <> ''
            ORDER BY CreatedDate DESC
        """),
        {"pid": prechecking_id},
    ).fetchone()
    return (row.Apless or "") if row else ""

def _apply(cell, font=None, alignment=None, border=None, fill=None):
    if font:      cell.font      = font
    if alignment: cell.alignment = alignment
    if border:    cell.border    = border
    if fill:      cell.fill      = fill

def _assign_doc_types(owner_tokens: list, prefix: str, available: dict):
    assigned = [[f"{prefix}{t}"] if t and f"{prefix}{t}" in available else [] for t in owner_tokens]
    used = {t for types in assigned for t in types}
    leftover = [t for t in available if t not in used]
    missing = [i for i, types in enumerate(assigned) if not types]
    if len(missing) == 1 and len(leftover) == 1:
        assigned[missing[0]] = [leftover[0]]
        leftover = []
    return assigned, leftover

def _bit(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if _s(value) in ("True", "true", "1") else 0

def _blank(value):
    if value is None:
        return '-'
    value = str(value).strip()
    return value if value else '-'

def _build_common_filter(scope: dict, start_date: Optional[date], end_date: Optional[date],
                          lessee_nm: str) -> tuple[str, list]:
    clauses = []
    params: list = []

    if scope['cmo_filter'] is not None:
        placeholders = ','.join('?' for _ in scope['cmo_filter'])
        clauses.append(f"a.CMO IN ({placeholders})")
        params.extend(scope['cmo_filter'])

    if not scope['show_all_branches'] and scope['branch']:
        clauses.append("a.BRANCH_CD = ?")
        params.append(scope['branch'])

    if start_date and end_date:
        clauses.append("CAST(a.CREATE_DATE AS DATE) >= ? AND CAST(a.CREATE_DATE AS DATE) <= ?")
        params.append(start_date)
        params.append(end_date)

    if lessee_nm:
        clauses.append("b.LESSEE_NM LIKE ?")
        params.append(f"%{lessee_nm}%")

    if not clauses:
        return "1=1", []
    return " AND ".join(clauses), params

def _calc_as_of():
  
    today = date.today()
    year = today.year
    year_plus1 = year + 1
    year_minus1 = year - 1

    range1_start = date(year, 8, 1)
    range1_end = date(year_plus1, 1, 31)

    range2_start = date(year, 2, 1)
    range2_end = date(year, 7, 31)

    if range1_start <= today <= range1_end:
        return f"30 Juni {year}", date(year, 6, 30)
    elif range2_start <= today <= range2_end:
        return f"31 Desember {year_minus1}", date(year_minus1, 12, 31)
    else:
        return "", None

def _carried_source_filename(source_name: str) -> str:
    stripped = re.sub(r"^[^-]*-[A-Z0-9_]+-", "", source_name or "", count=1)
    return stripped or (source_name or "document")

def _carro(value) -> int:
    return 1 if _s(value) in ("1", "True", "true") else 0

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

def _citizen_of(rec) -> str:
    if not rec:
        return ""
    return "WNA" if _s(rec.get("Citizen")).upper() == "WNA" else "WNI"

def _clean_db_value(value):
    if isinstance(value, str) and value.strip().upper() == "NULL":
        return None
    return value

def _clean_row(mapping) -> dict:
    return {k: _clean_db_value(v) for k, v in dict(mapping).items()}

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

def _clear_person(prechecking_id: str, ocr_for: str, keep_id=None) -> None:
    rows = db.session.execute(text("""
        SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND OCR_For = :ocr_for
    """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchall()
    _delete_ocr_ids([r.Id for r in rows if r.Id != keep_id])

def _current_username() -> str:
    return session.get("username", "")

def _delete_doc_rows(rows) -> list:
    for r in rows:
        db.session.execute(text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
                           {"id": r.CustomerDocumentId})
    return [r.AWSKey for r in rows if r.AWSKey]

def _delete_ocr_ids(ids) -> None:
    for ocr_id in ids:
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Dukcapil WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR_Rate WHERE Id = :id"), {"id": ocr_id})
        db.session.execute(text("DELETE FROM TEMP_CAFLESS_OCR WHERE Id = :id"), {"id": ocr_id})

def _delete_s3_keys(keys) -> None:
    for key in dict.fromkeys(keys):
        try:
            _aws_delete(key)
        except Exception:
            current_app.logger.exception("S3 delete failed for %s", key)

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

def _dob_to_sql(value):
    v = _s(value)
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def _doc_row(key, label, files_by_type):
    return {"key": key, "label": label, "files": files_by_type.get(key, [])}

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

def _edit_link_params(r: dict) -> dict:
    cons_leas = (r.get('Cons_Leas') or '').strip()
    fin_type = cons_leas or None
    guarantor = 2 if r.get('HAS_GUARANTOR') == '1' else 1
    ind_cor = 2 if r.get('LESSEE_TP') == 'PT' else 1
    c2c = 1 if str(r.get('SUPP')) == '999999' else 0
    condition = (r.get('CONDITION') or '').strip()
    new_car = 2 if condition == 'NEW' else 1

    return {
        'id1': fin_type, 'id2': ind_cor, 'id3': 1, 'id4': guarantor, 'id5': new_car,
        'id6': 'Edit', 'id7': r.get('TENOR'), 'id8': c2c,
        'apless': r.get('APLESS'), 'applno': r.get('APPL_NO'),
    }

def _exec_rows(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def _exec_scalar(sql: str, params: list):
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        cursor.close()

def _exec_sp(sp_name: str, params: list) -> list[dict]:
   
    placeholders = ', '.join(['?'] * len(params))
    sql          = f"EXEC {sp_name} {placeholders}"

    raw_conn = db.session.connection().connection
    cursor   = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        while cursor.description is None:
            if not cursor.nextset():
                return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def _exec_write(sql: str, params: list) -> None:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()

def _fetch_combo(cat_value: str):
    rows = db.session.execute(text(
        "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat"
    ), {"cat": cat_value}).fetchall()
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _fetch_ratio_rows(ratio: str, tahun: str) -> list:
    rows = db.session.execute(
        text("""
            SELECT
                a.Ratio                                                       AS ratio_val,
                i.DESC_VALUE                                                  AS remark_desc,
                a.Remark                                                      AS remark_val,
                a.As_Of,
                CASE WHEN a.Ratio IN ('1','5') THEN z.DESC_VALUE ELSE CAST(a.Actual_From AS VARCHAR(20)) END AS actual_from,
                CASE WHEN a.Ratio IN ('1','5') THEN x.DESC_VALUE ELSE CAST(a.Actual_To   AS VARCHAR(20)) END AS actual_to,
                CASE WHEN a.Ratio IN ('1','5') THEN d.DESC_VALUE ELSE CAST(a.Thresholder_Level_From AS VARCHAR(20)) END AS ojk_from,
                CASE WHEN a.Ratio IN ('1','5') THEN e.DESC_VALUE ELSE CAST(a.Threshold_Level_To     AS VARCHAR(20)) END AS ojk_to,
                f.fullname AS created_by,
                a.Created_Date,
                g.fullname AS update_by,
                a.Update_Date
            FROM Ratio a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO d WITH(NOLOCK) ON d.VALUE = a.Thresholder_Level_From AND d.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO e WITH(NOLOCK) ON e.VALUE = a.Threshold_Level_To     AND e.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO z WITH(NOLOCK) ON z.VALUE = a.Actual_From            AND z.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO x WITH(NOLOCK) ON x.VALUE = a.Actual_To              AND x.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO i WITH(NOLOCK) ON i.VALUE = a.Remark                 AND i.CAT_VALUE = 'REMARK_THRS'
                LEFT JOIN APP_USRMST f WITH(NOLOCK) ON f.employee_id = a.Created_By
                LEFT JOIN APP_USRMST g WITH(NOLOCK) ON g.employee_id = a.Update_By
            WHERE a.Ratio = :ratio AND YEAR(a.As_Of) = :tahun
            ORDER BY a.As_Of
        """),
        {"ratio": ratio, "tahun": int(tahun)}
    ).fetchall()

    result = []
    for r in rows:
        update_by   = r.update_by   or "-"
        update_date = fmt_date(r.Update_Date, "%d-%m-%Y") or "-"
        result.append({
            "as_of":        fmt_date(r.As_Of, "%B %Y"),
            "remark_desc":  r.remark_desc or "",
            "actual":       format_threshold(r.ratio_val, r.remark_val, r.actual_from or "", r.actual_to   or ""),
            "ojk":          format_threshold(r.ratio_val, r.remark_val, r.ojk_from    or "", r.ojk_to      or ""),
            "created_by":   r.created_by   or "",
            "created_date": fmt_date(r.Created_Date, "%d-%m-%Y"),
            "update_by":    update_by,
            "update_date":  update_date,
        })
    return result

def _fetch_sales(as_of: date, search: str) -> list[dict]:
    first_date = date(as_of.year, 1, 1)

    where = [
        "d.NPWP_Type IN ('PR', '00')",
        "c.Category = 'SALES'",
        "d.Category = 'SALES'",
        "c.AccountType = 'C'",
        "e.EXECUTION IS NOT NULL",
        "a.SD_TYPE = 'S'",
        "e.EXECUTION BETWEEN ? AND ?",
    ]
    params: list = [first_date, as_of]

    top_clause = ""
    if search:
        where.append("b.NAME LIKE ?")
        params.append(f"%{search}%")
    else:
        top_clause = "TOP 200"

    sql = f"""
        SELECT {top_clause}
            c.BeneficiaryID AS RegNo,
            'Individual' AS Type,
            b.NAME AS CommRecvName,
            b.ADDRESS AS CommRecvAddress,
            d.NPWP_Start AS Npwp,
            ISNULL(d.NPWP_No, '') AS NpwpNumber
        FROM CAFKOMIS a WITH (NOLOCK)
            INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO = b.SALES_NO
            INNER JOIN BeneficiaryAccount c ON b.SALES_NO = c.BeneficiaryID
            INNER JOIN BeneficiaryTax d ON b.SALES_NO = d.BeneficiaryID
            INNER JOIN CLFCONT e ON a.APPL_NO = e.APPL_NO
        WHERE {' AND '.join(where)}
        GROUP BY c.BeneficiaryID, b.NAME, b.ADDRESS, d.NPWP_Start, d.NPWP_No
        ORDER BY b.NAME
    """
    rows = _exec_rows(sql, params)
    return [
        {
            'reg_no': r.get('RegNo'),
            'type': r.get('Type'),
            'name': r.get('CommRecvName') or '-',
            'address': r.get('CommRecvAddress') or '-',
            'npwp': _fmt_value(r.get('Npwp')),
            'npwp_number': r.get('NpwpNumber') or '-',
        }
        for r in rows
    ]

def _fmt_date(val) -> str:
   
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return str(val) if val is not None else ''

def _fmt_value(val):
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return val

def _format_npwp(npwp: Optional[str]) -> str:
    if not npwp:
        return '-'
    return (f"{npwp[0:2]}.{npwp[2:5]}.{npwp[5:8]}.{npwp[8:9]}"
            f"-{npwp[9:12]}.{npwp[12:16]}")

def _get_session_ctx() -> dict:
    return {
        "emp_id":       session.get("emp_id", ""),
        "username":     session.get("username", ""),
        "access_level": session.get("accesslevel", ""),
        "branch_cd":    session.get("branchcode", ""),
    }

def _has_document(prechecking_id: str, document_type: str) -> bool:
    row = db.session.execute(text("""
        SELECT TOP 1 CustomerDocumentId FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": document_type}).fetchone()
    return row is not None

def _is_wna(rec) -> bool:
    return _s(rec.get("Citizen")).upper() == "WNA"

def _lookup_apless(name: str, address: str) -> str:
    row = db.session.execute(
        text("SELECT apless FROM cafless WITH(NOLOCK) WHERE LESSEE_NM LIKE :name AND [address1] LIKE :address"),
        {"name": name, "address": address}
    ).fetchone()
    return row.apless if row and row.apless else "nonMLCI"

def _num(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def _ocr_for_of(check_for: str) -> str:
    return "G"

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

def _ratio_title(ratio: str) -> str:
    row = db.session.execute(
        text("SELECT DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'RATIO' AND VALUE = :v"),
        {"v": ratio}
    ).fetchone()
    return row.DESC_VALUE if row else ratio

def _record_upload_audit_log(username: str, applno: str, apless: str, document_type: str, file_name: str) -> None:
    pass

def _render_rows_html(rows: list[dict]) -> str:
    if not rows:
        return ('<tr><td colspan="11" align="center" style="border:thin solid #000">'
                '<font color="red"><b>Data Not Found</b></font></td></tr>')
    parts = []
    for d in rows:
        parts.append(f"""
            <tr>
                <td style="border:thin solid #000" align="center">{d['no']}</td>
                <td style="border:thin solid #000">{d['cam_no']}</td>
                <td style="border:thin solid #000">{d['customer_name']}</td>
                <td style="border:thin solid #000">{d['brand_type']}</td>
                <td style="border:thin solid #000" align="right">{d['net_finance']:,.0f}</td>
                <td style="border:thin solid #000" align="right">{d['total_outstanding']:,.0f}</td>
                <td style="border:thin solid #000" align="right">{d['interest']:.4f}</td>
                <td style="border:thin solid #000" align="center">{d['tenor']}</td>
                <td style="border:thin solid #000">{d['create_date']}</td>
                <td style="border:thin solid #000">{d['cmo']}</td>
                <td style="border:thin solid #000">{d['status']}</td>
            </tr>""")
    return ''.join(parts)

def _resolve_scope(requested_branch: str) -> dict:
    access_level = _access_level()
    emp_id = _emp_id()
    own_branch_cd = _branch()
    is_ho = (own_branch_cd == '100')

    branch = (requested_branch or '000') if is_ho else own_branch_cd

    if access_level == 'CMO':
        cmo_filter = [emp_id]
    elif access_level == 'CMH':
        cmo_filter = fetch_subordinate_ids(emp_id)
    else:
        cmo_filter = None

    return {
        'disabled': not is_ho,
        'branch': branch,
        'cmo_filter': cmo_filter,
        'show_all_branches': branch == '000',
    }

def _retype_docs(prechecking_id: str, old_type: str, new_type: str) -> None:
    if old_type and new_type and old_type != new_type:
        db.session.execute(text("""
            UPDATE TEMP_CUSTOMER_DOCUMENT SET DocumentType = :new
            WHERE Prechecking_Id = :pid AND DocumentType = :old
        """), {"pid": prechecking_id, "old": old_type, "new": new_type})

def _row_to_detail(r: dict, no: int, revision: str) -> dict:
    create_date = r.get('CREATE_DATE')
    brand = (r.get('BRAND_NM') or '').strip()
    type_nm = (r.get('TYPE_NM') or '').strip()
    return {
        'no': no,
        'cam_no': f"{r.get('Cons_Leas')} - {r.get('APPL_NO')}{revision}",
        'appl_no': r.get('APPL_NO'),
        'customer_name': r.get('LESSEE_NM') or '-',
        'brand_type': f"{brand} / {type_nm}" if (brand or type_nm) else '-',
        'net_finance': num(r.get('Net_Finance')),
        'total_outstanding': num(r.get('tot_outs')),
        'interest': round(num(r.get('DECLRATE')), 4),
        'tenor': int(num(r.get('TENOR'))),
        'create_date': create_date.strftime('%d-%m-%Y') if create_date else '',
        'cmo': r.get('cmo') or '-',
        'status': r.get('approver') or '-',
        'is_revision': bool(revision),
        'edit_link_params': _edit_link_params(r),
    }

def _s(value) -> str:
    return "" if value is None else str(value).strip()

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

def _session_str(key: str) -> str:
    return session.get(key, "") or ""

def _sql_date(value: str):
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def _strip_special(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', value or '')

def _token(value) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", _s(value))

def _truthy_bit(value) -> bool:
    return value not in (None, "", 0, "0", False)

def _validate_members(members: list) -> list:
    errors = []
    for entry in members:
        name = (entry.get('name') or '').strip()
        if not name:
            continue
        if not (entry.get('bod_position') or '').strip() and not (entry.get('boc_position') or '').strip():
            errors.append(f"BOD or BOC position must be selected for {name}")
    return errors

def _wna_signature(name, id_no, id_type) -> dict:
    return {"citizen": "WNA", "id_type": id_type, "idCardNo": _s(id_no), "name": _s(name)}

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

def format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.year == 2011:
            return ""
        return value.strftime("%d-%m-%Y %H:%M:%S")
    return str(value)

def join_nonempty(*values, sep=', '):
    parts = [str(v) for v in values if v not in (None, '')]
    return sep.join(parts) if parts else '-'

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

def pangkat(x: float, n: float) -> float:
    return math.exp(n * math.log(x))
