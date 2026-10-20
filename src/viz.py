"""Estilo común de los gráficos: la misma paleta y apariencia en todos los notebooks.

Paleta categórica validada para daltonismo y contraste (orden fijo).
En TODO el proyecto: azul = clientes que se quedan, naranja = clientes que abandonan.
"""

import matplotlib.pyplot as plt

from src.config import FIGURES_DIR

BLUE = "#2a78d6"
BLUE_WASH = "#2a78d61a"  # el mismo azul al ~10 % de opacidad, para rellenos
ORANGE = "#eb6834"

CHURN_COLORS = {0: BLUE, 1: ORANGE}
CHURN_LABELS = {0: "No churn", 1: "Churn"}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"


def apply_style() -> None:
    """Ejes y rejilla discretos (líneas finas y continuas), texto en tinta neutra, sin marcos."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.titlecolor": INK,
            "axes.labelcolor": INK_SECONDARY,
            "axes.edgecolor": BASELINE,
            "axes.linewidth": 1,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 1,
            "grid.linestyle": "-",
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_SECONDARY,
            "ytick.labelcolor": INK_SECONDARY,
            "lines.linewidth": 2,
            "legend.frameon": False,
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
        }
    )


def save_figure(fig: plt.Figure, name: str) -> None:
    """Guarda el gráfico en reports/figures/ para reutilizarlo en el README y el informe."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / f"{name}.png")
