# Customer Churn Analysis & Prediction

> **Estado:** Fase 2 completada (datos, SQL y limpieza). Este README se completará en la Fase 8.

Proyecto de Data Analytics y Machine Learning para responder a una pregunta de negocio:

> ¿Qué factores están asociados al abandono de clientes y podemos construir un modelo que identifique de forma fiable a los clientes con mayor riesgo de churn?

- **Datos:** [IBM Telco Customer Churn](https://github.com/IBM/telco-customer-churn-on-icp4d) (7.043 clientes de una operadora **ficticia**, licencia Apache 2.0), normalizado en cuatro tablas SQL.
- **Stack:** Python, Pandas, NumPy, SQL (SQLite), Scikit-learn, Jupyter, Matplotlib, pytest, Git/GitHub.

## Cómo ejecutarlo

Requisitos: Python 3.11 o superior (probado con 3.13) y Git.

```bash
git clone https://github.com/JavierMolero12/customer-churn-analysis.git
```

```bash
cd customer-churn-analysis
```

```bash
python -m venv .venv
```

Activa el entorno: en Windows `.venv\Scripts\activate`, en macOS/Linux `source .venv/bin/activate`.

```bash
pip install -r requirements.txt
```

```bash
python -m src.pipeline
```

El último comando descarga los datos (verificando el SHA-256), construye la base de datos SQLite, la limpia y genera `data/processed/customer_features.csv`. Tarda unos segundos.

Tests y notebooks:

```bash
python -m pytest
```

```bash
jupyter lab
```

## Documentación

- [Diseño del proyecto](docs/01_project_design.md): problema, dataset, modelo de datos, hipótesis, leakage, arquitectura y roadmap.
- [Diccionario de datos](docs/data_dictionary.md): cada columna con su origen (REAL / DERIVADO / SINTÉTICO).
- [Notebook 01 — Exploración y limpieza](notebooks/01_data_exploration.ipynb).
- [Pull Requests del proyecto](docs/pull_requests/): descripción de cada PR.
