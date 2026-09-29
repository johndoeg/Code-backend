from flask import Blueprint, jsonify, redirect, request, session

from app.services.customer_document_service import (
    delete_customer_document,
    get_document_view_url,
    get_lessee_category,
    list_customer_documents,
    upload_customer_document,
)

customer_documents_bp = Blueprint(
    "customer_documents", __name__, url_prefix="/api/cam/customer-documents"
)

def _current_username() -> str:
    return session.get("username", "")

@customer_documents_bp.get("")
def get_customer_documents():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    organization_type = request.args.get("organization_type", "")
    if not (apless and applno and organization_type):
        return jsonify({"error": "apless, applno and organization_type are required"}), 400
    return jsonify(list_customer_documents(applno, apless, organization_type))

@customer_documents_bp.get("/lessee-category")
def get_lessee_category_route():
    apless = request.args.get("apless", "")
    if not apless:
        return jsonify({"error": "apless is required"}), 400
    return jsonify({"lessee_cat": get_lessee_category(apless)})

@customer_documents_bp.post("")
def post_customer_document():
    form = request.form
    apless = form.get("apless", "")
    applno = form.get("applno", "")
    organization_type = form.get("organization_type", "")
    document_type = form.get("document_type", "")
    prefix = form.get("prefix", "")
    subfolder = form.get("subfolder", "")
    grnid = form.get("grnid", "")
    max_file_size_mb = float(form.get("max_file_size_mb") or 0)

    if not (apless and applno and organization_type and document_type):
        return jsonify({"error": "apless, applno, organization_type and document_type are required"}), 400

    file_storage = request.files.get("file")
    error, doc = upload_customer_document(
        file_storage=file_storage,
        document_type=document_type,
        prefix=prefix,
        applno=applno,
        apless=apless,
        organization_type=organization_type,
        subfolder=subfolder,
        username=_current_username(),
        grnid=grnid,
        max_file_size_mb=max_file_size_mb,
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"document": doc}), 201

@customer_documents_bp.delete("/<int:id_customer_document>")
def delete_customer_document_route(id_customer_document: int):
    deleted = delete_customer_document(id_customer_document)
    if not deleted:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"deleted": True})

@customer_documents_bp.get("/<int:id_customer_document>/download")
def download_customer_document(id_customer_document: int):
    url = get_document_view_url(id_customer_document)
    if not url:
        return jsonify({"error": "Document not found"}), 404
    return redirect(url)

@customer_documents_bp.get("/<int:id_customer_document>/view")
def view_customer_document(id_customer_document: int):
    url = get_document_view_url(id_customer_document)
    if not url:
        return jsonify({"error": "Document not found"}), 404
    return redirect(url)