# 📊 YouTube Charts Scraper – Top Artists Colombia

Este proyecto es un **web scraper automatizado en Python** que extrae información de los artistas más populares en **YouTube Charts (Colombia)** y guarda métricas en una base de datos **MySQL**.

Utiliza **Playwright (async)** para navegar por contenido dinámico, visitar el perfil de cada artista y almacenar estadísticas como visualizaciones semanales, vistas totales, vistas del día anterior y ranking.

---

## 🚀 Funcionalidades

- 🔍 Scraping desde:  
  **YouTube Charts – Top Artists Colombia (semanal)**
- 📈 Métricas recolectadas:
  - Ranking semanal
  - Visualizaciones semanales
  - Total de visualizaciones
  - Visualizaciones del día anterior
  - Semanas en lista
  - URL del artista
  - Imagen del artista
- 💾 Persistencia en **MySQL** con control de duplicados.
- ⚙️ Manejo robusto de errores, navegación y renderizado dinámico.
- 🔁 Preparado para automatización (cron, Docker, ECS, Lambda).

---

## 🛠️ Tecnologías

- **Python 3.10**
- **Playwright (async)**
- **MySQL**
- **Docker**
- **AWS (opcional: ECS / Lambda)**

---

## 📂 Estructura de Base de Datos

### Tabla: `artists`
| Campo | Tipo | Descripción |
|------|------|-------------|
| id | INT | ID del artista |
| artist_name | VARCHAR | Nombre del artista |
| artist_url | TEXT | Enlace al perfil |
| img_url | TEXT | Imagen del artista |

### Tabla: `artist_metrics`
| Campo | Tipo | Descripción |
|------|------|-------------|
| id | INT | ID del registro |
| artist_id | INT | Relación con `artists` |
| RankS | INT | Ranking semanal |
| weekly_views | BIGINT | Vistas semanales |
| total_views | BIGINT | Vistas totales |
| yesterday_views | BIGINT | Vistas del día anterior |
| created_at | DATE | Fecha de ejecución |

---

## ⚙️ Instalación Local

### 1️⃣ Clonar repositorio
```bash
git clone https://github.com/tu-usuario/youtube-scraper.git
cd youtube-scraper
