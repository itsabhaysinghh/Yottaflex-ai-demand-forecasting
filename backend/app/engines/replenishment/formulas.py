import math
from dataclasses import dataclass
from typing import Tuple
from scipy.stats import norm


@dataclass(frozen=True)
class ReorderPointCalculation:
    lead_time_demand: float
    safety_stock: int
    sigma_ltd: float
    reorder_point: int


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


def calculate_reorder_point_details(
    avg_daily_demand: float,
    demand_std_dev: float,
    avg_lead_time_days: float,
    lead_time_std_dev: float,
    service_level: float,
    min_safety_stock: int,
    max_safety_stock: int | None,
) -> ReorderPointCalculation:
    lead_time_demand = calculate_lead_time_demand(
        avg_daily_demand,
        avg_lead_time_days,
    )
    safety_stock, sigma_ltd = calculate_safety_stock(
        avg_daily_demand=avg_daily_demand,
        demand_std_dev=demand_std_dev,
        avg_lead_time_days=avg_lead_time_days,
        lead_time_std_dev=lead_time_std_dev,
        service_level=service_level,
        min_safety_stock=min_safety_stock,
        max_safety_stock=max_safety_stock,
    )
    reorder_point = calculate_reorder_point(lead_time_demand, safety_stock)
    return ReorderPointCalculation(
        lead_time_demand=lead_time_demand,
        safety_stock=safety_stock,
        sigma_ltd=sigma_ltd,
        reorder_point=reorder_point,
    )


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
    units_added = final_qty - raw_quantity

    return final_qty, units_added, moq_applied

