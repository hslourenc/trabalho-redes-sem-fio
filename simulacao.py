import os
import numpy as np
import matplotlib.pyplot as plt

# --- Reference-based parameters (2026 Context) ---
# Derived from:
# [1] Kokkinis et al. (2025) - Techno-economic modeling for 6G
# [7] Akyildiz et al. (2020) - 6G Vision and Requirements
# [15] Shafi et al. (2025) - Industrial Viewpoints on RAN Technologies for 6G
# [25] Oughton et al. (2019) - Open-source techno-economic assessment (pysim5G)

DEFAULT_POPULATION = 500_000
DEFAULT_AREA_KM2 = 200
DEFAULT_ACTIVE_RATIO = 0.1
DEFAULT_AVG_THROUGHPUT_MBPS = 20

TECHNOLOGIES = {
    "5G": {
        "range_m": 596,  # Ref [15, 24] - Urban macro coverage at 3.5GHz (179 sites for 200km2)
        "capacity_gbps": 2.0,  # Ref [13, 24] - Typical aggregate site capacity
        "capex_per_site": 150_000,  # Ref [1, 25] - Standard Macro-BS CAPEX
        "opex_per_site_year": 20_000,  # Ref [1, 25] - Standard Macro-BS OPEX
        "base_latency_ms": 4.0,  # Ref [4, 15] - Commercial 5G urban latency
        "base_jitter_ms": 1.0,   # Ref [23] - Industrial KPI for 5G
        "base_ber": 1e-5,        # Ref [13, 15] - Reliability 99.999%
        "spectrum_ghz": 3.5,
        "network_slicing": 0.80,
        "mec_support": 0.90,
        "urllc_support": 0.85,
        "description": "5G macro-cell urban coverage.",
    },
    "6G": {
        "range_m": 150,  # Ref [1, 15] - THz/Sub-THz high densification
        "capacity_gbps": 100.0, # Ref [6, 13] - Peak rates reaching 100Gbps+
        "capex_per_site": 300_000, # Ref [1] - Estimated 2x to 8x 5G cost (using 2x per docx)
        "opex_per_site_year": 40_000,
        "base_latency_ms": 0.1,  # Ref [7, 15] - 100us goal for 6G
        "base_jitter_ms": 0.01, # Ref [7] - Microsecond precision
        "base_ber": 1e-9,       # Ref [7, 15] - Reliability 99.9999999%
        "spectrum_ghz": 300.0,
        "network_slicing": 0.95,
        "mec_support": 0.98,
        "urllc_support": 0.99,
        "description": "6G high-density THz infrastructure.",
    },
}

def coverage_sites(area_km2: float, range_m: float) -> int:
    """Calculates minimal sites for geographic coverage (Hexagonal model)."""
    # Using hexagonal tiling: Area of hexagon = (3 * sqrt(3) / 2) * R^2
    # But for a simpler conservative estimate, we use circles with overlap or the Docx logic.
    site_area_km2 = np.pi * (range_m / 1000) ** 2
    return int(np.ceil(area_km2 / site_area_km2))

def capacity_sites(total_demand_gbps: float, site_capacity_gbps: float) -> int:
    """Calculates sites based on traffic demand."""
    return int(np.ceil(total_demand_gbps / site_capacity_gbps))

def estimate_performance(load_factor: float, tech_params: dict) -> tuple[float, float, float]:
    """
    Estimates latency, jitter, and BER using M/M/1 Queuing Theory.
    Model: D(rho) = D_base / (1 - rho)
    As utilization (rho) approaches 1, delay increases hyperbolically.
    Ref: [2] Thomas Biebricher (2023) - AI and ML Applications: 5G and 6G
    """
    rho = min(max(load_factor, 0.001), 0.99) # Constraint for stability

    # Latency: M/M/1 average delay model
    # D = D_prop + D_queue -> simplified as D_base / (1-rho)
    latency_ms = tech_params["base_latency_ms"] / (1 - rho)

    # Jitter: Standard deviation of delay in M/M/1
    # J = sqrt(rho) / (mu * (1 - rho)) -> simplified as J_base * sqrt(rho) / (1-rho)
    jitter_ms = (tech_params["base_jitter_ms"] * np.sqrt(rho)) / (1 - rho)

    # BER: Increases exponentially with congestion due to interference/loss
    # Formula: BER(rho) = BER_base * 10^(k * (rho - threshold))
    if rho > 0.75:
        ber = tech_params["base_ber"] * 10 ** (3 * (rho - 0.75) / 0.25)
    else:
        ber = tech_params["base_ber"]

    return float(latency_ms), float(jitter_ms), float(ber)

def simulate_network(
    tech_name: str,
    population: int = DEFAULT_POPULATION,
    active_ratio: float = DEFAULT_ACTIVE_RATIO,
    avg_throughput_mbps: float = DEFAULT_AVG_THROUGHPUT_MBPS,
    area_km2: float = DEFAULT_AREA_KM2,
) -> dict:
    tech = TECHNOLOGIES[tech_name]
    active_users = int(np.round(population * active_ratio))
    total_demand_gbps = active_users * avg_throughput_mbps / 1000.0

    num_sites_cover = coverage_sites(area_km2, tech["range_m"])
    num_sites_capacity = capacity_sites(total_demand_gbps, tech["capacity_gbps"])
    num_sites = max(num_sites_cover, num_sites_capacity)

    load_factor = total_demand_gbps / (num_sites * tech["capacity_gbps"])
    latency_ms, jitter_ms, ber = estimate_performance(load_factor, tech)

    return {
        "tech": tech_name,
        "population": population,
        "active_ratio": active_ratio,
        "avg_throughput_mbps": avg_throughput_mbps,
        "active_users": active_users,
        "total_demand_gbps": total_demand_gbps,
        "sites_cover": num_sites_cover,
        "sites_capacity": num_sites_capacity,
        "sites": num_sites,
        "load_factor": float(load_factor),
        "capacity_margin": float(max(0.0, 1 - load_factor)),
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "ber": ber,
        "capex_usd": num_sites * tech["capex_per_site"],
        "opex_usd_per_year": num_sites * tech["opex_per_site_year"],
        "spectrum_ghz": tech["spectrum_ghz"],
        "network_slicing": tech["network_slicing"],
        "mec_support": tech["mec_support"],
        "urllc_support": tech["urllc_support"],
    }

def simulate_hybrid(
    population: int = DEFAULT_POPULATION,
    active_ratio: float = DEFAULT_ACTIVE_RATIO,
    avg_throughput_mbps: float = DEFAULT_AVG_THROUGHPUT_MBPS,
    area_km2: float = DEFAULT_AREA_KM2,
    dense_area_ratio: float = 0.30, # Hotspots in 30% of area
    dense_user_ratio: float = 0.45, # 45% of users in these hotspots
) -> dict:
    dense_area = area_km2 * dense_area_ratio
    medium_area = area_km2 - dense_area

    total_active_users = int(np.round(population * active_ratio))
    dense_active_users = int(np.round(total_active_users * dense_user_ratio))
    medium_active_users = total_active_users - dense_active_users

    dense_demand_gbps = dense_active_users * avg_throughput_mbps / 1000.0
    medium_demand_gbps = medium_active_users * avg_throughput_mbps / 1000.0

    tech_6g = TECHNOLOGIES["6G"]
    tech_5g = TECHNOLOGIES["5G"]

    sites_6g_cover = coverage_sites(dense_area, tech_6g["range_m"])
    sites_6g_capacity = capacity_sites(dense_demand_gbps, tech_6g["capacity_gbps"])
    sites_6g = max(sites_6g_cover, sites_6g_capacity)

    sites_5g_cover = coverage_sites(medium_area, tech_5g["range_m"])
    sites_5g_capacity = capacity_sites(medium_demand_gbps, tech_5g["capacity_gbps"])
    sites_5g = max(sites_5g_cover, sites_5g_capacity)

    load_6g = dense_demand_gbps / (sites_6g * tech_6g["capacity_gbps"])
    load_5g = medium_demand_gbps / (sites_5g * tech_5g["capacity_gbps"])

    latency_6g, jitter_6g, ber_6g = estimate_performance(load_6g, tech_6g)
    latency_5g, jitter_5g, ber_5g = estimate_performance(load_5g, tech_5g)

    total_sites = sites_6g + sites_5g
    capex_total = sites_6g * tech_6g["capex_per_site"] + sites_5g * tech_5g["capex_per_site"]
    opex_total = sites_6g * tech_6g["opex_per_site_year"] + sites_5g * tech_5g["opex_per_site_year"]

    demand_total = dense_demand_gbps + medium_demand_gbps
    weight_dense = dense_demand_gbps / demand_total if demand_total > 0 else 0.5
    weight_medium = medium_demand_gbps / demand_total if demand_total > 0 else 0.5

    return {
        "tech": "Hybrid",
        "population": population,
        "active_ratio": active_ratio,
        "avg_throughput_mbps": avg_throughput_mbps,
        "active_users": total_active_users,
        "total_demand_gbps": demand_total,
        "dense_area_km2": dense_area,
        "medium_area_km2": medium_area,
        "sites_6g": sites_6g,
        "sites_5g": sites_5g,
        "sites": total_sites,
        "load_factor": float(weight_dense * load_6g + weight_medium * load_5g),
        "capacity_margin": float(max(0.0, 1 - demand_total / (sites_6g * tech_6g["capacity_gbps"] + sites_5g * tech_5g["capacity_gbps"]))),
        "latency_ms": float(weight_dense * latency_6g + weight_medium * latency_5g),
        "jitter_ms": float(weight_dense * jitter_6g + weight_medium * jitter_5g),
        "ber": float(weight_dense * ber_6g + weight_medium * ber_5g),
        "capex_usd": capex_total,
        "opex_usd_per_year": opex_total,
        "spectrum_ghz": float(weight_dense * tech_6g["spectrum_ghz"] + weight_medium * tech_5g["spectrum_ghz"]),
        "network_slicing": float(weight_dense * tech_6g["network_slicing"] + weight_medium * tech_5g["network_slicing"]),
        "mec_support": float(weight_dense * tech_6g["mec_support"] + weight_medium * tech_5g["mec_support"]),
        "urllc_support": float(weight_dense * tech_6g["urllc_support"] + weight_medium * tech_5g["urllc_support"]),
        "sites_6g_cover": sites_6g_cover,
        "sites_6g_capacity": sites_6g_capacity,
        "sites_5g_cover": sites_5g_cover,
        "sites_5g_capacity": sites_5g_capacity,
    }

def summary_text(result: dict) -> str:
    if result["tech"] != "Hybrid":
        return (
            f"{result['tech']}: sites={result['sites']}, capex=${result['capex_usd']/1e6:.2f}M, "
            f"opex=${result['opex_usd_per_year']/1e6:.2f}M/ano, load={result['load_factor']:.2f}, "
            f"latency={result['latency_ms']:.2f}ms, jitter={result['jitter_ms']:.2f}ms, ber={result['ber']:.1e}"
        )

    return (
        f"Hybrid: sites={result['sites']} (5G={result['sites_5g']}, 6G={result['sites_6g']}), "
        f"capex=${result['capex_usd']/1e6:.2f}M, opex=${result['opex_usd_per_year']/1e6:.2f}M/ano, "
        f"load_avg={result['load_factor']:.3f}, latency={result['latency_ms']:.2f}ms, "
        f"jitter={result['jitter_ms']:.2f}ms, ber={result['ber']:.1e}"
    )

def plot_sweep(x_values: np.ndarray, results: dict, x_label: str, filename: str) -> None:
    os.makedirs("plots", exist_ok=True)
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    metrics = ["sites", "latency_ms", "jitter_ms", "ber"]
    titles = ["Número de sites", "Latência média (ms)", "Jitter médio (ms)", "BER efetiva"]
    scales = ["linear", "linear", "linear", "log"]
    colors = {"5G": "tab:blue", "6G": "tab:orange", "Hybrid": "tab:green"}

    for ax, metric, title, scale in zip(axs.flatten(), metrics, titles, scales):
        for tech_name, curve in results.items():
            ax.plot(x_values, curve[metric], label=tech_name, color=colors.get(tech_name, None))
        ax.set_xlabel(x_label)
        ax.set_ylabel(title)
        ax.set_yscale(scale)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend()

    fig.suptitle(f"Comportamento de redes 5G, 6G e híbrida com variação de {x_label}")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(os.path.join("plots", filename), dpi=180)
    plt.close(fig)

def run_sweeps() -> None:
    tech_names = ["5G", "6G", "Hybrid"]
    traffic_values = np.linspace(5, 50, 10)
    traffic_results = {tech: {"sites": [], "latency_ms": [], "jitter_ms": [], "ber": []} for tech in tech_names}
    for throughput in traffic_values:
        for tech in tech_names:
            result = simulate_hybrid(avg_throughput_mbps=throughput) if tech == "Hybrid" else simulate_network(tech, avg_throughput_mbps=throughput)
            for metric in traffic_results[tech]:
                traffic_results[tech][metric].append(result[metric])
    plot_sweep(traffic_values, traffic_results, "Demanda média por usuário (Mbps)", "traffic_sweep_v2.png")

    active_ratio_values = np.linspace(0.05, 0.20, 10)
    active_results = {tech: {"sites": [], "latency_ms": [], "jitter_ms": [], "ber": []} for tech in tech_names}
    for active_ratio in active_ratio_values:
        for tech in tech_names:
            result = simulate_hybrid(active_ratio=active_ratio) if tech == "Hybrid" else simulate_network(tech, active_ratio=active_ratio)
            for metric in active_results[tech]:
                active_results[tech][metric].append(result[metric])
    plot_sweep(active_ratio_values, active_results, "Taxa de usuários ativos simultâneos", "active_ratio_sweep_v2.png")

def print_comparison() -> None:
    baseline_5g = simulate_network("5G")
    baseline_6g = simulate_network("6G")
    baseline_hybrid = simulate_hybrid()
    print("--- Comparação de deployment para o caso base (Ref-based) ---")
    print(summary_text(baseline_5g))
    print(summary_text(baseline_6g))
    print(summary_text(baseline_hybrid))

if __name__ == "__main__":
    print_comparison()
    run_sweeps()
