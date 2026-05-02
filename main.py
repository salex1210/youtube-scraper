import asyncio
from datetime import datetime
import mysql.connector
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import os
import unicodedata
import re

URL = "https://charts.youtube.com/charts/TopArtists/co/weekly"


MESES_ES = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}

# ===============================
# UTILIDADES
# ===============================

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.strip().lower()

def parse_fecha_es(fecha_str: str) -> str:
    if not fecha_str:
        return None

    fecha_str = normalize_text(fecha_str)
    fecha_str = re.sub(r"[•·]", "", fecha_str)
    fecha_str = re.sub(r"[.,]", "", fecha_str)

    # Caso: ya viene en formato ISO
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return fecha_str
    except:
        pass

    # Caso: 11/01/2025
    
    try:
        dt = datetime.strptime(fecha_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        pass

    partes = fecha_str.split()
    if len(partes) < 3:
        return None

    dia, mes_txt, anio = partes[:3]
    dia = re.sub(r"\D", "", dia)

    mes = MESES_ES.get(mes_txt)
    if not mes:
        return None

    fecha_mysql = f"{anio}-{mes}-{int(dia):02d}"
    try:
        datetime.strptime(fecha_mysql, "%Y-%m-%d")
        return fecha_mysql
    except:
        return None


def parse_views(text):
    if not text:
        return None

    text = text.lower().strip()

    if text in ["-", "—", ""]:
        return None

    text = text.replace("<", "")

    for word in ["visualizaciones", "vistas"]:
        text = text.replace(word, "")

    text = text.replace(",", "").strip()

    try:
        if "m" in text:
            return int(float(text.replace("m", "")) * 1_000_000)
        if "k" in text:
            return int(float(text.replace("k", "")) * 1_000)
        return int(float(text))
    except ValueError:
        return None


async def ensure_row_visible(page, index):
    container = page.locator("ytmc-table-body")

    for _ in range(20):
        rows = await page.locator("ytmc-entry-row").count()
        if index < rows:
            row = page.locator("ytmc-entry-row").nth(index)
            await row.scroll_into_view_if_needed()
            await page.wait_for_timeout(200)
            return

        await container.evaluate("el => el.scrollBy(0, el.clientHeight)")
        await page.wait_for_timeout(500)

    raise TimeoutError(f"No se pudo renderizar la fila {index}")

# ===============================
# SCRAPING
# ===============================

async def wait_for_table(page):
    await page.wait_for_load_state("domcontentloaded")
    for _ in range(15):
        if await page.locator("ytmc-entry-row").count() > 0:
            return
        await page.wait_for_timeout(1000)
    raise TimeoutError("La tabla de artistas no cargó")

async def process_artist(page, index):
    await ensure_row_visible(page, index)
    row = page.locator("ytmc-entry-row").nth(index)

    # ===============================
    # DATOS DESDE LA FILA
    # ===============================
    rank = (await row.locator("#rank").inner_text()).strip()
    name = (await row.locator(".artistName").inner_text()).strip()
    print(f"\nProcesando: {name}")

    metrics = row.locator(".metric.content")

    try:
        weeks_on_chart = (await metrics.nth(1).inner_text()).strip()
    except:
        weeks_on_chart = None

    try:
        weeks_on_the_list = (await metrics.nth(2).inner_text()).strip()
    except:
        weeks_on_the_list = None

    try:
        weekly_views_raw = (await metrics.nth(3).inner_text()).strip()
    except:
        weekly_views_raw = None

    weekly_views = parse_views(weekly_views_raw)

    artist = row.locator(".artistName")

    # ===============================
    # CLICK ROBUSTO
    # ===============================
    clicked = False

    try:
        await row.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await artist.wait_for(state="visible", timeout=10000)
        await artist.click()
        clicked = True
    except:
        try:
            await page.evaluate(
                "(el) => el.click()",
                await artist.element_handle()
            )
            clicked = True
        except Exception as e:
            print(f"⚠ No se pudo hacer click en {name}: {e}")

    if not clicked:
        return {
            "rank": int(rank),
            "artist": name,
            "last_week": parse_views(weeks_on_chart),
            "weeks_on_the_list": weeks_on_the_list,
            "weekly_views": weekly_views,
            "total_views": None,
            "yesterday_views": None,
            "artist_url": None,
            "img_url": None,
            "executed_at": None
        }

    # Esperar navegación
    try:
        await page.wait_for_url("**/artist/**", timeout=30000)
    except:
        print(f"⚠ No se pudo navegar al artista {name}")
        return {
            "rank": int(rank),
            "artist": name,
            "last_week": parse_views(weeks_on_chart),
            "weeks_on_the_list": weeks_on_the_list,
            "weekly_views": weekly_views,
            "total_views": None,
            "yesterday_views": None,
            "artist_url": None,
            "img_url": None,
            "executed_at": None
        }

    artist_url = page.url

    # ===============================
    # TOTAL VIEWS
    # ===============================
    try:
        await page.wait_for_selector(
            "#ytmc-views-card-v2-container .views-subtitle",
            timeout=30000
        )

        total_views_raw = (
            await page.locator(
                "#ytmc-views-card-v2-container .views-subtitle"
            ).inner_text()
        ).strip()

        total_views = parse_views(total_views_raw)

    except PlaywrightTimeout:
        total_views = None

    # ===============================
    # VISTA DE AYER
    # ===============================
    try:
        # Selecciona el último tr del tbody
        yesterday_view = page.locator("tbody tr:last-child td:nth-child(2)")
        view_1 = (await yesterday_view.inner_text()).strip()
        views_ayer = parse_views(view_1)
        # views_ayer = parse_views(view_1)
    except:
        views_ayer = None

    try:
        date_view = page.locator("tr:nth-child(28) td:nth-child(1)")
        date = parse_fecha_es((await date_view.inner_text()).strip())
    except Exception as e:
        print(f"⚠ Fecha inválida: {e}")
        date = None

    try:
        img = await page.wait_for_selector("img#hero-banner-image", timeout=10000)
        img_url = await img.get_attribute("src")
    except:
        img_url = None

    # ===============================
    # VOLVER A LA LISTA
    # ===============================
    await page.go_back()
    await wait_for_table(page)

    print("────────────────────────────")
    print(f"Artista             : {name}")
    print(f"Rank                : {rank}")
    print(f"Última semana       : {weeks_on_chart}")
    print(f"Semanas en la lista : {weeks_on_the_list}")
    print(f"Visualizaciones     : {weekly_views}")
    print(f"Total views         : {total_views}")
    print(f"yesterday views     : {views_ayer}")
    print(f"Date created        : {date}")

    return {
        "rank": int(rank),
        "artist": name,
        "last_week": parse_views(weeks_on_chart),
        "weeks_on_the_list": weeks_on_the_list,
        "weekly_views": weekly_views,
        "total_views": total_views,
        "yesterday_views": views_ayer,
        "artist_url": artist_url,
        "img_url": img_url,
        "executed_at": date
    }

# ===============================
# PROCESO PRINCIPAL
# ===============================

async def main():
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(URL, wait_until="networkidle")
        await wait_for_table(page)

        total = await page.locator("ytmc-entry-row").count()
        print(f"\nArtistas encontrados: {total}")

        for i in range(total):
            try:
                data = await process_artist(page, i)
                results.append(data)
            except Exception as e:
                print(f"Error artista índice {i}: {e}")

        await browser.close()

    # ===============================
    # GUARDAR EN MYSQL
    # ===============================
    conn = get_db_connection()
    cursor = conn.cursor()

    for data in results:
        try:
            artist_id = get_or_create_artist(
                cursor,
                data["artist"],
                data["artist_url"],
                data["img_url"]
            )

            insert_artist_metrics(cursor, artist_id, data)
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"Error DB artista {data['artist']}: {e}")

    cursor.close()
    conn.close()

    print("MySQL actualizado correctamente")

# ===============================
# BASE DE DATOS
# ===============================

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        auth_plugin="mysql_native_password"
    )


def get_or_create_artist(cursor, name, url, img_url):
    cursor.execute(
        "SELECT id FROM artists WHERE artist_name = %s",
        (name,)
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO artists (artist_name, artist_url, img_url)
        VALUES (%s, %s, %s)
        """,
        (name, url, img_url)
    )
    return cursor.lastrowid

def insert_artist_metrics(cursor, artist_id, data):
    cursor.execute(
        """
        INSERT INTO artist_metrics (
            artist_id, RankS, weekly_views, total_views, yesterday_views, created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            artist_id,
            data["rank"],
            data["weekly_views"],
            data["total_views"],
            data["yesterday_views"],
            data["executed_at"] or datetime.today().strftime("%Y-%m-%d")
        )
    )

# ===============================
# EJECUCIÓN
# ===============================

if __name__ == "__main__":
    asyncio.run(main())
