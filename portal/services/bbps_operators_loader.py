"""
BBPS operators – DB first (portal_bbps_operator), Excel fallback for backward compatibility.
Used by Mobikwik and Euronet Bharat Bill services. Load Excel into DB via: manage.py load_bbps_operators.
"""
import os
from typing import Any, Dict, List, Optional

from django.conf import settings


def _operator_row_to_dict(operator: "BBPSOperator") -> Dict[str, Any]:
    """Convert BBPSOperator model instance to legacy dict shape (op, operator_id, name, etc.)."""
    op_val = operator.op
    if op_val and str(op_val).isdigit():
        op_val = int(op_val)
    return {
        "op": op_val,
        "operator_id": operator.biller_id,
        "biller_id": operator.biller_id,
        "name": operator.name or "Unknown",
        "category": operator.category or "",
        "view_bill": operator.view_bill or "",
        "customer_label": operator.customer_label or "Consumer ID",
        "regex": operator.regex,
        "ad1": operator.ad1,
        "ad2": operator.ad2,
        "ad3": operator.ad3,
        "ad4": operator.ad4,
        "ad9": operator.ad9,
        "additional_params": operator.additional_params,
    }


def load_bbps_operators_from_db(
    bbps_enabled_only: bool = True,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load operators from DB (portal_bbps_operator). Returns same dict shape as load_bbps_operators_from_excel.
    """
    from portal.models import BBPSOperator

    qs = BBPSOperator.objects.filter(is_active=True)
    if bbps_enabled_only:
        qs = qs.filter(bbps_enabled=True)
    if category:
        qs = qs.filter(category__iexact=category.strip())
    return [_operator_row_to_dict(op) for op in qs.order_by("category", "name")]


def get_operators_excel_path() -> Optional[str]:
    """Return path to Operators.xlsx (in Mobikwik folder)."""
    base = getattr(settings, "BASE_DIR", None)
    if not base:
        return None
    path = os.path.join(base, "Mobikwik", "Operators.xlsx")
    return path if os.path.isfile(path) else None


def load_bbps_operators_from_excel(
    bbps_enabled_only: bool = True,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load operators: DB first, then Excel if DB has none. Same dict shape for BBPS API.
    """
    from portal.models import BBPSOperator

    # Prefer DB (after running load_bbps_operators)
    if BBPSOperator.objects.exists():
        return load_bbps_operators_from_db(bbps_enabled_only=bbps_enabled_only, category=category)

    path = get_operators_excel_path()
    if not path:
        return []

    try:
        import pandas as pd
    except ImportError:
        return []

    try:
        df = pd.read_excel(path, sheet_name="Operator")
    except Exception:
        return []

    if df.empty:
        return []

    # Normalize column names (strip spaces)
    df.columns = [str(c).strip() for c in df.columns]

    if bbps_enabled_only and "BBPS Enabled" in df.columns:
        col = df["BBPS Enabled"]
        mask = col.fillna(False).astype(str).str.upper().str.strip().isin(("TRUE", "1", "YES"))
        df = df[mask]

    if category:
        cat_col = "Category"
        if cat_col in df.columns:
            df = df[df[cat_col].astype(str).str.strip().str.upper() == str(category).strip().upper()]

    # Mobikwik API expects "op" as Integer; try column "op" or common alternatives
    def _get_op_value(row: Any) -> Any:
        for col in ("op", "Operator Id", "Operator ID", "OperatorId", "Mobikwik Op"):
            v = row.get(col)
            if v is not None and not (hasattr(v, "__iter__") and not isinstance(v, str) and pd.isna(v)):
                s = str(v).strip()
                if s.isdigit():
                    return int(s)
                if s:
                    return s
        return row.get("op")

    operators = []
    for _, row in df.iterrows():
        biller_id = row.get("Biller ID")
        if pd.isna(biller_id) or not str(biller_id).strip():
            continue
        op = _get_op_value(row)
        op_name = row.get("Operator Name", "")
        cat = row.get("Category", "")
        view_bill = str(row.get("ViewBill", "")).strip() if pd.notna(row.get("ViewBill")) else ""
        name_label = row.get("Name", "") or row.get("cn", "")  # Customer ID field label
        regex = row.get("Regex")
        ad1 = row.get("ad1 with regex") if "ad1 with regex" in row else row.get("ad1")
        ad2 = row.get("ad2")
        ad3 = row.get("ad3")
        ad4 = row.get("ad4")
        ad9 = row.get("ad9")
        additional_params = row.get("Additional Params for payment API")

        def _val(v) -> Optional[str]:
            if v is None or (hasattr(v, "__iter__") and not isinstance(v, str) and pd.isna(v)):
                return None
            s = str(v).strip()
            return s if s else None

        operators.append({
            "op": op if isinstance(op, int) else _val(op),
            "operator_id": str(biller_id).strip(),
            "biller_id": str(biller_id).strip(),
            "name": _val(op_name) or "Unknown",
            "category": _val(cat) or "",
            "view_bill": view_bill,
            "customer_label": _val(name_label) or "Customer ID",
            "regex": _val(regex),
            "ad1": _val(ad1),
            "ad2": _val(ad2),
            "ad3": _val(ad3),
            "ad4": _val(ad4),
            "ad9": _val(ad9),
            "additional_params": _val(additional_params),
        })

    return operators


def get_bbps_categories() -> List[str]:
    """Return list of unique categories: DB first (BBPS enabled), else from Excel."""
    from portal.models import BBPSOperator

    if BBPSOperator.objects.filter(bbps_enabled=True, is_active=True).exists():
        return sorted(
            BBPSOperator.objects.filter(bbps_enabled=True, is_active=True)
            .values_list("category", flat=True)
            .distinct()
        )

    path = get_operators_excel_path()
    if not path:
        return []
    try:
        import pandas as pd
        df = pd.read_excel(path, sheet_name="Operator")
        df.columns = [str(c).strip() for c in df.columns]
        if "BBPS Enabled" in df.columns:
            col = df["BBPS Enabled"]
            mask = col.fillna(False).astype(str).str.upper().str.strip().isin(("TRUE", "1", "YES"))
            df = df[mask]
        if "Category" not in df.columns:
            return []
        cats = df["Category"].dropna().astype(str).str.strip().unique().tolist()
        return sorted([c for c in cats if c])
    except Exception:
        return []
