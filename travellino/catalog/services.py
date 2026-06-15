import json
import logging
import os

import httpx
from django.core.cache import cache

from google import genai

logger = logging.getLogger(__name__)

FS_API_KEY = os.getenv('FOURSQUARE_API_KEY')
FS_BASE = 'https://places-api.foursquare.com/places'
FS_HEADERS = {
    'Authorization': f'Bearer {FS_API_KEY}',
    'X-Places-Api-Version': '2025-06-17',
}

_genai_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

GEMINI_MODELS = [
    'gemini-3.5-flash',
    'gemini-3.1-flash-lite',
    'gemini-3-flash-preview',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-flash-lite',
    'gemini-flash-latest',
]


def _gemini_generate(prompt: str, response_mime_type: str = None, temperature: float = 0.1) -> str:
    config_kwargs = {'temperature': temperature}
    if response_mime_type:
        config_kwargs['response_mime_type'] = response_mime_type

    last_exc = None
    for model_name in GEMINI_MODELS:
        try:
            response = _genai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(**config_kwargs),
            )
            return response.text
        except Exception as e:
            logger.debug(f'Error on {model_name}: {e}. Switching to next...')
            last_exc = e
            continue

    logger.error(f'All Gemini models failed. Last error: {last_exc}')
    raise last_exc


# Foursquare sort options
FS_SORT_OPTIONS = ('RELEVANCE', 'RATING', 'DISTANCE', 'POPULARITY')


# ---------------------------------------------------------------------------
# Step 1 — Gemini translates free-form user input into precise FS params
# ---------------------------------------------------------------------------

def parse_to_foursquare_params(
    query: str,
    category: str = '',
    price: str = '',
    location_type: str = '',
    vibe: str = '',
    rate: str = '',
) -> dict:
    """
    Single Gemini call.
    Input  — raw user query (any language, any style) + UI filters.
    Output — dict of Foursquare /places/search params, filled as precisely
             as possible. Never stuffs everything into `query`.
    Falls back to sensible defaults on error.
    """
    prompt = f"""You are a travel search assistant that converts user requests into Foursquare Places API search parameters.

User request (may be in any language, any style — poem, slang, anything):
"{query}"

UI filters selected by the user (treat as hard constraints):
- category: {category or 'not specified'}
- price level: {price or 'not specified'}  (1=cheapest … 4=most expensive)
- location type: {location_type or 'not specified'}  (indoor / outdoor / any)
- vibe: {vibe or 'not specified'}
- minimum rating: {rate or 'not specified'}

Your job:
1. Translate the request to English if needed.
2. Understand the intent — what kind of place, atmosphere, activity.
3. Fill the Foursquare search fields INTELLIGENTLY:
   - `query`      → 1-4 word English keyword for the place type ("rooftop bar", "ramen", "art museum")
                    incorporate category/vibe into this if it sharpens the search
   - `min_price`  → 1-4 only if price is clearly implied or set by filter; otherwise null
   - `max_price`  → 1-4 only if price is clearly implied or set by filter; otherwise null
   - `open_now`   → true only if user explicitly wants places open right now
   - `sort`       → RELEVANCE (default) | RATING (user wants best/top) | DISTANCE (user wants nearby) | POPULARITY
   - `limit`      → always 50

Return ONLY valid JSON, no markdown:
{{
  "query": "short english keyword",
  "min_price": null,
  "max_price": null,
  "open_now": false,
  "sort": "RELEVANCE",
  "limit": 50,
  "translated_query": "full english translation of user request"
}}

Rules:
- null means omit this param entirely
- sort must be exactly one of: RELEVANCE RATING DISTANCE POPULARITY
"""

    try:
        text = _gemini_generate(prompt, response_mime_type='application/json', temperature=0.1)
        parsed = json.loads(text)

        parsed['limit'] = 50

        if parsed.get('sort') not in FS_SORT_OPTIONS:
            parsed['sort'] = 'RELEVANCE'

        return parsed

    except Exception as e:
        logger.error(f'Gemini parse_to_foursquare_params error: {e}')
        return {
            'query': None,
            'min_price': None,
            'max_price': None,
            'open_now': False,
            'sort': 'RELEVANCE',
            'limit': 50,
            'translated_query': query,
        }


# ---------------------------------------------------------------------------
# Step 2 — call Foursquare /places/search
# ---------------------------------------------------------------------------

def fetch_foursquare_places(near: str, fs_params: dict) -> list[dict]:
    """
    Calls Foursquare Places Search API.
    Returns list of raw place dicts (up to 50).
    Each dict has `xid` field — the Foursquare place ID used by the frontend.
    After building the list, caches each place individually by xid
    so get_place_detail can serve details without extra API calls.
    """
    params = {
        'near': near,
        'limit': fs_params.get('limit', 50),
        'sort': fs_params.get('sort', 'RELEVANCE'),
    }

    if fs_params.get('query'):
        params['query'] = fs_params['query']
    if fs_params.get('min_price'):
        params['min_price'] = fs_params['min_price']
    if fs_params.get('max_price'):
        params['max_price'] = fs_params['max_price']
    if fs_params.get('open_now'):
        params['open_now'] = 'true'

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f'{FS_BASE}/search', headers=FS_HEADERS, params=params)
            resp.raise_for_status()
            results = resp.json().get('results', [])
    except Exception as e:
        logger.error(f'Foursquare search error: {e}')
        return []

    places = []
    for r in results:
        name = (r.get('name') or '').strip()
        if not name:
            continue

        fsq_id = r.get('fsq_place_id')
        location = r.get('location', {})
        categories = r.get('categories', [])
        photos = r.get('photos', [])

        place = {
            'xid': fsq_id,
            'name': name,
            'categories': [c.get('name', '') for c in categories],
            'category_ids': [str(c.get('fsq_category_id', '')) for c in categories],
            'lat': r.get('latitude'),
            'lon': r.get('longitude'),
            'address': location.get('formatted_address', ''),
            'city': location.get('locality', ''),
            'country': location.get('country', ''),
            'rating': r.get('rating'),
            'price': r.get('price'),
            'distance': r.get('distance'),
            'photos': photos,
            'website': r.get('website', ''),
            'phone': r.get('tel', ''),
        }
        places.append(place)

        # Cache each place individually so get_place_detail never needs to call Foursquare
        if fsq_id:
            cache.set(f'place_raw:{fsq_id}', place, 60 * 60 * 24)  # 24h

    return places


# ---------------------------------------------------------------------------
# Step 3 — Gemini ranks, filters and labels the raw list (single call)
# ---------------------------------------------------------------------------

def llm_rank_and_filter(places: list[dict], translated_query: str) -> list[dict]:
    """
    Single Gemini call.
    Receives up to 50 raw Foursquare places.
    Returns the full ranked+filtered list — caller paginates.
    Each returned item gets a `labels` field (human-readable category tags).
    """
    if not places:
        return []

    indexed = [
        {
            'i': i,
            'name': p['name'],
            'categories': p['categories'][:3],
            'rating': p['rating'],
            'distance': p['distance'],
        }
        for i, p in enumerate(places)
    ]

    prompt = f"""You are a travel assistant ranking search results for a user.

User wants: "{translated_query}"

Candidate places (from Foursquare):
{json.dumps(indexed, ensure_ascii=False)}

Your job:
1. Remove places clearly irrelevant to the user request.
2. Rank the remaining by relevance (best match first).
3. Return ONLY valid JSON:
{{"ranked": [{{"i": 3}}, {{"i": 0}}, {{"i": 7}}]}}

Include all relevant candidates ordered best to worst. Omit only clearly wrong results."""

    try:
        resp_text = _gemini_generate(prompt, response_mime_type='application/json', temperature=0.1)
        parsed = json.loads(resp_text)
        ranked_indices = parsed.get('ranked', [])

        result = []
        for entry in ranked_indices:
            i = entry.get('i')
            if i is None or not (0 <= i < len(places)):
                continue
            place = dict(places[i])
            place['labels'] = place['categories'][:3] or ['Place']
            result.append(place)

        return result

    except Exception as e:
        logger.error(f'Gemini rank error: {e}')
        for p in places:
            p['labels'] = p['categories'][:3] or ['Place']
        return places


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def search_places(
    near: str,
    query: str,
    category: str = '',
    rate: str = '',
    price: str = '',
    location_type: str = '',
    vibe: str = '',
) -> list[dict]:
    """
    Main search. Returns full ranked list (up to 50).
    Caller handles pagination (slice [0:10], [10:20], …) and caching.

    Flow:
        user query + filters
            → Gemini → precise Foursquare params
            → Foursquare /places/search → up to 50 raw results
            → Gemini → ranked + filtered full list
            → return all; frontend paginates by 10
    """
    fs_params = parse_to_foursquare_params(query, category, price, location_type, vibe, rate)
    translated_query = fs_params.pop('translated_query', query)

    raw_places = fetch_foursquare_places(near, fs_params)
    if not raw_places:
        return []

    return llm_rank_and_filter(raw_places, translated_query)


# ---------------------------------------------------------------------------
# Place detail — no Foursquare requests, only cache + Gemini
# ---------------------------------------------------------------------------

def get_place_detail(xid: str) -> dict | None:
    """
    Returns place detail without calling Foursquare.

    Flow:
        1. Check if full detail is already cached (from a previous detail request)
        2. If not — load raw place data cached during search
        3. Generate description via Gemini
        4. Cache the result for 24h and return
    """
    # Full detail already built and cached
    detail_cache_key = f'place_detail:{xid}'
    cached = cache.get(detail_cache_key)
    if cached:
        return cached

    # Raw place data cached during search
    raw = cache.get(f'place_raw:{xid}')
    if not raw:
        logger.warning(f'No cached data for xid={xid}. User may have jumped directly to detail without searching first.')
        return None

    description = generate_description(raw['name'], raw['categories'])

    result = {
        'xid': xid,
        'name': raw['name'],
        'description': description,
        'labels': raw['categories'][:3] or ['Place'],
        'image': '',
        'rating': raw.get('rating'),
        'price': raw.get('price'),
        'website': raw.get('website', ''),
        'phone': raw.get('phone', ''),
        'hours': {
            'open_now': None,
            'display': [],
        },
        'address': {
            'formatted': raw.get('address', ''),
            'city': raw.get('city', ''),
            'suburb': '',
            'street': '',
        },
        'lat': raw.get('lat'),
        'lon': raw.get('lon'),
    }

    cache.set(detail_cache_key, result, 60 * 60 * 24)  # 24h
    return result


def generate_description(name: str, categories: list[str]) -> str:
    """
    Generates a 2-3 sentence traveler-focused description via Gemini.
    No external API calls — only Gemini.
    """
    kind_str = ', '.join(categories[:3]) if categories else 'place'
    prompt = f"""You are a travel guide assistant.
Write a short 2-3 sentence description for travelers about this place.
Name: {name}
Type: {kind_str}
Return ONLY the description text. No labels, no headers."""

    try:
        return _gemini_generate(prompt, temperature=0.4).strip()
    except Exception as e:
        logger.error(f'Gemini generate_description error: {e}')
        return ''