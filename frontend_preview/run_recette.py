import csv, json, subprocess, sys, re, html, concurrent.futures as cf, pathlib
P = pathlib.Path(sys.argv[1]); KIT = pathlib.Path(sys.argv[2]); OUT = P / "recette"; OUT.mkdir(exist_ok=True)
rows = list(csv.DictReader(open(KIT / "07_recette/RECETTE.csv", encoding="utf-8")))
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
prev = {}
if ONLY and (OUT / "results.json").exists(): prev = json.load(open(OUT / "results.json"))
SPECIAL = {"R18": (800, 640), "R19": (800, 640), "R43": (1200, 1900)}
LONG = {"R15": 30000, "R22": 45000, "R30": 20000, "R32": 15000, "R11": 25000, "R45": 20000, "R36": 15000}
def chrome(i, mode):
    w, h = SPECIAL.get(i, (800, 1180)); vt = LONG.get(i, 12000)
    args = ["timeout", "120", "google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}", f"--virtual-time-budget={vt}", "--lang=fr-FR"]
    if i == "R48": args.append("--force-prefers-reduced-motion")
    url = f"http://127.0.0.1:8770/?recette={i}#/dashboard"
    if mode == "dom": args += ["--dump-dom", url]
    else: args += [f"--screenshot={OUT}/{i}.png", url]
    return subprocess.run(args, capture_output=True, text=True).stdout
def one(r):
    i = r["id"]; dom = chrome(i, "dom"); m = re.search(r'<pre id="recette-result"[^>]*>(.*?)</pre>', dom, re.S)
    res = json.loads(html.unescape(m.group(1))) if m else {"id": i, "status": "FAIL", "proof": "Aucun résultat (délai ou erreur JS)"}
    chrome(i, "shot"); return i, res
with cf.ThreadPoolExecutor(4) as ex: results = dict(ex.map(one, [r for r in rows if not ONLY or r["id"] in ONLY]))
results = {**prev, **results}; json.dump(results, open(OUT / "results.json", "w"), ensure_ascii=False)
for r in rows:
    res = results[r["id"]]; r["statut_PASS_FAIL_NON_TESTE"] = res["status"]
    r["preuve_ou_commentaire"] = f"[{res.get('viewport','')}, Chrome headless, prévisualisation web démo] {res['proof']} — capture recette/{r['id']}.png"
with open(OUT / "RECETTE_resultats.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
from collections import Counter
print(Counter(results[r["id"]]["status"] for r in rows))
for r in rows:
    if results[r["id"]]["status"] != "PASS": print(r["id"], results[r["id"]]["status"], results[r["id"]]["proof"][:300])
