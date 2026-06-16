import json, re, urllib.request, sys
from datetime import date, timedelta

ALIAS = {
    'SKO':'KOR','KOR':'KOR','MEX':'MEX','CZE':'CZE','RSA':'RSA','SAF':'RSA',
    'CAN':'CAN','SUI':'SUI','QAT':'QAT','BIH':'BIH','BOS':'BIH',
    'BRA':'BRA','MAR':'MAR','MOR':'MAR','SCO':'SCO','HAI':'HAI',
    'USA':'USA','AUS':'AUS','PAR':'PAR','TUR':'TUR',
    'GER':'GER','ECU':'ECU','CIV':'CIV','IVC':'CIV','CUW':'CUW','CUR':'CUW',
    'NED':'NED','JPN':'JPN','SWE':'SWE','TUN':'TUN',
    'BEL':'BEL','IRN':'IRN','IRI':'IRN','EGY':'EGY','NZL':'NZL',
    'ESP':'ESP','URU':'URU','KSA':'KSA','SAU':'KSA','CPV':'CPV',
    'FRA':'FRA','SEN':'SEN','NOR':'NOR','IRQ':'IRQ',
    'ARG':'ARG','AUT':'AUT','ALG':'ALG','JOR':'JOR',
    'POR':'POR','COL':'COL','COD':'COD','DRC':'COD','UZB':'UZB',
    'ENG':'ENG','CRO':'CRO','GHA':'GHA','PAN':'PAN',
}

def fetch(datestr):
    url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={datestr}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except:
        return {}

# ESPN home/away 기준으로 완료된 경기 점수 수집
# scores[(espn_home_id, espn_away_id)] = (home_score, away_score)
scores = {}
for i in range(20):  # 6/11 ~ 6/29
    d = date(2026, 6, 11) + timedelta(days=i)
    data = fetch(d.strftime('%Y%m%d'))
    for ev in data.get('events', []):
        comp = ev['competitions'][0]
        if not comp.get('status', {}).get('type', {}).get('completed'):
            continue
        home = next((c for c in comp['competitors'] if c['homeAway'] == 'home'), None)
        away = next((c for c in comp['competitors'] if c['homeAway'] == 'away'), None)
        if not home or not away:
            continue
        hId = ALIAS.get(home['team']['abbreviation'].upper())
        aId = ALIAS.get(away['team']['abbreviation'].upper())
        if hId and aId:
            try:
                scores[(hId, aId)] = (int(float(home['score'])), int(float(away['score'])))
            except:
                pass

print(f"완료된 경기: {len(scores)}개")

with open('worldcup2026.html', encoding='utf-8') as f:
    html = f.read()

def update_match(m):
    full = m.group(0)
    h_m = re.search(r"h:'([A-Z]+)'", full)
    a_m = re.search(r"a:'([A-Z]+)'", full)
    if not h_m or not a_m:
        return full
    h, a = h_m.group(1), a_m.group(1)

    sc = scores.get((h, a))
    if sc:
        hs_html, as_html = sc[0], sc[1]
    else:
        sc = scores.get((a, h))
        if sc:
            hs_html = sc[1]  # HTML의 h팀 = ESPN의 away팀
            as_html = sc[0]  # HTML의 a팀 = ESPN의 home팀
        else:
            return full  # 아직 미완료

    # 기존 hs/as 제거 후 새 값 추가
    clean = re.sub(r',\s*hs:\d+,\s*as:\d+', '', full)
    clean = clean[:-1] + f',hs:{hs_html},as:{as_html}' + '}'
    print(f"  {h} {hs_html}-{as_html} {a}")
    return clean

pattern = r"\{[^}]*h:'[A-Z]+'[^}]*a:'[A-Z]+'[^}]*\}"
updated = re.sub(pattern, update_match, html)

if updated == html:
    print("변경 없음")
    sys.exit(0)

with open('worldcup2026.html', 'w', encoding='utf-8') as f:
    f.write(updated)

print("HTML 업데이트 완료")
