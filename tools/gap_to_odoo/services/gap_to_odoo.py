import logging
import pandas as pd

HOURS_PER_DAY = 7.0
EXCEL_COLUMN_NAMES = ["Flux", "Sujet", "Light", "MVP", "Full", "Choix", "Description précise fonctionnelle", "Ateliers / Paramétrage", "Coordination / Modélisation", "Développement"]
ODOO_COLUMN_NAMES = ["type_id.name", "allocated_hours", "name", "flux", "subject", "tag_ids.name"]
EXCLUDED_CHOICES = ["N/A", "NA", "DROP", "Drop", "drop", "na", "n/a"]

logger = logging.getLogger(__name__)

def ret_to_str(val) -> str:
    return str(val) if val is not None else ""

def ret_time_odoo(val) -> tuple[float, bool]:
    if pd.isna(val):
        return (0, False)
    elif isinstance(val, (int, float)):
        return (float(val) * HOURS_PER_DAY, True)
    else:
        return (float(val) * HOURS_PER_DAY, True)
    
def ret_choice_str(val) -> str:
    if pd.isna(val):
        return ""
    elif isinstance(val, str) and val.strip() in EXCLUDED_CHOICES:
        return ""
    else:
        return str(val)

def ret_categ_bool(val) -> bool:
    if pd.isna(val):
        return False
    elif isinstance(val, str) and "x" in val.strip().lower():
        return True
    else:
        return False

COLUMN_MAPPING = {
    "Flux": ret_to_str,
    "Light": ret_categ_bool,
    "MVP": ret_categ_bool,
    "Full": ret_categ_bool,
    "Choix": ret_choice_str,
    "Description précise fonctionnelle": ret_to_str,
    "Ateliers / Paramétrage": ret_time_odoo,
    "Coordination / Modélisation": ret_time_odoo,
    "Développement": ret_time_odoo
}

def gap_to_odoo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms a DataFrame from GAP format to Odoo format.
    
    This is a placeholder implementation. The actual transformation logic
    will depend on the specific formats of the input and output data.
    
    Args:
        df: A pandas DataFrame in GAP format.

    Returns:
        A pandas DataFrame in Odoo format.
    """
    # Filter out excluded choices
    df_filtered = df[~df["Choix"].isin(EXCLUDED_CHOICES)].copy()
    # Log the filtered DataFrame
    logger.info("Filtered DataFrame:")
    logger.info("\n%s", df_filtered)
    
    # Apply transformations
    transformed_data = []
    
    for _, row in df_filtered.iterrows():
        if not row.get("Description précise fonctionnelle") or pd.isna(row.get("Description précise fonctionnelle")):
            continue
        # Process time columns and sum hours
        dev_hours, dev_valid = ret_time_odoo(row.get("Développement"))
        atel_hours, _ = ret_time_odoo(row.get("Ateliers / Paramétrage"))
        coord_hours, _ = ret_time_odoo(row.get("Coordination / Modélisation"))
        is_light = ret_categ_bool(row.get("Light"))
        is_mvp = ret_categ_bool(row.get("MVP"))
        is_full = ret_categ_bool(row.get("Full"))

        total_hours = dev_hours + atel_hours + coord_hours
        if total_hours == 0 and not (is_light or is_mvp or is_full):
            continue
        # Determine type_id.name based on development hours
        type_id_name = "Développement" if dev_valid else "Fonctionnel"
        
        # Build tag_ids.name list
        tags = []
        choice_val = ret_choice_str(row.get("Choix"))
        if choice_val:
            tags.append(choice_val)
        
        # Build transformed row
        transformed_row = {
            "flux": ret_to_str(row.get("Flux")),
            "subject": ret_to_str(row.get("Sujet")),
            "type_id.name": type_id_name,
            "name": ret_to_str(row.get("Description précise fonctionnelle")),
            "allocated_hours": total_hours,
            "tag_ids.name": ",".join(tags) if tags else ""
        }
        
        transformed_data.append(transformed_row)
    
    result_df = pd.DataFrame(transformed_data)
    return result_df[ODOO_COLUMN_NAMES]
