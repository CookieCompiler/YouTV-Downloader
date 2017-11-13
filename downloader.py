import datetime
import os
import json

from bs4 import BeautifulSoup
import dateutil.parser
import requests

CHUNKSIZE = 8 * 1024 * 1024  # 8 MB


def run():
    config = readConfig()
    username = config.get('username')
    password = config.get('password')
    premium = config.get('premium')
    path = config.get('storage_path')
    s = init(path)
    login(s, username, password)

    # record all broadcasts next 24 hours
    for broadcast in config.get('broadcasts'):
        record(s, broadcast.get('title'), broadcast.get('filter'))

    # download recorded broadcasts
    download(s, path)


def init(path):
    if not os.path.isdir(path):
        os.makedirs(path)

    return requests.Session()


def login(s, user, password):
    s.post("https://youtv.de/login", {"session[email]": user, "session[password]": password})


def readConfig():
    return json.load(open('config.json'))


def cleanstring(s):
    return s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss").replace("Ä", "Ae").replace("Ö",
            "Oe").replace("Ü", "Ue").replace(" ", "_")


def makefilename(rec):
    if rec['series_number'] is None or rec['series_season'] is None:
        return rec['starts_at'][0:19].replace("T", "_").replace(":", "-") + "_" + cleanstring(rec['title']) + "_" + \
               rec['channel_name'].lower().replace(" ", "-") + ".mp4"
    else:
        return "S" + makedoubledigit(rec['series_season']) + "E" + makedoubledigit(
            rec['series_number']) + "_" + cleanstring(rec['title']) + ".mp4"


def makedoubledigit(n):
    if n > 9:
        return str(n)
    else:
        return "0" + str(n)


def getremotefileurl(s, url):
    soup = BeautifulSoup(s.get(url).text, 'html.parser')
    sources = soup.find_all('source')
    # FIXME: sort the list by resolution and take the first element
    if len(sources) == 4:
        return sources[2]['src']
    elif len(sources) == 2:
        return sources[0]['src']


def download(s, path):
    recordings = s.get('https://www.youtv.de/api/v2/recs.json').json().get('recordings')
    for rec in recordings:
        if rec.get('status') == 'recorded':
            url = getremotefileurl(s, "https://www.youtv.de/tv-sendungen/" + str(rec.get('id')) + "/streamen")
            video = s.get(url, stream=True)
            with open(path + makefilename(rec), "wb") as file:
                for chunk in video.iter_content(chunk_size=CHUNKSIZE):
                    if chunk:
                        file.write(chunk)
            delete(s, rec.get('id'))


def delete(s, rid):
    s.delete('https://www.youtv.de/api/v2/recordings/' + str(rid) + '.json')


def record(s, title, filters):
    response = s.get('https://www.youtv.de/api/v2/search/broadcasts.json?title=' + title).json()
    for broadcast in response.get('search').get('broadcasts'):
        if dateutil.parser.parse(broadcast.get('starts_at')).replace(tzinfo=None) <= datetime.datetime.now() + datetime.timedelta(days=1):
            if broadcast['production_year'] >= filters['min_productionyear']:
                data = {"recording": {"broadcast_id": broadcast.get("id")}}
                s.post('https://www.youtv.de/api/v2/recordings.json', json=data)


run()