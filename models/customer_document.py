from app import db
from datetime import datetime, timezone

class CustomerDocument(db.Model):
    __tablename__ = "CUSTOMER_DOCUMENT"

    id_customer_document = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appl_no = db.Column("appl_no", db.String(50), nullable=False, index=True)
    apless = db.Column("APLESS", db.String(50), nullable=False, index=True)
    file_document = db.Column("file_document", db.String(255))
    organization_type = db.Column("organization_type", db.String(20))
    doc_no = db.Column("doc_no", db.Integer)
    doc_type = db.Column("doc_type", db.String(20))
    document_type = db.Column("DocumentType", db.String(50), index=True)
    upload_dt = db.Column("Upload_Dt", db.DateTime, default=lambda: datetime.now(timezone.utc))
    aws_key = db.Column("AWSKey", db.String(500))
    grnid = db.Column("GRNID", db.String(50))

    def to_dict(self) -> dict:
        return {
            "id": self.id_customer_document,
            "documentType": self.document_type,
            "fileName": self.file_document,
            "uploadedAt": self.upload_dt.isoformat() if self.upload_dt else None,
        }