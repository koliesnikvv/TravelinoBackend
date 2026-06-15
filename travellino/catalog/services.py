import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from django.core.cache import cache
import google.generativeai as genai

logger = logging.getLogger(__name__)

OTM_API_KEY = os.getenv('OPENTRIPMAP_API_KEY')
OTM_BASE = 'https://api.opentripmap.com/0.1/en/places'

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Fallback chain — tried in order when a model returns 429 (rate limit).
# Add or reorder models here as quotas change.
GEMINI_MODELS = [
    'gemini-3.5-flash',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b',
]


def _gemini_generate(prompt: str, response_mime_type: str = None, temperature: float = 0.1) -> str:
    """
    Calls Gemini with automatic model fallback on rate limit (429).
    Tries each model in GEMINI_MODELS in order.
    Returns response text or raises the last exception if all models fail.
    """
    generation_config_kwargs = {'temperature': temperature}
    if response_mime_type:
        generation_config_kwargs['response_mime_type'] = response_mime_type

    last_exc = None
    for model_name in GEMINI_MODELS:
        try:
            response = genai.GenerativeModel(model_name).generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**generation_config_kwargs),
            )
            return response.text
        except Exception as e:
            err_str = str(e).lower()
            # 429 = quota exceeded, try next model
            # other errors (400, 500 etc) — no point retrying with another model
            if '429' in err_str or 'quota' in err_str or 'rate' in err_str:
                logger.debug(f'Rate limit on {model_name}, switching to next...')
                last_exc = e
                continue
            raise

    logger.error(f'All Gemini models rate limited. Last error: {last_exc}')
    raise last_exc

_AVAILABLE_KINDS = (
    'accomodations,other_hotels,hostels,motels,resorts,campsites,guest_houses,apartments,villas_and_chalet,alpine_hut,'
    'foods,restaurants,cafes,fast_food,bars,pubs,food_courts,bakeries,marketplaces,biergartens,'
    'shops,malls,supermarkets,conveniences,outdoor,'
    'nightclubs,casino,hookah,'
    'sport,diving,surfing,kitesurfing,climbing,skiing,winter_sports,'
    'amusements,amusement_parks,water_parks,ferris_wheels,roller_coasters,miniature_parks,'
    'baths_and_saunas,thermal_baths,saunas,open_air_baths,'
    'architecture,historic_architecture,palaces,manor_houses,wineries,amphitheatres,pyramids,triumphal_archs,'
    'other_buildings_and_structures,skyscrapers,towers,observation_towers,lighthouses,suspension_bridges,'
    'religion,churches,cathedrals,monasteries,mosques,synagogues,buddhist_temples,hindu_temples,'
    'historic,historical_places,historic_districts,fortifications,castles,bunkers,hillforts,'
    'burial_places,cemeteries,war_memorials,mausoleums,'
    'archaeology,megaliths,cave_paintings,'
    'monuments_and_memorials,monuments,milestones,'
    'cultural,museums,art_galleries,aquariums,zoos,planetariums,science_museums,history_museums,military_museums,open_air_museums,archaeological_museums,'
    'theatres_and_entertainments,concert_halls,cinemas,opera_houses,music_venues,'
    'urban_environment,sculptures,fountains,gardens_and_parks,squares,'
    'nature_reserves,national_parks,wildlife_reserves,glaciers,islands,'
    'beaches,white_sand_beaches,golden_sand_beaches,nude_beaches,'
    'waterfalls,other_lakes,canals,lagoons,'
    'mountain_peaks,volcanoes,caves,canyons,rock_formations,'
    'hot_springs,geysers,'
    'interesting_places,view_points,tourist_object'
)

CATEGORY_TO_KINDS = {
    'Culture':   'museums,art_galleries,historic,historic_architecture,architecture,cultural,theatres_and_entertainments,concert_halls,opera_houses,history_museums,archaeological_museums,open_air_museums',
    'Adventure': 'sport,diving,surfing,kitesurfing,climbing,skiing,winter_sports,amusements,amusement_parks,mountain_peaks,caves,canyons,rock_formations',
    'Nature':    'nature_reserves,national_parks,wildlife_reserves,gardens_and_parks,waterfalls,other_lakes,hot_springs,geysers,glaciers,islands',
    'Beaches':   'beaches,white_sand_beaches,golden_sand_beaches,nude_beaches',
    'Nightlife': 'nightclubs,casino,bars,pubs,concert_halls,music_venues,theatres_and_entertainments',
    'Cuisine':   'restaurants,foods,cafes,fast_food,bars,pubs,food_courts,bakeries,marketplaces,biergartens',
    'Wellness':  'baths_and_saunas,thermal_baths,saunas,open_air_baths,gardens_and_parks,hot_springs,nature_reserves',
    'Urban':     'urban_environment,architecture,sculptures,fountains,gardens_and_parks,squares,view_points,skyscrapers',
    'Seclusion': 'nature_reserves,national_parks,wildlife_reserves,glaciers,islands,waterfalls,caves',
}

OUTDOOR_KINDS = {
    'gardens_and_parks', 'squares', 'fountains', 'sculptures', 'beaches',
    'white_sand_beaches', 'golden_sand_beaches', 'nude_beaches', 'waterfalls',
    'mountain_peaks', 'volcanoes', 'caves', 'canyons', 'rock_formations',
    'nature_reserves', 'national_parks', 'wildlife_reserves', 'glaciers', 'islands',
    'hot_springs', 'geysers', 'view_points', 'archaeological_museums',
    'open_air_museums', 'open_air_baths', 'amphitheatres',
    'fortifications', 'castles', 'hillforts', 'war_memorials', 'monuments',
    'milestones', 'campsites', 'sport', 'diving', 'surfing', 'kitesurfing',
    'climbing', 'skiing', 'winter_sports',
}

INDOOR_KINDS = {
    'museums', 'art_galleries', 'aquariums', 'zoos', 'planetariums',
    'science_museums', 'history_museums', 'military_museums',
    'theatres_and_entertainments', 'concert_halls', 'cinemas', 'opera_houses',
    'music_venues', 'restaurants', 'cafes', 'fast_food', 'bars', 'pubs',
    'food_courts', 'bakeries', 'nightclubs', 'casino', 'hookah',
    'baths_and_saunas', 'thermal_baths', 'saunas', 'malls', 'supermarkets',
    'shops', 'amusement_parks', 'water_parks', 'churches', 'cathedrals',
    'monasteries', 'mosques', 'synagogues', 'buddhist_temples', 'hindu_temples',
    'palaces', 'manor_houses', 'skyscrapers', 'towers', 'observation_towers',
    'other_hotels', 'hostels', 'motels', 'resorts', 'guest_houses', 'apartments',
}

# Priority order for picking a display label from kinds string.
# First match wins. Ordered from most specific/meaningful to most generic.
KINDS_DISPLAY_PRIORITY = [
    'restaurants', 'cafes', 'fast_food', 'bars', 'pubs', 'bakeries', 'food_courts',
    'biergartens', 'marketplaces',
    'museums', 'art_galleries', 'history_museums', 'science_museums', 'military_museums',
    'archaeological_museums', 'open_air_museums',
    'aquariums', 'zoos', 'planetariums',
    'theatres_and_entertainments', 'concert_halls', 'opera_houses', 'cinemas', 'music_venues',
    'nightclubs', 'casino', 'hookah',
    'beaches', 'white_sand_beaches', 'golden_sand_beaches',
    'churches', 'cathedrals', 'monasteries', 'mosques', 'synagogues',
    'buddhist_temples', 'hindu_temples',
    'castles', 'fortifications', 'palaces', 'manor_houses',
    'monuments', 'war_memorials',
    'gardens_and_parks', 'squares', 'fountains', 'sculptures',
    'view_points', 'observation_towers', 'towers', 'lighthouses',
    'thermal_baths', 'saunas', 'baths_and_saunas',
    'nature_reserves', 'national_parks', 'wildlife_reserves',
    'waterfalls', 'caves', 'mountain_peaks', 'glaciers', 'islands',
    'sport', 'climbing', 'diving', 'surfing',
    'amusement_parks', 'water_parks',
    'skyscrapers', 'architecture', 'historic_architecture',
    'interesting_places', 'tourist_object', 'view_points',
]

# Human-readable labels for kinds
KINDS_LABELS = {
    'restaurants': 'Restaurant',
    'cafes': 'Café',
    'fast_food': 'Fast Food',
    'bars': 'Bar',
    'pubs': 'Pub',
    'bakeries': 'Bakery',
    'food_courts': 'Food Court',
    'biergartens': 'Beer Garden',
    'marketplaces': 'Market',
    'museums': 'Museum',
    'art_galleries': 'Art Gallery',
    'history_museums': 'History Museum',
    'science_museums': 'Science Museum',
    'military_museums': 'Military Museum',
    'archaeological_museums': 'Archaeological Museum',
    'open_air_museums': 'Open Air Museum',
    'aquariums': 'Aquarium',
    'zoos': 'Zoo',
    'planetariums': 'Planetarium',
    'theatres_and_entertainments': 'Theatre',
    'concert_halls': 'Concert Hall',
    'opera_houses': 'Opera House',
    'cinemas': 'Cinema',
    'music_venues': 'Music Venue',
    'nightclubs': 'Nightclub',
    'casino': 'Casino',
    'beaches': 'Beach',
    'white_sand_beaches': 'Beach',
    'golden_sand_beaches': 'Beach',
    'churches': 'Church',
    'cathedrals': 'Cathedral',
    'monasteries': 'Monastery',
    'mosques': 'Mosque',
    'synagogues': 'Synagogue',
    'buddhist_temples': 'Buddhist Temple',
    'hindu_temples': 'Hindu Temple',
    'castles': 'Castle',
    'fortifications': 'Fortress',
    'palaces': 'Palace',
    'manor_houses': 'Manor House',
    'monuments': 'Monument',
    'war_memorials': 'War Memorial',
    'gardens_and_parks': 'Park',
    'squares': 'Square',
    'fountains': 'Fountain',
    'sculptures': 'Sculpture',
    'view_points': 'Viewpoint',
    'observation_towers': 'Observation Tower',
    'towers': 'Tower',
    'lighthouses': 'Lighthouse',
    'thermal_baths': 'Thermal Baths',
    'saunas': 'Sauna',
    'baths_and_saunas': 'Spa',
    'nature_reserves': 'Nature Reserve',
    'national_parks': 'National Park',
    'wildlife_reserves': 'Wildlife Reserve',
    'waterfalls': 'Waterfall',
    'caves': 'Cave',
    'mountain_peaks': 'Mountain',
    'glaciers': 'Glacier',
    'islands': 'Island',
    'sport': 'Sport',
    'climbing': 'Climbing',
    'diving': 'Diving',
    'surfing': 'Surfing',
    'amusement_parks': 'Amusement Park',
    'water_parks': 'Water Park',
    'skyscrapers': 'Skyscraper',
    'architecture': 'Architecture',
    'historic_architecture': 'Historic Site',
    'interesting_places': 'Attraction',
    'tourist_object': 'Attraction',
}


def get_place_labels(kinds_str: str, max_labels: int = 3) -> list[str]:
    """
    Returns up to max_labels human-readable labels for a place,
    ordered by KINDS_DISPLAY_PRIORITY (most meaningful first).
    Used in list view to show relevant tags instead of raw kinds[0].
    """
    if not kinds_str:
        return ['Place']
    kinds_set = set(kinds_str.split(','))
    labels = []
    seen = set()
    for kind in KINDS_DISPLAY_PRIORITY:
        if kind in kinds_set:
            label = KINDS_LABELS.get(kind, kind.replace('_', ' ').title())
            if label not in seen:
                labels.append(label)
                seen.add(label)
            if len(labels) >= max_labels:
                break
    return labels or ['Place']


def get_city_coordinates(city_name: str) -> tuple[float, float] | None:
    cache_key = f'city_coords:{city_name.lower()}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f'{OTM_BASE}/geoname',
                params={'name': city_name, 'apikey': OTM_API_KEY}
            )
            resp.raise_for_status()
            geo = resp.json()
    except Exception as e:
        logger.error(f'Opentripmap geoname error: {e}')
        return None

    lat = geo.get('lat')
    lon = geo.get('lon')
    if not lat or not lon:
        return None

    result = (lat, lon)
    cache.set(cache_key, result, 60 * 60 * 24 * 30)
    return result


def get_city_bbox(lat: float, lon: float, radius_km: float = 15.0) -> dict:
    import math
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * abs(math.cos(math.radians(lat))) or 1)
    return {
        'lon_min': lon - delta_lon,
        'lon_max': lon + delta_lon,
        'lat_min': lat - delta_lat,
        'lat_max': lat + delta_lat,
    }


def get_places_by_bbox(lat: float, lon: float, kinds: str, rate: int = 2, radius_km: float = 10, limit: int = 100) -> list[dict]:
    bbox = get_city_bbox(lat, lon, radius_km)
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f'{OTM_BASE}/bbox',
                params={
                    'lon_min': bbox['lon_min'],
                    'lon_max': bbox['lon_max'],
                    'lat_min': bbox['lat_min'],
                    'lat_max': bbox['lat_max'],
                    'kinds': kinds,
                    'rate': rate,
                    'limit': limit,
                    'format': 'geojson',
                    'apikey': OTM_API_KEY,
                }
            )
            resp.raise_for_status()
            features = resp.json().get('features', [])
    except Exception as e:
        logger.error(f'Opentripmap bbox error: {e}')
        return []

    results = []
    for f in features:
        props = f.get('properties', {})
        name = props.get('name', '').strip()
        if not name:
            continue
        coords = f.get('geometry', {}).get('coordinates', [])
        results.append({
            'xid': props.get('xid'),
            'name': name,
            'kinds': props.get('kinds', ''),
            'rate': props.get('rate', 0),
            'lon': coords[0] if coords else None,
            'lat': coords[1] if coords else None,
        })

    return results


def _fetch_xid_detail(xid: str) -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f'{OTM_BASE}/xid/{xid}',
                params={'apikey': OTM_API_KEY}
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f'Opentripmap xid error {xid}: {e}')
        return None


def _fetch_xid_details_parallel(xids: list[str], max_workers: int = 5) -> dict[str, dict]:
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_xid = {executor.submit(_fetch_xid_detail, xid): xid for xid in xids}
        for future in as_completed(future_to_xid):
            xid = future_to_xid[future]
            data = future.result()
            if data:
                results[xid] = data
    return results


def parse_and_translate(
    query: str,
    category: str = '',
    rate: str = '',
    price: str = '',
    location_type: str = '',
    vibe: str = '',
) -> tuple[str, dict]:
    """
    Single Gemini call that:
    1. Translates query to English if not already ASCII.
    2. Determines search params: kinds, rate, radius_km.

    Returns (translated_query, {kinds, rate, radius_km}).
    Falls back to deterministic values on error.
    """
    candidate_kinds = CATEGORY_TO_KINDS.get(category, _AVAILABLE_KINDS)

    needs_translation = bool(query and not query.isascii())

    user_input_parts = filter(None, [
        query,
        f'category:{category}' if category else '',
        f'price:{price}' if price else '',
        f'location:{location_type}' if location_type else '',
        f'vibe:{vibe}' if vibe else '',
        f'minimum_rating:{rate}' if rate else '',
    ])
    user_input = ' '.join(user_input_parts)

    translation_instruction = (
        'Also translate the query field to English before analyzing it. '
        'Include the translated query in your response as "translated_query".\n'
        if needs_translation else
        'The query is already in English. Set "translated_query" to the same value as the input query.\n'
    )

    prompt = f"""You are a travel API assistant. A user is searching for places to visit in a city.

User input: "{user_input}"

Available place kinds: {candidate_kinds}

{translation_instruction}
Analyze the user input carefully. It may contain hints about:
- what type of places they want -> pick appropriate kinds
- price level (cheap/budget -> fast_food,cafes,marketplaces,gardens_and_parks; expensive/luxury -> restaurants,palaces,opera_houses,resorts)
- location preference (outdoor -> parks,beaches,squares,monuments; indoor -> museums,restaurants,theatres,malls)
- vibe (active/sporty -> sport,climbing,surfing kinds; relaxed/calm -> gardens_and_parks,thermal_baths,cafes)
- rating preference -> set rate accordingly (1=any, 2=notable, 3=must-see only)
- area size -> set radius_km (small/nearby=3, normal=10, large/nature=20)

Return ONLY valid JSON, nothing else:
{{"translated_query": "english version of query", "kinds": "beaches,restaurants", "rate": 2, "radius_km": 10}}"""

    try:
        response_text = _gemini_generate(
            prompt=prompt,
            response_mime_type="application/json",
            temperature=0.1
        )
        parsed = json.loads(response_text)
        translated_query = parsed.get('translated_query', query) or query

        valid = set(_AVAILABLE_KINDS.split(','))
        kinds = ','.join(k.strip() for k in parsed.get('kinds', '').split(',') if k.strip() in valid)

        if location_type == 'outdoor' and kinds:
            kinds = ','.join(k for k in kinds.split(',') if k in OUTDOOR_KINDS) or kinds
        elif location_type == 'indoor' and kinds:
            kinds = ','.join(k for k in kinds.split(',') if k in INDOOR_KINDS) or kinds

        params = {
            'kinds': kinds or candidate_kinds,
            'rate': max(1, min(3, int(parsed.get('rate', 2)))),
            'radius_km': max(2, min(25, float(parsed.get('radius_km', 10)))),
        }
        return translated_query, params

    except Exception as e:
        logger.error(f'Gemini parse_and_translate error: {e}')
        fallback_params = {
            'kinds': candidate_kinds,
            'rate': int(rate) if rate and rate.isdigit() else 2,
            'radius_km': 10,
        }
        return query, fallback_params


def llm_rank_and_translate(places: list[dict], user_input: str) -> list[dict]:
    """
    Single Gemini call: rank all candidates by relevance and translate names to English.
    Removed step1 (needs_detail check) to save one Gemini round-trip.
    limit is now 100 to compensate for not doing per-place detail fetching.
    """
    if not places:
        return []

    indexed = [{'i': i, 'name': p['name'], 'kinds': p['kinds'], 'rate': p['rate']} for i, p in enumerate(places)]

    prompt = f"""You are a travel assistant. User wants: "{user_input}"

Here are the candidate places:
{json.dumps(indexed, ensure_ascii=False)}

Your job:
1. Remove places that are clearly irrelevant to the user request
2. Rank the remaining candidates by relevance (most relevant first)
3. Translate each name to English (if already English, keep as is)
4. Return ONLY valid JSON:
{{"ranked": [
  {{"i": 3, "name": "Eiffel Tower"}},
  {{"i": 0, "name": "Louvre Museum"}}
]}}

Include every candidate that is relevant, ordered best to worst match."""

    try:
        resp_text = _gemini_generate(
            prompt=prompt,
            response_mime_type="application/json",
            temperature=0.1
        )
        parsed = json.loads(resp_text)
        ranked = parsed.get('ranked', [])

        result = []
        for entry in ranked:
            i = entry.get('i')
            if i is None or not (0 <= i < len(places)):
                continue
            place = dict(places[i])
            place['name'] = entry.get('name', place['name'])
            place['labels'] = get_place_labels(place.get('kinds', ''))
            result.append(place)

        return result

    except Exception as e:
        logger.error(f'Gemini rank error: {e}')
        result = []
        for p in places:
            place = dict(p)
            place['labels'] = get_place_labels(place.get('kinds', ''))
            result.append(place)
        return result


def search_places(lat: float, lon: float, query: str, category: str = '', rate: str = '',
                  price: str = '', location_type: str = '', vibe: str = '') -> list[dict]:
    """
    Main search. Returns full ranked list (up to 100).
    Caller is responsible for pagination and caching.
    """
    translated_query, params = parse_and_translate(query, category, rate, price, location_type, vibe)

    user_input = ' '.join(filter(None, [
        translated_query, category, price, location_type, vibe,
        f'rating:{rate}' if rate else ''
    ]))

    raw_places = get_places_by_bbox(lat, lon, params['kinds'], params['rate'], params['radius_km'], limit=100)

    if not raw_places:
        return []

    return llm_rank_and_translate(raw_places, user_input)


def get_place_detail(xid: str) -> dict | None:
    return _fetch_xid_detail(xid)


def _get_wikimedia_image(name: str) -> str:
    """
    Tries to fetch a thumbnail from Wikimedia API by place name.
    Returns image URL string or empty string if not found.
    """
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                'https://en.wikipedia.org/w/api.php',
                params={
                    'action': 'query',
                    'titles': name,
                    'prop': 'pageimages',
                    'pithumbsize': 800,
                    'format': 'json',
                    'redirects': 1,
                }
            )
            resp.raise_for_status()
            pages = resp.json().get('query', {}).get('pages', {})
            for page in pages.values():
                thumb = page.get('thumbnail', {}).get('source', '')
                if thumb:
                    return thumb
    except Exception as e:
        logger.warning(f'Wikimedia image fetch failed for "{name}": {e}')
    return ''


def build_place_detail_response(xid: str, data: dict) -> dict:
    name = data.get('name', '')
    kinds = data.get('kinds', '')
    raw_description = (
        data.get('wikipedia_extracts', {}).get('text', '') or
        data.get('info', {}).get('descr', '')
    )

    # Try OTM image first, fall back to Wikimedia
    image = (
        data.get('preview', {}).get('source', '') or
        data.get('image', '')
    )
    if not image and name:
        image = _get_wikimedia_image(name)

    address = data.get('address', {})
    description = clean_description(name, kinds, raw_description)

    return {
        'xid': xid,
        'name': name,
        'description': description,
        'kinds': kinds,
        'labels': get_place_labels(kinds),
        'image': image,
        'address': {
            'city': address.get('city', ''),
            'suburb': address.get('suburb', ''),
            'pedestrian': address.get('pedestrian', '') or address.get('road', ''),
        },
        # otm_url removed — URLs from OTM API are unreliable
    }


def clean_description(name: str, kinds: str, raw: str) -> str:
    if raw:
        prompt = f"""You are a travel guide assistant. The following is a description of a place called "{name}".
Translate it to English if needed and rewrite it as a clear, engaging 2-3 sentence description for travelers.
Return ONLY the description text. No labels, no extra text.

Original text: {raw[:1000]}"""
    else:
        prompt = f"""You are a travel guide assistant. Write a short 2-sentence description for travelers about this place:
Name: {name}
Type: {kinds}
Return ONLY the description. No labels, no extra text."""

    try:
        response_text = _gemini_generate(
            prompt=prompt,
            temperature=0.4
        )
        return response_text.strip()
    except Exception as e:
        logger.error(f'Gemini error in clean_description: {e}')
        return raw or ''