# PR #7 — feat: model features, train/test split and leakage-safe preprocessing

**Rama:** `feature/feature-engineering` → `develop` · **Fase:** 4 (feature engineering)

## Description

Prepara todo lo que necesita el modelo de las fases 5–6 sin entrenar todavía ninguno: variables nuevas, qué columnas entran y por qué, la división train/test y un preprocesado que solo aprende de train. Cada decisión de selección se tomó con datos de **train**, nunca con el test (diseño §4, L5).

## Changes

- `src/feature_engineering.py` (nuevo):
  - `add_model_features`: añade `tenure_bucket` (tramos del diseño) y `has_price_history` (marca si `price_change_ratio` es observado o imputado). Son deterministas: no aprenden nada de los datos.
  - `model_feature_columns` + `EXCLUDED_FEATURES`: 19 columnas entran; cada una de las que no entran tiene su motivo escrito en el código.
  - `check_no_leakage`: detiene el proceso si el identificador, el objetivo o una fecha se cuelan entre las variables (L1, L2, L6).
  - `split_train_test`: 80/20 estratificado por `churn`, semilla 42, y comprobación previa de que `customer_id` es único (L6).
  - `build_preprocessor`: `ColumnTransformer` sin ajustar (escalado, imputación constante y one-hot con categorías fijas) para meterlo dentro del `Pipeline` del modelo (L4).
  - `collinearity_report`: VIF de las numéricas candidatas antes y después de la selección, solo con train.
  - `python -m src.feature_engineering`: imprime la división, las exclusiones y la tabla de VIF.
- `src/config.py`: tramos de antigüedad y tamaño del test en un único sitio.
- `tests/test_features.py`: 5 tests nuevos.
  - Los tramos siguen el diseño y `has_price_history` coincide con los valores observados.
  - Ninguna variable prohibida, sensible o excluida entra en el modelo, y una fecha colada provoca un error.
  - Train y test no comparten clientes y mantienen la proporción de churn.
  - El escalado aprende solo de train.
  - La matriz de test no tiene NaN y tiene las columnas esperadas.
- `docs/data_dictionary.md`: sección «Variables del modelo» con lo que entra, lo que no y la evidencia.
- `docs/01_project_design.md`, `README.md`, `CHANGELOG.md`: estado de la fase 4 y comandos.

## Decisiones

| Decisión | Motivo | Evidencia (train) |
|---|---|---|
| Fuera `n_payments` | Idéntica a `tenure_months` | Iguales en el 100 % |
| Fuera `total_revenue` (R5) | `≈ tenure × cuota` | r = 0,9996 |
| Fuera `avg_historical_charge` | `≈ monthly_charges`; lo útil ya está en `price_change_ratio` | r = 0,992; VIF 203 |
| Fuera `n_services`, `n_addon_services` | Sumas exactas de los `has_*`, que sí entran y dicen **qué** servicio importa | Iguales en el 100 % |
| Fuera `is_auto_payment` | Se deduce de `payment_method` | — |
| Fuera `is_male`, `is_senior` por defecto | Atributos sensibles; no son una palanca de negocio | `is_senior` sí se asocia al churn (42 % frente a 24 %) |
| `price_change_ratio` sin historial → 1,0 | "Sin cambio observado"; constante, no aprende de los datos | 507 clientes de train con `tenure < 2` |
| One-hot con `drop="first"` y categorías fijas | Cada coeficiente se lee frente a una referencia clara | — |

Tras la selección, el VIF de las numéricas queda entre 1,0 y 1,1.

## Validation

```text
python -m src.feature_engineering
  train: 5,634 clientes, churn 26.5%
  test:  1,409 clientes, churn 26.5%
  variables: 19 columnas de entrada -> 26 tras el preprocesado; NaN en test: 0

python -m pytest   -> 20 passed
```

## Potential issues

- **Fase 3 pendiente.** Esta fase se adelanta a la de estadística. No depende de ella: las decisiones se toman con train y no contrastan hipótesis. El notebook 02 contrastará H1–H8 con todos los clientes, como dice el diseño.
- **Excluir `is_senior` cuesta rendimiento.** Es una decisión de criterio, no técnica. La fase 5 debe medir el modelo con y sin atributos sensibles (`include_sensitive=True`) y documentar la diferencia.
- `tenure_months` y `tenure_bucket` entran juntas: el tramo deja a la logística captar la caída del riesgo en el primer año. Si la fase 5 ve coeficientes inestables, se puede quedar solo una.
- `handle_unknown="error"` hace que una categoría nueva rompa el preprocesado. Es intencionado (los datos ya están validados aguas arriba), pero en producción habría que decidir otra política.
