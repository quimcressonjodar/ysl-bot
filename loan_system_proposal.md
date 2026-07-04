# Propuesta de Sistema de Créditos/Préstamos para el Bot de Economía del Clan Usaosne

## 1. Introducción

El bot de economía actual del clan Usaosne ya incorpora un sistema de gestión de monedas (`wallet` y `bank`), así como diversas actividades para ganar y gastar dinero, incluyendo recompensas diarias/semanales, trabajos, crímenes, compra/venta de ítems y mascotas, y juegos de azar. Se ha identificado que las batallas de mascotas pueden llevar a los usuarios a un estado de "deuda paralizante" (`crippling debt`) con saldos negativos en sus `wallets`, lo que sugiere la necesidad de un sistema formal para gestionar préstamos y créditos.

Esta propuesta detalla la implementación de un sistema de créditos/préstamos que permitirá a los usuarios obtener fondos adicionales, gestionar sus deudas y, al mismo tiempo, introducir un mecanismo de intereses que fomente la devolución y añada una capa de complejidad y realismo a la economía del bot.

## 2. Análisis de la Economía Actual

La economía del bot se basa en los siguientes pilares:

*   **Fuentes de Ingresos:**
    *   `!daily`: 1,000 monedas diarias.
    *   `!weekly`: 25,000 monedas semanales.
    *   `!claim`: Recompensas por roles (ej. rol `bronze` da 2,000, `ascended` da 60,000,000).
    *   `!work`: Ganancias aleatorias entre 250 y 800 monedas con un cooldown de 45 minutos.
    *   `!crime`: Ganancias aleatorias entre 2,000 y 6,500 monedas con un cooldown de 2 horas, con riesgo de perder entre 1,000 y 3,500 monedas.
    *   `!adventure`: Recompensas de ítems vendibles (valor desde 2 hasta 10,000,000,000 para ítems `godly`).
    *   `!claimdrop`: Recompensas de monedas (50,000 a 200,000) o ítems de valor variable cada 5 horas.
    *   `!pay`: Transferencias de monedas entre usuarios.
    *   `!blackjack`, `!roulette`, `!dice`: Juegos de azar con multiplicadores de ganancia (hasta x36 en ruleta) y riesgo de pérdida.

*   **Sumideros de Gasto:**
    *   `!deposit`: Mueve monedas de `wallet` a `bank` (almacenamiento seguro).
    *   `!withdraw`: Mueve monedas de `bank` a `wallet`.
    *   `!pay`: Transferencias de monedas a otros usuarios.
    *   `!sell`: Venta de ítems del inventario (convierte ítems en monedas).
    *   `!shop` (vía `cogs/pets.py`): Compra de mascotas (5,000 a 75,000,000,000 monedas), comida (25,000 a 500,000 monedas) y roles (25,000 a 1,000,000,000 monedas).
    *   `!battle` (vía `views/pet_views.py`): Pérdida de 15,000 a 30,000 monedas en batallas de mascotas.
    *   `!crime`: Posible multa de 1,000 a 3,500 monedas.
    *   `!roulette`, `!blackjack`, `!dice`: Apuestas en juegos de azar.

*   **Deuda Implícita:**
    *   Actualmente, el sistema permite que el `wallet` de un usuario tenga un saldo negativo, especialmente después de perder una batalla de mascotas. Esto se etiqueta como "Bankrupt! The loser is now in crippling debt." (`views/pet_views.py`, línea 164), pero no hay un mecanismo formal de seguimiento o recuperación de esta deuda.

## 3. Propuesta de Sistema de Créditos/Préstamos

Se propone un sistema de préstamos que permita a los usuarios solicitar una cantidad de monedas, con la obligación de devolverla más un interés acumulado con el tiempo. Este sistema se integrará con la economía existente y formalizará el concepto de deuda.

### 3.1. Nuevos Comandos

*   `!loan <cantidad>`: Solicita un préstamo de una cantidad específica de monedas.
    *   **Límites:** El monto máximo del préstamo podría basarse en el patrimonio neto total del usuario (wallet + bank) o en su historial de actividad económica (ej. total ganado en `work`, `daily`, `weekly`). Esto evita préstamos excesivos a usuarios nuevos o inactivos.
    *   **Interés:** Se informará al usuario sobre la tasa de interés y el período de acumulación.
    *   **Condiciones:** No se podrá solicitar un nuevo préstamo si ya se tiene una deuda pendiente.

*   `!repay <cantidad>`: Permite al usuario devolver una parte o la totalidad de su préstamo.
    *   **Prioridad:** El pago se aplicará primero a los intereses acumulados y luego al capital del préstamo.
    *   **Pago mínimo:** Podría haber un pago mínimo requerido para evitar que la deuda crezca indefinidamente.

*   `!debt`: Muestra el estado actual de la deuda del usuario, incluyendo el capital pendiente, los intereses acumulados, el total a devolver y la fecha del próximo cálculo de intereses.

### 3.2. Mecanismo de Intereses

El interés se acumulará sobre el capital pendiente del préstamo a intervalos regulares (ej. cada 24 horas). La tasa de interés podría ser fija o variable, y se podría considerar un interés compuesto.

*   **Tasa de Interés:** Una tasa de interés razonable podría ser entre 1% y 5% por período (ej. diario).
*   **Acumulación:** El interés se calculará y añadirá al capital pendiente cada X horas (ej. 24 horas). Esto incentivará a los usuarios a devolver los préstamos rápidamente.
*   **Cálculo:** `Interés_acumulado = Capital_pendiente * Tasa_interés_por_período`
    `Nuevo_capital_pendiente = Capital_pendiente + Interés_acumulado`

### 3.3. Integración con la Economía Existente

*   **Saldo Negativo:** El concepto de "deuda paralizante" de las batallas de mascotas se formalizará como un préstamo automático. Si el `wallet` de un usuario cae por debajo de cero, el monto negativo se convertirá automáticamente en un préstamo con las mismas condiciones de interés.
*   **Restricciones:**
    *   Los usuarios con deuda pendiente no podrán participar en juegos de azar (`!roulette`, `!blackjack`, `!dice`) con el dinero prestado. Podrían usar su propio dinero si tienen saldo positivo en `wallet` o `bank`.
    *   Los ingresos de `!daily`, `!weekly`, `!claim`, `!work`, `!crime` y `!adventure` se destinarán automáticamente a cubrir la deuda pendiente (primero intereses, luego capital) hasta que el préstamo sea saldado. Esto podría ser un porcentaje de las ganancias o la totalidad, dependiendo de la agresividad deseada para la recuperación de la deuda.
    *   Los usuarios con deuda no podrán transferir dinero (`!pay`) a otros usuarios.

### 3.4. Almacenamiento de Datos (MongoDB `eco_col`)

Se añadirán nuevos campos a la colección `eco_col` para cada usuario:

*   `loan_amount`: Cantidad de capital pendiente del préstamo.
*   `interest_accrued`: Cantidad de intereses acumulados.
*   `last_interest_calc`: Timestamp de la última vez que se calcularon los intereses.
*   `loan_start_time`: Timestamp de cuándo se tomó el préstamo.

### 3.5. Tareas Programadas

Se necesitará una tarea programada (similar a `spawn_global_drop` en `cogs/events.py`) que se ejecute periódicamente (ej. cada hora o cada 24 horas) para:

1.  Iterar sobre todos los usuarios con `loan_amount > 0`.
2.  Calcular los intereses acumulados desde `last_interest_calc`.
3.  Actualizar `loan_amount` e `interest_accrued`.
4.  Actualizar `last_interest_calc`.

## 4. Consideraciones Adicionales

*   **Interfaz de Usuario:** Los mensajes del bot deben ser claros y concisos, informando al usuario sobre el estado de su préstamo, los intereses y las restricciones aplicadas.
*   **Administración:** Se podrían añadir comandos de administración para que los moderadores puedan ver, modificar o perdonar préstamos de usuarios.
*   **Economía a Largo Plazo:** El sistema de préstamos puede influir en la inflación/deflación de la economía. Es importante monitorear el impacto y ajustar las tasas de interés o los límites de préstamo si es necesario.

## 5. Conclusión

La implementación de un sistema de créditos/préstamos formalizará la gestión de la deuda en el bot, proporcionará a los usuarios una herramienta para obtener fondos en momentos de necesidad y añadirá una dinámica económica más profunda. Al integrar este sistema con las mecánicas existentes y establecer un mecanismo de intereses, se creará un entorno más desafiante y gratificante para los miembros del clan Usaosne.
