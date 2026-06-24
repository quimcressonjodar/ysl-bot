# 🏆 YSL Bot - Protox.io Clan

Bot oficial de Discord para el clan **YSL** de [Protox.io](https://protox.io).

Este bot proporciona un conjunto completo de herramientas para la gestión del servidor y el seguimiento de jugadores, construido con una arquitectura modular y escalable.

## ✨ Características Principales

*   **🎮 Integración con Protox.io**:
    *   Vinculación de cuentas Discord <-> Player ID.
    *   Consulta de perfiles y estadísticas en tiempo real.
    *   Seguimiento automático de XP semanal mediante Snapshots programados.
    *   Leaderboard semanal interno del clan.
*   **🛡️ Moderación Avanzada**:
    *   Sistema de warnings (advertencias).
    *   Timeouts (mute), kicks y bans.
    *   Purga de mensajes.
    *   Logs detallados de moderación.
*   **🎫 Sistema de Tickets**:
    *   Creación de tickets mediante botones interactivos.
    *   Canales privados temporales para soporte.
    *   Registro en base de datos.
*   **👋 Bienvenidas y Utilidades**:
    *   Mensajes automáticos de bienvenida y despedida.
    *   Información detallada de usuarios y del servidor.
    *   Comandos administrativos para configurar el servidor dinámicamente.
*   **🌐 Backend Web Integrado**:
    *   Servidor Flask ejecutándose en segundo plano.
    *   Endpoints REST (`/api/users`, `/api/stats`, `/api/leaderboard`).
    *   Preparado para ser alojado en plataformas como Render o Heroku (incluye endpoint `/health`).

## 🏗️ Arquitectura

El proyecto sigue una estructura modular basada en **Cogs** de `discord.py`, respaldado por **MongoDB** para la persistencia de datos.

```text
ysl-bot/
├── cogs/               # Módulos del bot (comandos y eventos)
│   ├── admin.py        # Comandos de configuración y administración
│   ├── moderation.py   # Warns, mutes, kicks, bans, purge
│   ├── protox.py       # Integración con API de Protox y tracking de XP
│   ├── tickets.py      # Sistema de soporte
│   ├── utility.py      # Comandos de información y ayuda
│   └── welcome.py      # Eventos de entrada/salida de miembros
├── database/           # Conexión y colecciones de MongoDB
├── utils/              # Funciones auxiliares y formateadores
│   ├── protox_api.py   # Cliente HTTP asíncrono para la API del juego
│   ├── formatters.py   # Generadores de embeds consistentes
│   └── helpers.py      # Verificaciones de permisos y utilidades
├── web/                # Servidor backend (Flask)
├── config.py           # Configuración central y variables de entorno
└── main.py             # Punto de entrada principal
```

## 🚀 Instalación y Configuración

### 1. Requisitos Previos

*   Python 3.10 o superior.
*   Una base de datos MongoDB (MongoDB Atlas recomendado).
*   Un token de bot de Discord (obtenido en el [Developer Portal](https://discord.com/developers/applications)).

### 2. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/ysl-bot.git
cd ysl-bot
```

### 3. Instalar dependencias

Se recomienda usar un entorno virtual:

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo de ejemplo y rellena tus datos:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
DISCORD_TOKEN=tu_token_aqui
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/ysl_bot
PROTOX_API_BASE=https://api.protox.io
CLAN_NAME=YSL
WEEKLY_XP_REQUIREMENT=50000
PORT=10000
```

### 5. Ejecutar el bot

```bash
python main.py
```

## 🔧 Configuración inicial en Discord

Una vez que el bot esté en tu servidor, usa los siguientes comandos (requieren permisos de Administrador):

1.  `/setwelcome <canal>` - Define dónde se enviarán las bienvenidas.
2.  `/setlog <canal>` - Define dónde se registrarán las acciones de moderación.
3.  `/ticketsetup <canal>` - Envía el panel interactivo para que los usuarios abran tickets.

## 📝 Comandos Destacados

Todos los comandos del bot utilizan la nueva API de Slash Commands (`/`).

*   `/register <player_id> <username>`: Vincula tu cuenta de Protox.io.
*   `/weeklyxp`: Comprueba tu progreso hacia la meta semanal de XP.
*   `/leaderboard`: Muestra el Top 15 del clan en la semana actual.
*   `/warn <usuario> <razón>`: Advierte a un miembro.
*   `/mute <usuario> <duración>`: Aplica un timeout temporal.

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.
