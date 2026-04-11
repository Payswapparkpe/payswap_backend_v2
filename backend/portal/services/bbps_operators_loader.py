"""
BBPS operators – DB first (portal_bbps_operator), Excel fallback for backward compatibility.
Used by Mobikwik and Euronet Bharat Bill services. Load Excel into DB via: manage.py load_bbps_operators.
"""
import os
import re
from typing import Any, Dict, List, Optional

from django.conf import settings

# Map Excel category variants to canonical BBPS categories (UPPER_UNDERSCORE).
# Used when loading Excel into DB and when reading from Excel (get_bbps_categories, load_bbps_operators_from_excel).
CATEGORY_CANONICAL_MAP: Dict[str, str] = {
    "WATER": "WATER",
    "WATER_SUPPLIER": "WATER",
    "WATERSUPPLIER": "WATER",
    "MUNICIPAL_TAXES": "MUNICIPAL_TAXES",
    "MUNICIPALITY": "MUNICIPAL_TAXES",
    "MUNCIPAL": "MUNICIPAL_TAXES",  # typo in Excel
    "MUNICIPAL": "MUNICIPAL_TAXES",
    "EMI": "EMI_PAYMENT",
    "EMI_PAYMENT": "EMI_PAYMENT",
    "CREDIT_CARD": "CREDIT_CARD",
    "CREDITCARDPAY": "CREDIT_CARD",
    "CREDIT_CARD_PAY": "CREDIT_CARD",
    "PREPAID": "PREPAID",
    "POSTPAID": "POSTPAID",
}

DEFAULT_OPERATOR_FILES = (
    os.path.join("mobikwik", "Operators (13).xlsx"),
    os.path.join("Mobikwik", "Operators (13).xlsx"),
    os.path.join("mobikwik", "Operators.xlsx"),
    os.path.join("Mobikwik", "Operators.xlsx"),
)


def _normalize_category_raw(raw: str) -> str:
    """Normalize category string to UPPER_UNDERSCORE (no canonical mapping)."""
    return (raw or "").strip().upper().replace(" ", "_")


def canonical_category(normalized: str) -> str:
    """Return canonical category for DB/API; if no mapping, return normalized as-is."""
    if not normalized:
        return ""
    return CATEGORY_CANONICAL_MAP.get(normalized, normalized)


def _is_na(value: Any, pd: Any = None) -> bool:
    if value is None:
        return True
    if pd is not None:
        try:
            return bool(pd.isna(value))
        except Exception:
            pass
    return False


def _val(value: Any, default: Optional[str] = None, pd: Any = None) -> Optional[str]:
    if _is_na(value, pd=pd):
        return default
    s = str(value).strip()
    return s if s else default


def _is_trueish(value: Any, pd: Any = None) -> bool:
    if _is_na(value, pd=pd):
        return False
    return str(value).strip().upper() in ("TRUE", "1", "YES")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Z0-9]+", "_", (text or "").upper()).strip("_")
    return s[:24] if s else "OP"


def _build_fastag_biller_id(op_val: Optional[str], name: Optional[str], hint: Optional[str] = None) -> str:
    seed = (hint or name or "FASTAG").strip()
    return f"FASTAG_{(op_val or 'OP').strip()}_{_slug(seed)}"


def _extract_op_value(row: Dict[str, Any], pd: Any = None) -> Optional[str]:
    for col in ("op", "Operator Id", "Operator ID", "OperatorId", "Mobikwik Op"):
        if col not in row:
            continue
        v = row.get(col)
        if _is_na(v, pd=pd):
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _is_operator_like_columns(columns: List[str]) -> bool:
    cols = {str(c).strip() for c in columns}
    required_signals = {"Operator Name", "Category"}
    biller_signals = {"Biller ID", "op", "Operator Id", "Operator ID", "OperatorId", "Mobikwik Op"}
    return bool(required_signals.intersection(cols)) and bool(biller_signals.intersection(cols))


def _normalize_operator_row(
    row: Dict[str, Any],
    *,
    pd: Any = None,
    bbps_enabled_only: bool = True,
    category_filter: Optional[str] = None,
) -> (Optional[Dict[str, Any]], Optional[str]):
    if bbps_enabled_only and "BBPS Enabled" in row and not _is_trueish(row.get("BBPS Enabled"), pd=pd):
        return None, "bbps_disabled"

    op_val = _extract_op_value(row, pd=pd)
    name = _val(row.get("Operator Name"), "Unknown", pd=pd)
    cat_raw = _val(row.get("Category"), "", pd=pd)
    cat_normalized = _normalize_category_raw(cat_raw or "")
    cat = canonical_category(cat_normalized) or cat_normalized

    if category_filter and cat != category_filter:
        return None, "category_mismatch"

    biller_id = _val(row.get("Biller ID"), None, pd=pd)
    if not biller_id:
        if op_val and "FASTAG" in (cat or ""):
            ad1_hint = _val(row.get("ad1"), None, pd=pd) or _val(row.get("ad1 with regex"), None, pd=pd) or ""
            biller_id = _build_fastag_biller_id(op_val, name, hint=(name or ad1_hint))
        else:
            return None, "missing_biller_id"

    view_bill = _val(row.get("ViewBill"), "", pd=pd)
    circle = _val(row.get("Circle"), None, pd=pd) or _val(row.get("cir"), None, pd=pd) or _val(row.get("Circle Code"), "", pd=pd)
    name_label = _val(row.get("Name"), None, pd=pd) or _val(row.get("cn"), "Consumer ID", pd=pd)
    regex = _val(row.get("Regex"), None, pd=pd)
    ad1 = _val(row.get("ad1 with regex"), None, pd=pd) if "ad1 with regex" in row else _val(row.get("ad1"), None, pd=pd)
    ad2 = _val(row.get("ad2"), None, pd=pd)
    ad3 = _val(row.get("ad3"), None, pd=pd)
    ad4 = _val(row.get("ad4"), None, pd=pd)
    ad9 = _val(row.get("ad9"), None, pd=pd)
    additional_params = _val(row.get("Additional Params for payment API"), None, pd=pd)

    op_clean = _val(op_val, None, pd=pd)
    return {
        "op": op_clean,
        "operator_id": biller_id,
        "biller_id": biller_id,
        "name": name or "Unknown",
        "category": cat or "",
        "view_bill": view_bill or "",
        "circle": circle or "",
        "customer_label": name_label or "Consumer ID",
        "regex": regex,
        "ad1": ad1,
        "ad2": ad2,
        "ad3": ad3,
        "ad4": ad4,
        "ad9": ad9,
        "additional_params": additional_params,
        "bbps_enabled": _is_trueish(row.get("BBPS Enabled"), pd=pd) if "BBPS Enabled" in row else True,
    }, None


def parse_operator_workbook(
    path: str,
    *,
    bbps_enabled_only: bool = True,
    category: Optional[str] = None,
    sheet_names: Optional[List[str]] = None,
    include_sheets: Optional[List[str]] = None,
    exclude_sheets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Parse BBPS operators from workbook sheets using shared normalization logic.
    Returns operators + per-sheet stats.
    """
    try:
        import pandas as pd
    except ImportError:
        return {"operators": [], "sheet_stats": {}, "error": "pandas_import_error"}

    include_set = set(s.strip() for s in include_sheets or [] if str(s).strip())
    exclude_set = set(s.strip() for s in exclude_sheets or [] if str(s).strip())
    category_param = str(category).strip().upper() if category else None

    try:
        xls = pd.ExcelFile(path)
    except Exception:
        return {"operators": [], "sheet_stats": {}, "error": "excel_open_error"}

    selected_sheets = list(sheet_names or xls.sheet_names)
    if include_set:
        selected_sheets = [s for s in selected_sheets if s in include_set]
    if exclude_set:
        selected_sheets = [s for s in selected_sheets if s not in exclude_set]

    operators: List[Dict[str, Any]] = []
    sheet_stats: Dict[str, Dict[str, int]] = {}

    for sheet in selected_sheets:
        stats = {"rows": 0, "parsed": 0, "skipped": 0, "rejected": 0}
        sheet_stats[sheet] = stats
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception:
            stats["rejected"] += 1
            continue
        if df is None or df.empty:
            continue

        df.columns = [str(c).strip() for c in df.columns]
        if not _is_operator_like_columns(list(df.columns)):
            stats["skipped"] += len(df.index)
            continue

        for _, raw_row in df.iterrows():
            stats["rows"] += 1
            row = raw_row.to_dict() if hasattr(raw_row, "to_dict") else dict(raw_row)
            op_data, reason = _normalize_operator_row(
                row,
                pd=pd,
                bbps_enabled_only=bbps_enabled_only,
                category_filter=category_param,
            )
            if op_data:
                operators.append(op_data)
                stats["parsed"] += 1
            else:
                if reason in ("missing_biller_id",):
                    stats["rejected"] += 1
                else:
                    stats["skipped"] += 1

    # Deduplicate by biller_id, keeping last occurrence.
    dedup: Dict[str, Dict[str, Any]] = {}
    fastag_seen: set = set()
    for op in operators:
        cat = str(op.get("category") or "").upper()
        if cat == "FASTAG":
            sign = (str(op.get("op") or "").strip(), str(op.get("name") or "").strip().upper())
            if sign in fastag_seen:
                continue
            fastag_seen.add(sign)
        key = str(op.get("biller_id") or "").strip()
        if not key:
            continue
        existing = dedup.get(key)
        # FASTAG rows often reuse biller IDs that collide with non-FASTAG rows.
        # Preserve FASTAG operator variants by assigning deterministic synthetic ids.
        if existing and (
            str(existing.get("category") or "").upper() == "FASTAG"
            or cat == "FASTAG"
        ):
            base_key = _build_fastag_biller_id(str(op.get("op") or ""), str(op.get("name") or "FASTAG"))
            key = base_key
            n = 2
            while key in dedup:
                key = f"{base_key}_{n}"
                n += 1
            op = dict(op)
            op["biller_id"] = key
            op["operator_id"] = key
        dedup[key] = op

    return {
        "operators": [v for _, v in dedup.items() if v.get("biller_id")],
        "sheet_stats": sheet_stats,
        "selected_sheets": selected_sheets,
    }


def _operator_row_to_dict(operator: "BBPSOperator") -> Dict[str, Any]:
    """Convert BBPSOperator model instance to legacy dict shape (op, operator_id, name, circle, etc.)."""
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
        "circle": getattr(operator, "circle", None) or "",
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
    """Return first matching operators workbook path from known locations."""
    base = getattr(settings, "BASE_DIR", None)
    if not base:
        return None
    for rel in DEFAULT_OPERATOR_FILES:
        path = os.path.join(base, rel)
        if os.path.isfile(path):
            return path
    return None


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

    parsed = parse_operator_workbook(
        path,
        bbps_enabled_only=bbps_enabled_only,
        category=category,
        sheet_names=["Operator"],
    )
    return parsed.get("operators") or []


def get_bbps_categories() -> List[str]:
    """Return list of unique categories: DB first (BBPS enabled), else from Excel."""
    from portal.models import BBPSOperator

    if BBPSOperator.objects.filter(bbps_enabled=True, is_active=True).exists():
        raw = list(
            BBPSOperator.objects.filter(bbps_enabled=True, is_active=True)
            .values_list("category", flat=True)
            .distinct()
        )
        # Deduplicate (e.g. if DB has "BROADBAND POSTPAID" and "BROADBAND_POSTPAID" before full normalize)
        return sorted(set(c for c in raw if c and str(c).strip()))

    path = get_operators_excel_path()
    if not path:
        return []
    try:
        parsed = parse_operator_workbook(path, bbps_enabled_only=True, sheet_names=["Operator"])
        ops = parsed.get("operators") or []
        return sorted(set(str(op.get("category") or "").strip() for op in ops if str(op.get("category") or "").strip()))
    except Exception:
        return []
