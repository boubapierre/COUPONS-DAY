
import os
import time
import html
import json
import requests
import re

from pathlib import Path
from datetime import datetime, timedelta, timezone

# ============================================================
# 🔥 TRUECRASHBET V6 — SITE AUTO PUBLISH
# SportMonks + SerpApi + Telegram + Site Web
# ============================================================

SPORTMONKS_BASE = "https://api.sportmonks.com/v3/football"
SERPAPI_URL = "https://serpapi.com/search"
TELEGRAM_BASE = "https://api.telegram.org/bot"

# ============================================================
# CONFIGURATION — CLÉS DIRECTEMENT DANS LE SCRIPT
# ============================================================

SPORTMONKS_API_TOKEN = "7UEXoXoLmFlfS0RZ8THgOqTzS5x22k6caoUAwQkTTf4RPhvNx0392mGmcwsJ"
SERPAPI_API_KEY = "2855b64030c88b79b6f88f3bb4761267ff7559a2a621dedd8a3da2b9916a01fd"
TELEGRAM_BOT_TOKEN = "8705823770:AAGKatSMsEXiU4kgERG6sUIWOPCw6fvagu0"
TELEGRAM_CHAT_ID = "@TRUECRASHBET"

# ============================================================
# CONFIGURATION GÉNÉRALE
# ============================================================

REQUEST_TIMEOUT = 45
SERPAPI_TIMEOUT = 90
TELEGRAM_TIMEOUT = 30

DAYS_AHEAD = 1
MATCH_DELAY = 2
MAX_RETRIES = 3

CONFIDENCE_THRESHOLD = 68
MAX_SITE_PRONOSTICS = 3

MIN_DATETIME = datetime(2026, 9, 13, tzinfo=timezone.utc)

SITE_JSON_PATH = Path("public/pronostics.json")

ANALYZED_FIXTURES = set()

# ============================================================
# PAYS ET DRAPEAUX
# ============================================================

COUNTRY_FLAGS = {
    "england": "🇬🇧",
    "angleterre": "🇬🇧",
    "spain": "🇪🇸",
    "espagne": "🇪🇸",
    "france": "🇫🇷",
    "germany": "🇩🇪",
    "allemagne": "🇩🇪",
    "italy": "🇮🇹",
    "italie": "🇮🇹",
    "argentina": "🇦🇷",
    "brazil": "🇧🇷",
    "bresil": "🇧🇷",
    "europe": "🇪🇺",
    "world": "🌍",
    "asia": "🌏",
    "asie": "🌏",
    "africa": "🌍",
    "afrique": "🌍",
    "portugal": "🇵🇹",
    "russia": "🇷🇺",
    "russie": "🇷🇺",
    "netherlands": "🇳🇱",
    "belgium": "🇧🇪",
    "turkey": "🇹🇷",
    "scotland": "🏴",
    "greece": "🇬🇷",
    "austria": "🇦🇹",
    "switzerland": "🇨🇭",
    "ukraine": "🇺🇦",
    "croatia": "🇭🇷",
    "poland": "🇵🇱",
    "colombia": "🇨🇴",
    "chile": "🇨🇱",
    "uruguay": "🇺🇾",
    "paraguay": "🇵🇾",
    "ecuador": "🇪🇨",
    "peru": "🇵🇪",
    "bolivia": "🇧🇴",
    "mexico": "🇲🇽",
    "united states": "🇺🇸",
    "canada": "🇨🇦",
    "japan": "🇯🇵",
    "south korea": "🇰🇷",
    "china": "🇨🇳",
    "egypt": "🇪🇬",
    "morocco": "🇲🇦",
    "south africa": "🇿🇦",
    "algeria": "🇩🇿",
    "tunisia": "🇹🇳",
    "nigeria": "🇳🇬",
    "ghana": "🇬🇭",
    "senegal": "🇸🇳",
    "cameroon": "🇨🇲",
    "congo": "🇨🇬",
}

# ============================================================
# OUTILS
# ============================================================

def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_name(value):
    value = clean_text(value).lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9à-ÿ\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def safe_int(value, default=0):
    try:
        return int(float(str(value).replace("%", "").strip()))
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        return float(
            str(value).replace("%", "").replace(",", ".").strip()
        )
    except (TypeError, ValueError):
        return default


def escape_telegram(value):
    return html.escape(str(value or ""), quote=False)


def parse_datetime(value):
    if not value:
        return None

    try:
        result = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result.astimezone(timezone.utc)

    except (ValueError, TypeError):
        return None


def parse_fixture_datetime(fixture):
    return parse_datetime(fixture.get("starting_at"))


# ============================================================
# SPORTMONKS
# ============================================================

def sportmonks_get(endpoint, params=None, timeout=REQUEST_TIMEOUT):

    if not SPORTMONKS_API_TOKEN:
        print("❌ Clé SportMonks manquante.")
        return None

    request_params = dict(params or {})
    request_params["api_token"] = SPORTMONKS_API_TOKEN

    url = SPORTMONKS_BASE + endpoint

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = requests.get(
                url,
                headers={"Accept": "application/json"},
                params=request_params,
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json()

            print(
                f"⚠️ SportMonks HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        except requests.RequestException as error:
            print(f"⚠️ SportMonks : {error}")

        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)

    return None


# ============================================================
# COMPÉTITIONS ET MATCHS
# ============================================================

def get_league(fixture):
    league = fixture.get("league")
    return league if isinstance(league, dict) else {}


def get_league_name(fixture):
    return clean_text(
        get_league(fixture).get("name") or "Compétition inconnue"
    )


def get_country_name(fixture):

    league = get_league(fixture)
    country_data = league.get("country")

    if isinstance(country_data, dict):
        if country_data.get("name"):
            return clean_text(country_data["name"])

    if isinstance(country_data, str) and country_data.strip():
        return clean_text(country_data)

    return clean_text(
        league.get("country_name") or "International"
    )


def get_country_flag(country):
    return COUNTRY_FLAGS.get(normalize_name(country), "🌍")


def is_future_fixture(fixture, end_datetime):

    match_datetime = parse_fixture_datetime(fixture)
    now = datetime.now(timezone.utc)

    return bool(
        match_datetime
        and MIN_DATETIME <= match_datetime <= end_datetime
        and match_datetime > now
    )


def get_all_upcoming_fixtures():

    now = datetime.now(timezone.utc)

    start_datetime = max(now, MIN_DATETIME)
    end_datetime = start_datetime + timedelta(days=DAYS_AHEAD)

    print("=" * 65)
    print("🔥 TRUECRASHBET V6 — TOUTES COMPÉTITIONS")
    print(f"📅 Début : {start_datetime.isoformat()}")
    print(f"📅 Fin : {end_datetime.isoformat()}")
    print(f"🎯 Seuil : {CONFIDENCE_THRESHOLD}%")
    print("=" * 65)

    endpoint = (
        f"/fixtures/between/{start_datetime:%Y-%m-%d}/"
        f"{end_datetime:%Y-%m-%d}"
    )

    params = {
        "include": "participants;league;league.country;state;venue;stage;round",
        "per_page": 100,
    }

    all_fixtures = []
    page = 1

    while True:

        params["page"] = page
        data = sportmonks_get(endpoint, params)

        if not data:
            print("❌ Pas de réponse SportMonks.")
            break

        page_data = data.get("data", [])

        if not isinstance(page_data, list):
            break

        all_fixtures.extend(page_data)

        pagination = data.get("pagination", {})

        if not isinstance(pagination, dict):
            break

        next_page = pagination.get("next_page")

        if next_page:
            page = safe_int(next_page, page + 1)

        elif pagination.get("has_more"):
            page += 1

        else:
            break

        if page > 100:
            print("⚠️ Limite de pagination atteinte.")
            break

    fixtures = {}

    for fixture in all_fixtures:

        if not isinstance(fixture, dict):
            continue

        fixture_id = safe_int(fixture.get("id"))

        if not fixture_id or fixture_id in fixtures:
            continue

        if is_future_fixture(fixture, end_datetime):
            fixtures[fixture_id] = fixture

    result = list(fixtures.values())

    result.sort(
        key=lambda f: parse_fixture_datetime(f)
        or datetime.max.replace(tzinfo=timezone.utc)
    )

    print(f"📥 Matchs reçus : {len(all_fixtures)}")
    print(f"✅ Matchs retenus : {len(result)}")

    return result


# ============================================================
# DONNÉES DES MATCHS
# ============================================================

def get_teams(fixture):

    participants = fixture.get("participants")

    if not isinstance(participants, list):
        return {}, {}

    home, away = {}, {}

    for participant in participants:

        if not isinstance(participant, dict):
            continue

        meta = participant.get("meta", {})
        location = clean_text(
            meta.get("location", "")
        ).lower()

        if location == "home":
            home = participant

        elif location == "away":
            away = participant

    if not home and participants:
        home = participants[0]

    if not away and len(participants) > 1:
        away = participants[1]

    return home, away


def get_team_name(participant):

    if not isinstance(participant, dict):
        return "Équipe inconnue"

    return clean_text(
        participant.get("name") or "Équipe inconnue"
    )


def build_fixture_dataset(fixture):

    home, away = get_teams(fixture)

    league_name = get_league_name(fixture)
    country = get_country_name(fixture)

    match_datetime = parse_fixture_datetime(fixture)

    round_name = ""

    for key in ("round", "stage"):

        item = fixture.get(key)

        if isinstance(item, dict):
            round_name = clean_text(item.get("name", ""))

            if round_name:
                break

    venue = fixture.get("venue")

    if not isinstance(venue, dict):
        venue = {}

    return {
        "fixture_id": safe_int(fixture.get("id")),
        "home": get_team_name(home),
        "away": get_team_name(away),
        "league": league_name,
        "country": country,
        "flag": get_country_flag(country),
        "round": round_name,
        "date": match_datetime.strftime("%d/%m") if match_datetime else "?",
        "time": match_datetime.strftime("%H:%M") if match_datetime else "?",
        "venue": clean_text(venue.get("name", "")),
        "city": clean_text(venue.get("city", "")),
    }


# ============================================================
# SERPAPI — GOOGLE AI MODE
# ============================================================

def serpapi_search(query):

    if not SERPAPI_API_KEY:
        print("❌ Clé SerpApi manquante.")
        return ""

    params = {
        "engine": "google_ai_mode",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "hl": "fr",
        "gl": "fr",
        "device": "mobile",
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                SERPAPI_URL,
                params=params,
                timeout=SERPAPI_TIMEOUT
            )

            if response.status_code != 200:

                print(
                    f"⚠️ SerpApi HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)

                continue

            data = response.json()

            for field in (
                "reconstructed_markdown",
                "answer",
                "ai_overview",
                "text"
            ):

                value = data.get(field)

                if isinstance(value, str) and value.strip():
                    return value.strip()

            text_blocks = data.get("text_blocks")

            if isinstance(text_blocks, list):

                parts = []

                for block in text_blocks:

                    if isinstance(block, dict) and block.get("text"):
                        parts.append(str(block["text"]))

                    elif isinstance(block, str):
                        parts.append(block)

                if parts:
                    return "\n".join(parts).strip()

            answer_box = data.get("answer_box")

            if isinstance(answer_box, dict):

                value = (
                    answer_box.get("answer")
                    or answer_box.get("snippet")
                    or answer_box.get("result")
                )

                if value:
                    return str(value).strip()

            return ""

        except requests.RequestException as error:
            print(f"⚠️ SerpApi : {error}")

        except (ValueError, TypeError) as error:
            print(f"⚠️ Parsing SerpApi : {error}")

        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)

    return ""


# ============================================================
# PROMPT IA
# ============================================================

def build_ai_prompt(dataset):

    return f"""
Tu es un analyste expert en paris sportifs football pré-match.

Analyse ce match avec des informations vérifiables.
N'invente aucune statistique, cote, composition ou historique.

MATCH : {dataset["home"]} vs {dataset["away"]}
PAYS : {dataset["country"]}
COMPÉTITION : {dataset["league"]}
TOUR : {dataset["round"]}
DATE : {dataset["date"]}
HEURE : {dataset["time"]} UTC

ÉVALUE LES MARCHÉS :

- Victoire probable.
- Double chance.
- Buts première mi-temps.
- Moins de 3.5 buts.
- Équipe domicile ou extérieure marque +0.5 / +1.5.
- Résultat 1X2.
- BTTS.
- Total de buts Over/Under.

RÉPONSE STRICTE :

SELECTION: [marché précis]
CONFIDENCE: [nombre de 0 à 100]%
EXACT_SCORE: [score estimé]
ANALYSE: [maximum 15 mots]

Si aucun marché n'est suffisamment fiable, réponds NO_BET.

Ne présente jamais une estimation comme une certitude.
"""


# ============================================================
# EXTRACTION IA
# ============================================================

def clean_ai_response(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace("```", "")
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("`", "")

    return text.strip()


def extract_field(text, names):

    if not text:
        return ""

    lines = clean_ai_response(text).splitlines()

    for index, line in enumerate(lines):

        line = re.sub(r"^[\-*•]\s*", "", line.strip())

        match = re.match(
            r"^\s*([A-Za-zÀ-ÿ_ ]+?)\s*:\s*(.*?)\s*$",
            line
        )

        if not match:
            continue

        label = normalize_name(match.group(1))
        value = match.group(2).strip()

        if any(normalize_name(n) == label for n in names):

            if value:
                return clean_text(value)

            for next_line in lines[index + 1:]:

                next_line = next_line.strip()

                if not next_line:
                    continue

                if re.match(r"^[A-Za-zÀ-ÿ_ ]+\s*:", next_line):
                    break

                return clean_text(next_line)

    return ""


def extract_selection(text):
    return extract_field(text, ["SELECTION", "SÉLECTION"])


def extract_confidence(text):

    value = extract_field(
        text,
        ["CONFIDENCE", "CONFIANCE"]
    )

    match = re.search(r"\d+(?:[.,]\d+)?", value)

    return safe_float(match.group(0)) if match else 0.0


def extract_exact_score(text):
    return extract_field(text, ["EXACT_SCORE", "EXACT SCORE"])


def extract_analysis(text):
    return extract_field(text, ["ANALYSE", "ANALYSIS"])


# ============================================================
# CATÉGORIE DU MARCHÉ
# ============================================================

def detect_market(selection):

    text = normalize_name(selection)

    if "handicap" in text:
        return "Handicap asiatique"

    if any(x in text for x in ("mi temps", "premiere")):
        return "Mi-temps"

    if "exterieure" in text:
        return "Équipe extérieure"

    if any(x in text for x in ("btts", "marquent")):
        return "BTTS"

    if any(x in text for x in ("plus de", "moins de", "over", "under")):
        return "Total buts"

    return "1N2 / Match"


# ============================================================
# FORMAT TELEGRAM
# ============================================================

def build_telegram_message(
    fixture,
    selection,
    confidence,
    exact_score,
    analysis
):

    dataset = build_fixture_dataset(fixture)

    lines = [
        "🔥 <b>TRUECRASHBET</b>",
        f"⚽ <b>{escape_telegram(dataset['home'])} vs "
        f"{escape_telegram(dataset['away'])}</b>",
        f"🏆 {escape_telegram(dataset['league'])} "
        f"({escape_telegram(dataset['flag'])})",
        "",
        f"📌 <b>{escape_telegram(detect_market(selection))} :</b> "
        f"{escape_telegram(selection)}",
        f"📊 <b>Confiance :</b> {confidence:.0f}%",
    ]

    if exact_score:
        lines.append(
            f"🔢 <b>Score :</b> {escape_telegram(exact_score)}"
        )

    if analysis:
        lines.append(
            f"💡 <i>{escape_telegram(analysis)}</i>"
        )

    return "\n".join(lines)


# ============================================================
# ENVOI TELEGRAM
# ============================================================

def send_telegram_message(message):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Configuration Telegram manquante.")
        return False

    url = f"{TELEGRAM_BASE}{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=TELEGRAM_TIMEOUT
        )

        if response.status_code == 200 and response.json().get("ok"):
            print("✅ Telegram envoyé.")
            return True

        print(
            f"❌ Telegram HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    except requests.RequestException as error:
        print(f"❌ Telegram : {error}")

    return False


# ============================================================
# CONSTRUCTION PRONOSTIC POUR LE SITE
# ============================================================

def build_site_prediction(
    fixture,
    selection,
    confidence,
    exact_score,
    analysis
):

    dataset = build_fixture_dataset(fixture)

    return {
        "fixture_id": dataset["fixture_id"],
        "home": dataset["home"],
        "away": dataset["away"],
        "country": dataset["country"],
        "flag": dataset["flag"],
        "league": dataset["league"],
        "round": dataset["round"],
        "date": dataset["date"],
        "time": dataset["time"],
        "timezone": "UTC",
        "market": detect_market(selection),
        "selection": selection,
        "odds": None,
        "confidence": round(confidence, 1),
        "exact_score": exact_score,
        "analysis": analysis,
        "status": "EN ATTENTE"
    }


# ============================================================
# PUBLICATION JSON — SITE TRUECRASHBET
# ============================================================

def publish_site_json(predictions):

    SITE_JSON_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    now = datetime.now(timezone.utc)

    # Maximum trois sélections
    selected = sorted(
        predictions,
        key=lambda p: (
            -p["confidence"],
            p["date"],
            p["time"]
        )
    )[:MAX_SITE_PRONOSTICS]

    data = {
        "brand": "TRUECRASHBET",
        "date": now.date().isoformat(),
        "updated_at": now.isoformat(),
        "timezone": "UTC",
        "total": len(selected),
        "pronostics": selected
    }

    temporary_path = SITE_JSON_PATH.with_suffix(".tmp")

    with open(temporary_path, "w", encoding="utf-8") as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    temporary_path.replace(SITE_JSON_PATH)

    print("\n" + "=" * 65)
    print("🌐 PUBLICATION SITE TRUECRASHBET")
    print(f"📊 Pronostics publiés : {len(selected)}/3")

    for index, prediction in enumerate(selected, 1):

        print(
            f"{index}. {prediction['home']} - "
            f"{prediction['away']} | "
            f"{prediction['confidence']}%"
        )

    print(f"📁 Fichier : {SITE_JSON_PATH}")
    print("=" * 65)

    return selected


# ============================================================
# ANALYSE D'UN MATCH
# ============================================================

def analyse_fixture(fixture):

    fixture_id = safe_int(fixture.get("id"))

    if not fixture_id or fixture_id in ANALYZED_FIXTURES:
        return None

    end_datetime = datetime.now(timezone.utc) + timedelta(days=DAYS_AHEAD)

    if not is_future_fixture(fixture, end_datetime):
        return None

    dataset = build_fixture_dataset(fixture)

    print("-" * 65)

    print(
        f"📌 {dataset['home']} vs {dataset['away']} "
        f"| {dataset['league']}"
    )

    print("🧠 Analyse Google AI Mode...")

    ai_text = serpapi_search(build_ai_prompt(dataset))

    if not ai_text:
        print("❌ Aucune réponse IA.")
        return None

    ai_text = clean_ai_response(ai_text)

    selection = extract_selection(ai_text)
    confidence = extract_confidence(ai_text)
    exact_score = extract_exact_score(ai_text)
    analysis = extract_analysis(ai_text)

    ANALYZED_FIXTURES.add(fixture_id)

    if not selection or selection.upper().strip() == "NO_BET":
        print("⛔ NO_BET ou sélection absente.")
        return None

    confidence = max(0.0, min(100.0, confidence))

    if confidence < CONFIDENCE_THRESHOLD:
        print(f"⛔ Sous le seuil : {confidence}%")
        return None

    print(f"🎯 {selection}")
    print(f"📊 Confiance : {confidence}%")

    return build_site_prediction(
        fixture=fixture,
        selection=selection,
        confidence=confidence,
        exact_score=exact_score,
        analysis=analysis
    )


# ============================================================
# CONFIGURATION
# ============================================================

def check_configuration():

    checks = {
        "SPORTMONKS_API_TOKEN": bool(SPORTMONKS_API_TOKEN),
        "SERPAPI_API_KEY": bool(SERPAPI_API_KEY),
        "TELEGRAM_BOT_TOKEN": bool(TELEGRAM_BOT_TOKEN),
        "TELEGRAM_CHAT_ID": bool(TELEGRAM_CHAT_ID),
    }

    for name, valid in checks.items():
        print(f"{'✅' if valid else '❌'} {name}")

    return all(checks.values())


# ============================================================
# SCAN PRINCIPAL
# ============================================================

def scan():

    fixtures = get_all_upcoming_fixtures()

    if not fixtures:
        print("⚠️ Aucun match trouvé.")
        publish_site_json([])
        return

    candidates = []
    error_count = 0

    print("\n🔥 DÉBUT DE L'ANALYSE")

    for index, fixture in enumerate(fixtures, start=1):

        try:

            prediction = analyse_fixture(fixture)

            if prediction:
                candidates.append(prediction)

        except Exception as error:

            error_count += 1

            print(f"❌ Erreur match : {error}")

        if index < len(fixtures):
            time.sleep(MATCH_DELAY)

    # Sélection des trois meilleurs
    selected = publish_site_json(candidates)

    # Envoi Telegram des trois mêmes sélections
    sent_count = 0

    for prediction in selected:

        fixture = next(
            (
                f for f in fixtures
                if safe_int(f.get("id")) == prediction["fixture_id"]
            ),
            None
        )

        if fixture is None:
            continue

        message = build_telegram_message(
            fixture=fixture,
            selection=prediction["selection"],
            confidence=prediction["confidence"],
            exact_score=prediction["exact_score"],
            analysis=prediction["analysis"]
        )

        if send_telegram_message(message):
            sent_count += 1

    print("\n" + "=" * 65)
    print("🔥 TRUECRASHBET — FIN DU SCAN")
    print(f"📥 Matchs analysés : {len(fixtures)}")
    print(f"🎯 Pronostics admissibles : {len(candidates)}")
    print(f"🌐 Pronostics site : {len(selected)}")
    print(f"📨 Telegram : {sent_count}")
    print(f"❌ Erreurs : {error_count}")
    print("=" * 65)


# ============================================================
# MAIN
# ============================================================

def main():

    print("🔥 TRUECRASHBET V6 — SITE AUTO PUBLISH")

    if not check_configuration():
        print("❌ Configuration incomplète.")
        return

    try:
        scan()

    except KeyboardInterrupt:
        print("🛑 Programme interrompu.")

    except Exception as error:
        print(f"❌ Erreur générale : {error}")


if __name__ == "__main__":
    main()
