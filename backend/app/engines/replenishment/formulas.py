import math
from typing import Tuple
from scipy.stats import norm


def get_z_score(service_level: float) -> float:
    """
    Computes standard normal distribution Z-score for cycle service level.
    e.g. 0.95 -> 1.645, 0.98 -> 2.054.
    """
    sl = max(0.50, min(0.999, service_level))
    return float(norm.ppf(sl))


def calculate_lead_time_demand(avg_daily_demand: float, avg_lead_time_days: float) -> float:
    """
    Computes expected demand during supplier replenishment turnaround: LTD = D_bar * L_bar.
    """
    return max(0.0, float(avg_daily_demand * avg_lead_time_days))


def calculate_safety_stock(
    avg_daily_demand: float,
    demand_std_dev: float,
    avg_lead_time_days: float,
    lead_time_std_dev: float,
    service_level: float = 0.95,
    min_safety_stock: int = 0,
    max_safety_stock: int | None = None,
) -> Tuple[int, float]:
    """
    Calculates safety stock considering both demand variability and lead-time variability:
    sigma_LTD = sqrt( L_bar * sigma_D^2 + D_bar^2 * sigma_L^2 )
    Safety Stock = ceil( Z * sigma_LTD )
    """
    z = get_z_score(service_level)
    L_bar = max(0.1, avg_lead_time_days)
    D_bar = max(0.0, avg_daily_demand)
    s_D = max(0.0, demand_std_dev)
    s_L = max(0.0, lead_time_std_dev)

    variance_ltd = (L_bar * (s_D ** 2)) + ((D_bar ** 2) * (s_L ** 2))
    sigma_ltd = math.sqrt(max(0.0, variance_ltd))

    raw_ss = math.ceil(z * sigma_ltd)
    ss = max(min_safety_stock, raw_ss)
    if max_safety_stock is not None:
        ss = min(ss, max_safety_stock)

    return ss, sigma_ltd


def calculate_reorder_point(lead_time_demand: float, safety_stock: int) -> int:
    """
    Computes Reorder Point: ROP = ceil(LTD) + Safety Stock.
    """
    return math.ceil(lead_time_demand) + safety_stock


def enforce_pack_and_moq(raw_quantity: int, pack_size: int, moq: int) -> Tuple[int, int, bool]:
    """
    Enforces master pack size multiples and minimum order quantity:
    Returns: (final_quantity, units_added_by_rounding, moq_triggered)
    """
    if raw_quantity <= 0:
        return 0, 0, False

    pack = max(1, pack_size)
    # Round up to nearest integer multiple of pack size
    pack_rounded = math.ceil(raw_quantity / pack) * pack
    units_added = pack_rounded - raw_quantity

    moq_applied = False
    final_qty = pack_rounded
    if final_qty < moq:
        moq_applied = True
        # Round MOQ up to pack multiple if needed
        final_qty = math.ceil(moq / pack) * pack

    return final_qty, units_added, moq_applied

