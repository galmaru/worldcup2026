import json, re, urllib.request, sys, os
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

NAMES = {
    'MEX':'멕시코','KOR':'대한민국','CZE':'체코','RSA':'남아공',
    'CAN':'캐나다','SUI':'스위스','QAT':'카타르','BIH':'보스니아',
    'BRA':'브라질','MAR':'모로코','SCO':'스코틀랜드','HAI':'아이티',
    'USA':'미국','AUS':'호주','PAR':'파라과이','TUR':'튀르키예',
    'GER':'독일','ECU':'에콰도르','CIV':'코트디부아르','CUW':'퀴라소',
    'NED':'네덜란드','JPN':'일본','SWE':'스웨덴','TUN':'튀니지',
    'BEL':'벨기에','IRN':'이란','EGY':'이집트','NZL':'뉴질랜드',
    'ESP':'스페인','URU':'우루과이','KSA':'사우디아라비아','CPV':'카보베르데',
    'FRA':'프랑스','SEN':'세네갈','NOR':'노르웨이','IRQ':'이라크',
    'ARG':'아르헨티나','AUT':'오스트리아','ALG':'알제리','JOR':'요르단',
    'POR':'포르투갈','COL':'콜롬비아','COD':'DR콩고','UZB':'우즈베키스탄',
    'ENG':'잉글랜드','CRO':'크로아티아','GHA':'가나','PAN':'파나마',
}

def fetch(datestr):
    url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={datestr}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except:
        return {}

scores = {}
for i in range(20):
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

with open('worldcup2026.html', encoding='utf-8') as f:
    html = f.read()

# 기존 점수 추출 (변경 감지용)
existing = {}
for m in re.finditer(r"\{[^}]*h:'([A-Z]+)'[^}]*a:'([A-Z]+)'[^}]*hs:(\d+),as:(\d+)[^}]*\}", html):
    existing[(m.group(1), m.group(2))] = (int(m.group(3)), int(m.group(4)))

changes = []

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
            hs_html, as_html = sc[1], sc[0]
        else:
            return full

    if existing.get((h, a)) != (hs_html, as_html):
        hn, an = NAMES.get(h, h), NAMES.get(a, a)
        changes.append(f"{hn} {hs_html} - {as_html} {an}")

    clean = re.sub(r',\s*hs:\d+,\s*as:\d+', '', full)
    clean = clean[:-1] + f',hs:{hs_html},as:{as_html}' + '}'
    return clean

pattern = r"\{[^}]*h:'[A-Z]+'[^}]*a:'[A-Z]+'[^}]*\}"
updated = re.sub(pattern, update_match, html)

# 변경된 경기 목록을 파일로 저장 (workflow에서 Slack 알림에 사용)
if changes:
    with open('changes.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(changes))
    print(f"신규 업데이트 {len(changes)}경기: {', '.join(changes)}")
else:
    if os.path.exists('changes.txt'):
        os.remove('changes.txt')
    print("변경 없음")

if updated == html:
    sys.exit(0)

with open('worldcup2026.html', 'w', encoding='utf-8') as f:
    f.write(updated)
