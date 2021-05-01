import requests
import hashlib
import logging
import bencode
import traceback
import os, sys
import argparse
import json
import time
from config import CONFIG

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

FISH_HEADERS = requests.utils.default_headers()
FISH_HEADERS['User-Agent'] = "FishRSS"
SITE_CONST = {
    "dic":{
        "domain": "dicmusic.club",
        "source": "DICMusic",
    },
    "snake":{
        "domain": "snakepop.art",
        "source": "Snakepop",
    },
}

def check_path(path, is_file=False, auto_create=False):
    if path is not None:
        abspath = os.path.abspath(path)
        if os.path.exists(abspath):
            if is_file and not os.path.isfile(abspath):
                logging.warning("path {} must be a file".format(path))
                exit(0)
            if not is_file and not os.path.isdir(abspath):
                logging.warning("path {} must be a folder".format(path))
                exit(0)
        else:
            if not auto_create:
                logging.warning("path doesn't exist: {} ".format(path))
                exit(0)
            else:
                if is_file:
                    logging.info("file automatically created: {}".format(path))
                    folder = os.path.split(abspath)[0]
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    with open(abspath, "w") as _:
                        pass
                else:
                    logging.info("directory automatically created: {}".format(path))
                    os.makedirs(path)
check_path(CONFIG["torrent_dir"], is_file=False, auto_create=True)
check_path(CONFIG["downloaded_urls"], is_file=True, auto_create=True)

def get_info_hash(raw):
    info = bencode.decode(raw)["info"]
    info_raw = bencode.encode(info)
    sha = hashlib.sha1(info_raw)
    info_hash = sha.hexdigest()    
    return info_hash
def get_name(raw):
    info = bencode.decode(raw)["info"]
    return info["name"]

parser = argparse.ArgumentParser()
parser.add_argument('--site', required=True, choices=["dic", "snake"],
                    help="rss的站点: 填dic或snake")
parser.add_argument("--init", action="store_true", default=False,
                    help="如果加了此选项，则只记录rss到的历史但不保存到watch文件夹里")
if len(sys.argv) == 1:
    parser.print_help()
    exit(0)
args = parser.parse_args()

SITE = CONFIG[args.site]
site_domain = SITE_CONST[args.site]["domain"]
authkey = SITE["authkey"]
torrent_pass = SITE["torrent_pass"]
cookies = SITE["cookies"]
token_thresh = SITE["token_thresh"]

try:
    resp = requests.get("https://{}/ajax.php?action=notifications".format(site_domain), 
        cookies=cookies, headers=FISH_HEADERS, timeout=10)
    tlist = json.loads(resp.text)["response"]["results"]
except:
    logging.info("fail to read from RSS url")
    logging.info(traceback.format_exc())
    exit()
with open(CONFIG["downloaded_urls"], "r") as f:
    downloaded = set([line.strip() for line in f])
logging.info("{} torrents in rss result".format(len(tlist)))
cnt = 0
now = time.time()
for t in tlist[:10]:
    tid = t["torrentId"]
    dl_url_raw = "https://{}/torrents.php?action=download&id={}&authkey={}&torrent_pass={}".format(
        site_domain, tid, authkey, torrent_pass)
    if dl_url_raw in downloaded:
        continue
    if token_thresh[0] <= t["size"] and t["size"] <= token_thresh[1]:
        logging.info("using token")
        dl_url = dl_url_raw + "&usetoken=1"
    else:
        dl_url = dl_url_raw
    logging.info("downloading .torrent file from {}".format(dl_url))
    if args.init:
        logging.info("ignored")
        with open(CONFIG["downloaded_urls"], "a") as f:
            f.write("{}\n".format(dl_url_raw))
        continue
    try:
        resp = requests.get(dl_url, headers=FISH_HEADERS, timeout=120)
        raw = resp.content
        h = get_info_hash(raw)
        logging.info("hash={}".format(h))
        with open(CONFIG["downloaded_urls"], "a") as f:
            f.write("{}\n".format(dl_url_raw))
        save_path = os.path.join(CONFIG["torrent_dir"], "{}.torrent".format(get_name(raw)))
        logging.info("saving to {}".format(save_path))
        with open(save_path, "wb") as f:
            f.write(raw)
        cnt += 1
        time.sleep(2)
    except KeyboardInterrupt:
        logging.info(traceback.format_exc())
        break
    except:
        logging.info("fail to download:")
        logging.info(traceback.format_exc())        
logging.info("{} torrents added".format(cnt))
