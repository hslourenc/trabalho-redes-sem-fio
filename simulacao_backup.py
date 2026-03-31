import os
import numpy as np
import matplotlib.pyplot as plt

# --- Parâmetros gerais da cidade ---
# Estes valores representam o caso de estudo: cidade de 500.000 habitantes,
# área urbana de 200 km², e carga média de pico definida por uma fração de usuários ativos.
# A demanda é expressa em Mbps por usuário e usada para estimar tráfego total.
DEFAULT_POPULATION = 500_000
DEFAULT_AREA_KM2 = 200
DEFAULT_ACTIVE_RATIO = 0.1
DEFAULT_AVG_THROUGHPUT_MBPS = 20

# --- Perfis de tecnologia 5G e 6G ---
TECHNOLOGIES = {
    "5G": {
        "range_m": 500,
        "capacity_gbps": 2.0,
        "capex_per_site": 150_000,
        "opex_per_site_year": 20_000,
        "base_latency_ms": 4.0,
        "base_jitter_ms": 1.0,
        "base_ber": 1e-7,
        "spectrum_ghz": 3.5,
        "network_slicing": 0.80,
        "mec_support": 0.90,
        "urllc_support": 0.85,
        "description": "Cobertura de macro-células 5G com desempenho equilibrado para mobilidade urbana.",
    },
    "6G": {
        "range_m": 150,
        "capacity_gbps": 100.0,
        "capex_per_site": 300_000,
        "opex_per_site_year": 40_000,
        "base_latency_ms": 0.5,
        "base_jitter_ms": 0.1,
        "base_ber": 1e-9,
        "spectrum_ghz": 300.0,
        "network_slicing": 0.95,
        "mec_support": 0.98,
        "urllc_support": 0.99,
        "description": "Infraestrutura 6G de alta densidade, ultra-baixa latência e suporte a aplicações críticas.",
    },
}


def coverage_sites(area_km2: float, range_m: float) -> int:
    """Calcula o número mínimo de sites para cobertura geográfica."""
    site_area_km2 = np.pi * (range_m / 1000) ** 2
    return int(np.ceil(area_km2 / site_area_km2))


def capacity_sites(total_demand_gbps: float, site_capacity_gbps: float) -> int:
    """Calcula o número mínimo de sites para suportar a demanda de tráfego."""
    return int(np.ceil(total_demand_gbps / site_capacity_gbps))


def estimate_performance(load_factor: float, tech_params: dict) -> tuple[float, float, float]:
    """Estima latência, jitter e BER a partir do fator de carga por tecnologia.

    O modelo é simplificado, mas reflete duas ideias principais:
    1. Cada tecnologia tem um valor base de latência/jitter/BER em carga leve.
    2. À medida que a carga se aproxima da capacidade, os atrasos e erros crescem de forma não linear.

    A função usa tanh() para capturar a transição suave entre carga leve e carga moderada,
    e aplica um efeito adicional quando a rede ultrapassa a capacidade (load > 1.0).
    """
    load = max(load_factor, 0.01)

    # Latência aumenta de modo suave com a carga, partindo do valor base.
    latency_ms = tech_params["base_latency_ms"] * (1 + 1.5 * np.tanh(load * 1.8))

    # Jitter também cresce com a carga, mas pode ser mais sensível em redes congestionadas.
    jitter_ms = tech_params["base_jitter_ms"] * (1 + 3.5 * np.tanh(load * 2.0))

    # BER fica quase constante em cargas menores, mas dispara para cargas altas acima de 75%.
    ber = tech_params["base_ber"] * (1 + 120.0 * np.maximum(0, load - 0.75) ** 1.8)

    # Se a demanda exceder a capacidade disponível, aplicamos um fator extra de degradação.
    if load > 1.0:
        overload = load - 1.0
        latency_ms *= 1 + overload * 2.5
        jitter_ms *= 1 + overload * 2.0
        ber *= 10 ** (overload * 0.9)

    return float(latency_ms), float(jitter_ms), float(ber)


def simulate_network(
    tech_name: str,
    population: int = DEFAULT_POPULATION,
    active_ratio: float = DEFAULT_ACTIVE_RATIO,
    avg_throughput_mbps: float = DEFAULT_AVG_THROUGHPUT_MBPS,
    area_km2: float = DEFAULT_AREA_KM2,
) -> dict:
    """Simula o desempenho de uma tecnologia celular para o cenário urbano definido."""
    tech = TECHNOLOGIES[tech_name]

    # Calcula usuários ativos no pico a partir da taxa de ocupação.
    active_users = int(np.round(population * active_ratio))

    # Converte a demanda total de Mbps para Gbps.
    total_demand_gbps = active_users * avg_throughput_mbps / 1000.0

    # Número de sites necessários para cobrir geograficamente a área.
    num_sites_cover = coverage_sites(area_km2, tech["range_m"])

    # Número de sites necessários para suportar a demanda de tráfego.
    num_sites_capacity = capacity_sites(total_demand_gbps, tech["capacity_gbps"])

    # O dimensionamento final usa o maior dos dois critérios.
    num_sites = max(num_sites_cover, num_sites_capacity)

    # Fator de utilização da rede: demanda / capacidade total instalada.
    load_factor = total_demand_gbps / (num_sites * tech["capacity_gbps"])

    # Estima métricas de performance com base no nível de carga.
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
    dense_area_ratio: float = 0.30,
    dense_user_ratio: float = 0.45,
) -> dict:
    """Simula uma solução híbrida onde áreas de alta demanda recebem 6G e o resto recebe 5G.

    A ideia é modelar uma cidade com hotspots densos (centro urbano) e
    uma área mais ampla de cobertura geral. Isso permite capturar os
    trade-offs de custo e performance entre 6G de alta densidade e 5G de
    maior cobertura.
    """
    dense_area = area_km2 * dense_area_ratio
    medium_area = area_km2 - dense_area

    # Divide usuários ativos entre a área densa e a área média.
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
        "load_6g": float(load_6g),
        "load_5g": float(load_5g),
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
    """Gera texto resumido para um resultado de simulação."""
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


# A função a seguir gera gráficos comparativos para cada métrica.
# Ela salva as figuras em ./plots/ para facilitar a análise posterior.
def plot_sweep(
    x_values: np.ndarray,
    results: dict,
    x_label: str,
    filename: str,
) -> None:
    """Desenha curvas para sites, latência, jitter e BER em função de um parâmetro de entrada."""
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


# Executa varreduras de parâmetros de entrada para observar o comportamento
# de 5G, 6G e híbrido conforme a demanda, a taxa de usuários ativos e a população.
def run_sweeps() -> None:
    """Executa simulações em faixas de tráfego, taxa de usuários ativos e população."""
    tech_names = ["5G", "6G", "Hybrid"]

    traffic_values = np.linspace(5, 50, 10)
    traffic_results = {tech: {"sites": [], "latency_ms": [], "jitter_ms": [], "ber": []} for tech in tech_names}
    for throughput in traffic_values:
        for tech in tech_names:
            result = simulate_hybrid(avg_throughput_mbps=throughput) if tech == "Hybrid" else simulate_network(tech, avg_throughput_mbps=throughput)
            for metric in traffic_results[tech]:
                traffic_results[tech][metric].append(result[metric])
    plot_sweep(traffic_values, traffic_results, "Demanda média por usuário (Mbps)", "traffic_sweep.png")

    active_ratio_values = np.linspace(0.05, 0.20, 10)
    active_results = {tech: {"sites": [], "latency_ms": [], "jitter_ms": [], "ber": []} for tech in tech_names}
    for active_ratio in active_ratio_values:
        for tech in tech_names:
            result = simulate_hybrid(active_ratio=active_ratio) if tech == "Hybrid" else simulate_network(tech, active_ratio=active_ratio)
            for metric in active_results[tech]:
                active_results[tech][metric].append(result[metric])
    plot_sweep(active_ratio_values, active_results, "Taxa de usuários ativos simultâneos", "active_ratio_sweep.png")

    population_values = np.linspace(100_000, 1_000_000, 10, dtype=int)
    population_results = {tech: {"sites": [], "latency_ms": [], "jitter_ms": [], "ber": []} for tech in tech_names}
    for population in population_values:
        for tech in tech_names:
            result = simulate_hybrid(population=population) if tech == "Hybrid" else simulate_network(tech, population=population)
            for metric in population_results[tech]:
                population_results[tech][metric].append(result[metric])
    plot_sweep(population_values, population_results, "População da cidade", "population_sweep.png")


def print_comparison() -> None:
    """Imprime um resumo comparativo das três alternativas para o caso base."""
    baseline_5g = simulate_network("5G")
    baseline_6g = simulate_network("6G")
    baseline_hybrid = simulate_hybrid()

    print("--- Comparação de deployment para o caso base ---")
    print(summary_text(baseline_5g))
    print(summary_text(baseline_6g))
    print(summary_text(baseline_hybrid))
    print("\nAs figuras de comportamento foram geradas em ./plots/ com variações de demanda, taxa de usuários ativos e população.")


if __name__ == "__main__":
    print_comparison()
    run_sweeps()
