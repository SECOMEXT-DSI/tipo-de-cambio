import json, ssl, math, bs4, datetime, sqlite3, tweepy, facebook, urllib.request, requests, time, urllib3
from PIL import Image, ImageDraw, ImageFont

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#PATH
full_path = "/home/dsi-desarrollo/DSI-Develops/tipo_de_cambio/"

#TOKENS
with open(f"{full_path}config.json") as f:
    config = json.load(f)

CONSUMER_KEY = config["CONSUMER_KEY"]
CONSUMER_SECRET = config["CONSUMER_SECRET"]
ACCESS_TOKEN = config["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = config["ACCESS_TOKEN_SECRET"]

access_token = config["access_token"]

TOKEN_TELEGRAM = config["TOKEN_TELEGRAM"]
CHAT_ID = config["CHAT_ID"]



def send_telegram_message(text):
    url = f"https://149.154.167.220/bot{TOKEN_TELEGRAM}/sendMessage?chat_id={CHAT_ID}&text={text}"
    headers = {'Host': 'api.telegram.org'}  # Especifica el nombre de host correcto

    try:
        # Deshabilita la verificación SSL
        response = requests.get(url, headers=headers, verify=False, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error en la solicitud: {e}")
    
    time.sleep(2)
    
def obtain_change(date):
    day = "{:02}".format(date.day)
    month = "{:02}".format(date.month)
    year = "{:04}".format(date.year)
    url = f"https://dof.gob.mx/indicadores_detalle.php?cod_tipo_indicador=158&dfecha={day}%2F{month}%2F{year}&hfecha={day}%2F{month}%2F{year}"
    contents = urllib.request.urlopen(url)
    soup = bs4.BeautifulSoup(contents, 'html.parser')
    indicator_row = soup.find("tr", "Celda 1")
    if indicator_row:
        return str(indicator_row.findAll("td")[-1].renderContents())[2:-3], "SI"
    else:
        return "N/V", "NO"
    
def comprobate_secomext(value):
    url = "https://www.secomext.com.mx/sc_index.html"
    contents = urllib.request.urlopen(url)
    soup = bs4.BeautifulSoup(contents, 'html.parser')
    value_secomext = soup.find(attrs={'id':'catTipoCambioResultado'})
    if math.trunc(float(value_secomext.text)*10000) == math.trunc(float(value[0])*10000):
        return "SI"
    else:
        return "NO"

        
def write_data(date, value):
    conn = sqlite3.connect(f'{full_path}db/data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT Fecha FROM Cambio ORDER BY Fecha DESC LIMIT 1")
    last_date = cursor.fetchone()  
    if last_date is None or str(date) != last_date[0]:
        insert_query = """INSERT INTO Cambio (Fecha, Valor) VALUES (?, ?)"""
        cursor.execute(insert_query, (str(date), value))
        conn.commit()
    conn.close()
    
def obtain_last_data():
    conn = sqlite3.connect(f'{full_path}db/data.db')
    cursor = conn.cursor()
    query = """SELECT Valor FROM Cambio WHERE Valor != 'N/V' ORDER BY ID DESC LIMIT 2"""
    cursor.execute(query)
    last_value = cursor.fetchall()

    query2 = """SELECT Valor FROM Cambio ORDER BY ID DESC LIMIT 2"""
    cursor.execute(query2)
    last_row = cursor.fetchall()
    
    conn.close()

    if last_row[0][0] == "N/V":
        return last_value[0][0], last_value[0][0]
    else:
        return last_value[1][0], last_row[0][0]
    
def sync_data(today):
    conn = sqlite3.connect(f'{full_path}db/data.db')
    cursor = conn.cursor()
    
    query = """SELECT Fecha FROM Cambio ORDER BY Fecha DESC LIMIT 1"""
    cursor.execute(query)
    last_date = cursor.fetchone()
    
    conn.close()

    last_date_obj = datetime.datetime.strptime(last_date[0], '%Y-%m-%d')
    current_date = today
    delta_days = (current_date - last_date_obj.date()).days
    days = delta_days
    
    if days == 0:
        date_temp = current_date
        change_temp, status_temp = obtain_change(date_temp)
    else:
        for i in range(days-1, -1, -1):
            date_temp = current_date - datetime.timedelta(days=i)
            change_temp, status_temp = obtain_change(date_temp)
            write_data(date_temp, change_temp)    
    
    return days, last_date, change_temp, status_temp
    
def generate_image(date, values, pvr = 290, iva = 46):
    image = Image.open(f"{full_path}img/TEMPLATE.png")
    draw = ImageDraw.Draw(image)
    font_date = ImageFont.truetype(f"{full_path}fonts/Nunito-Bold.ttf", 35)
    font_value = ImageFont.truetype(f"{full_path}fonts/Nunito-Bold.ttf", 65)
    font_day = ImageFont.truetype(f"{full_path}fonts/Nunito-Bold.ttf", 41)

    today = date.strftime('%d-%m-%Y')
    tomorrow = date + datetime.timedelta(days=1)
    tomorrow = tomorrow.strftime('%d-%m-%Y')

    draw.text((340, 246), today, font=font_date, fill='black')
    draw.text((340, 416), tomorrow, font=font_date, fill='black')

    draw.text((70, 310), f'${values[0]} MXN', font=font_value, fill='white')
    draw.text((70, 480), f'${values[1]} MXN', font=font_value, fill='white')
    draw.text((130, 650), f'${pvr} MXN', font=font_value, fill='white')
    draw.text((150, 820), f'${iva} MXN', font=font_value, fill='white')

    draw.text((445, 936), date.strftime('%j'), font=font_day, fill='black')

    image.save(f"{full_path}img/Tipo_De_Cambio_{str(date)}.png")

def post_social_media(date, client, api, apifb, message):
    twitter_status = "Error al publicar en Twitter"
    try:
        media = api.media_upload(f"{full_path}img/Tipo_De_Cambio_{str(date)}.png")
        client.create_tweet(text=message, media_ids=[media.media_id])
        twitter_status = "Publicado correctamente en X ⬛️"
    except Exception as e:
        print(f"Error en publicar en Twitter: {e}")

    facebook_status = "Error al publicar en Facebook"
    try:
        apifb.put_photo(open(f"{full_path}img/Tipo_De_Cambio_{str(date)}.png", "rb"), message = message)
        facebook_status = "Publicado correctamente en Facebook 🟦"
    except Exception as e:
        print(f"Error al publicar en Facebook: {e}")
    
    return twitter_status, facebook_status

def generate_message(date, values):
    weekdays = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return  f"🔔 Tipo de cambio para este {weekdays[date.weekday()]}: 💵 ${values[0]} MXN. Para mañana, {weekdays[(date.weekday() + 1) % 7]}: ${values[1]} MXN. PRV y IVA/PRV al día. 📲 Más información en nuestro sitio web. #TipoDeCambio #ComercioExterior #SECOMEXT"

#Clientes
client = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)
auth = tweepy.OAuth1UserHandler(
    CONSUMER_KEY,
    CONSUMER_SECRET,
    ACCESS_TOKEN,
    ACCESS_TOKEN_SECRET,
)
api = tweepy.API(auth, wait_on_rate_limit=True)
apifb = facebook.GraphAPI(access_token)

#Main Code

today_temp = datetime.datetime.now() - datetime.timedelta(hours=6)
today = today_temp.date()
days_without_publish, last_day_published, change, estatus_dof = sync_data(today)

data = obtain_last_data()

generate_image(today, data)
message = generate_message(today, data)
twitter_status, facebook_status = post_social_media(today, client, api, apifb, message)

estatus_secomext =  comprobate_secomext(data)

message_temp = f"Se {"tenía" if days_without_publish == 1 else "tenían"} {days_without_publish} {"día" if days_without_publish == 1 else "días"} sin publicar, última publicación el día{last_day_published[0]}. 📆\n\n"

summary = f"RESUMEN DE PUBLICACIÓN ({today}):\n\n{message_temp if days_without_publish > 0 else ""}El DOF {estatus_dof} publico el tipo de cambio hoy.{"✅" if estatus_dof == "SI" else "❌"}\n\nRedes Sociales:\n{twitter_status}\n{facebook_status}\n\nEstatus portal SECOMEXT:\nEl tipo de cambio {estatus_secomext} coincide con el portal de SECOMEXT.{"✅" if estatus_secomext == "SI" else "❌"}\n\nMensaje Enviado:\n{message}."

print(summary)

send_telegram_message(summary)

print(f"Proceso Completado - {today}\n")