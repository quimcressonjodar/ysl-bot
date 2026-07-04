# Análisis y Propuesta: Sistema de Créditos para el Clan Usaosne

## 1. Evaluación del Ecosistema Económico Actual

El bot del clan Usaosne presenta una economía vibrante y diversificada, estructurada sobre un modelo de acumulación de riqueza a través de actividades tanto activas como pasivas. Tras analizar el código fuente del repositorio `quimcressonjodar/bot`, se observa que el sistema se apoya en una base de datos MongoDB para gestionar los balances de `wallet` (cartera) y `bank` (banco) de cada usuario. La escala económica es amplia, con recompensas que varían desde las 250 monedas en trabajos básicos hasta los 10,000 millones en ítems de rareza "godly".

| Categoría | Mecanismos de Flujo Monetario | Impacto Económico |
| :--- | :--- | :--- |
| **Ingresos Fijos** | `!daily`, `!weekly`, `!claim` (recompensas por roles) | Estabilidad y retención de usuarios. |
| **Actividades de Riesgo** | `!work`, `!crime`, `!rob`, Juegos de azar (`blackjack`, `roulette`) | Alta volatilidad y potencial de enriquecimiento rápido. |
| **Sumideros de Capital** | Tienda de mascotas, comida, roles y multas por crímenes fallidos | Control de la inflación y progresión del jugador. |
| **Deuda Implícita** | Batallas de mascotas con saldo negativo | Estado de bancarrota no regulado formalmente. |

Un hallazgo crítico en el archivo `views/pet_views.py` es la existencia de una "deuda paralizante" (`crippling debt`) que ocurre cuando un usuario pierde una batalla de mascotas y su saldo cae por debajo de cero. Actualmente, este estado es meramente cosmético en los mensajes del bot, sin consecuencias mecánicas reales más allá del saldo negativo.

## 2. Propuesta del Sistema de Créditos y Préstamos

Para formalizar la economía y añadir una capa de estrategia financiera, se propone la implementación de un sistema de créditos regulado. Este sistema permitiría a los usuarios solicitar capital inmediato a cambio de una obligación de devolución con intereses crecientes, resolviendo el vacío legal de las deudas actuales.

### 2.1. Dinámica de los Préstamos con Intereses

La característica principal de este sistema es el **interés compuesto temporal**. A diferencia de una multa fija, el interés propuesto crecería cuanto más tiempo pase el usuario sin devolver el dinero. Esto se lograría mediante una tarea programada que actualice la deuda periódicamente.

> "El sistema de crédito debe actuar como una herramienta de doble filo: proporciona liquidez inmediata para inversiones en mascotas o roles, pero penaliza severamente la morosidad mediante la acumulación de intereses que pueden superar el capital original si no se gestionan a tiempo."

Para garantizar la viabilidad, se sugiere la siguiente estructura de intereses:

| Concepto | Valor Propuesto | Descripción |
| :--- | :--- | :--- |
| **Tasa Base** | 2% - 5% | Interés inicial aplicado al solicitar el préstamo. |
| **Intervalo de Interés** | Cada 24 horas | Frecuencia con la que la deuda aumenta automáticamente. |
| **Límite de Crédito** | 20% del Patrimonio | Basado en la suma de `wallet` + `bank` + valor de inventario. |
| **Penalización por Mora** | +1% adicional | Incremento de la tasa si la deuda no se reduce en 7 días. |

### 2.2. Implementación Técnica Sugerida

La integración requeriría modificar la colección `economy` en la base de datos para incluir campos específicos como `loan_balance`, `interest_rate` y `last_interest_update`. El comando `!loan` verificaría que el usuario no tenga deudas previas y calcularía su límite máximo basándose en su actividad económica histórica para evitar el abuso por parte de cuentas nuevas.

Además, se recomienda implementar una **amortización automática**. Esto significa que un porcentaje de los ingresos obtenidos a través de `!work` o `!daily` se deduciría automáticamente para pagar la deuda pendiente. Este mecanismo asegura que el bot recupere el capital prestado incluso si el usuario no utiliza el comando `!repay` voluntariamente.

## 3. Restricciones y Seguridad Económica

Para evitar que el sistema de préstamos desestabilice la economía del clan, es fundamental imponer restricciones estrictas a los deudores. Un usuario con un préstamo activo no debería poder transferir dinero a otros mediante `!pay`, ni participar en juegos de alta apuesta como la ruleta con dinero prestado. Estas medidas previenen el "lavado de dinero" entre cuentas y aseguran que el crédito se utilice para la progresión dentro del juego, como la compra de mascotas o suministros, y no para apuestas temerarias que perpetúen el ciclo de deuda.

En conclusión, añadir un sistema de crédito no solo es posible, sino recomendable para dar sentido a los saldos negativos actuales. La clave del éxito reside en la **automatización de los intereses**, haciendo que la deuda sea una carga real que el usuario deba priorizar, añadiendo así una capa de realismo y gestión al bot del clan Usaosne.

## Referencias
[1] [Repositorio quimcressonjodar/bot](https://github.com/quimcressonjodar/bot) - Código fuente original del bot de economía.
[2] [Documentación de discord.py](https://discordpy.readthedocs.io/) - Librería base utilizada para la implementación de comandos y tareas programadas.
