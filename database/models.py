from dataclasses import dataclass, asdict
from typing import Optional
import hashlib
import re

@dataclass
class IssuanceRecord:
    id: Optional[int] = None
    department: str = ""
    category: str = ""
    issuance_number: str = ""
    title: str = ""
    publication_date: str = ""
    source_url: str = ""
    extraction_timestamp: str = ""

    def generate_duplicate_hash(self) -> str:
        """
        Generates a robust duplicate key using department, category,
        normalized issuance number, and normalized title.
        Preserves original values in the record while using normalized
        strings for duplicate comparison.
        """
        norm_dept = (self.department or "").strip().lower()
        norm_cat = (self.category or "").strip().lower()
        
        raw_num = (self.issuance_number or "").lower()
        norm_num = re.sub(r'[^\w]', '', raw_num).replace('_', '')
        
        raw_title = (self.title or "").lower()
        norm_title = re.sub(r'[^\w]', '', raw_title).replace('_', '')
        
        raw_key = f"{norm_dept}|{norm_cat}|{norm_num}|{norm_title}"
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def to_dict(self):
        return asdict(self)
