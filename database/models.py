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
        norm_dept = self.department.strip().lower()
        norm_cat = self.category.strip().lower()
        # Normalize whitespace and lowercase for comparison only
        norm_num = re.sub(r'\s+', ' ', self.issuance_number.strip().lower())
        norm_title = re.sub(r'\s+', ' ', self.title.strip().lower())
        
        raw_key = f"{norm_dept}|{norm_cat}|{norm_num}|{norm_title}"
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def to_dict(self):
        return asdict(self)
