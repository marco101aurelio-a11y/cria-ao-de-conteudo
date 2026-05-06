import jax
import jax.numpy as jnp
from typing import Dict, List

def calculate_marketing_performance(costs: List[float], conversions: List[int]) -> Dict:
    """
    Calcula métricas de performance (CAC, ROAS) usando JAX para operações vetorizadas.
    Atende à Skill #3 do Capvi Squad.
    """
    c = jnp.array(costs)
    v = jnp.array(conversions)
    
    # CAC por canal/campanha
    cac = c / jnp.where(v == 0, 1e-6, v)
    
    # Médias usando JAX
    mean_cac = jnp.mean(cac)
    total_cost = jnp.sum(c)
    total_conv = jnp.sum(v)
    global_cac = total_cost / jnp.where(total_conv == 0, 1, total_conv)
    
    return {
        "cac_vector": cac.tolist(),
        "mean_cac": float(mean_cac),
        "total_cost": float(total_cost),
        "total_conversions": int(total_conv),
        "global_cac": float(global_cac)
    }

def simulate_scaling(budget: float, historical_cac: float, factor: float = 1.2):
    """
    Simula escala de orçamento com perda de eficiência (fator JAX).
    """
    # Exemplo de função JAX JIT-able
    def scale_fn(b):
        return b / (historical_cac * factor)
    
    projected_conversions = jax.jit(scale_fn)(budget)
    return float(projected_conversions)
