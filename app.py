from flask import Flask, request, jsonify, render_template
import re
import requests
import asyncio
import aiohttp
import redis
import json
import os

app = Flask(__name__)

# Redis config
redis_host = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

POKE_API_BASE_URL = "https://pokeapi.co/api/v2/pokemon/"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_pokemon():
    try:
        regex_pattern = request.form.get('regex', '')

        # Validate regex
        try:
            re.compile(regex_pattern)
        except re.error:
            return jsonify({"error": "Invalid regex pattern"}), 400

        # Load Pokemon list from Redis or API
        cached_list = r.get("pokemon_list")
        if cached_list:
            pokemon_list = json.loads(cached_list)
        else:
            response = requests.get(f"{POKE_API_BASE_URL}?limit=10000")
            if response.status_code != 200:
                return jsonify({"error": "Failed to fetch Pokémon data"}), 500
            pokemon_list = response.json().get('results', [])
            r.setex("pokemon_list", 86400, json.dumps(pokemon_list))

        matching_pokemon = []

        for pokemon in pokemon_list:
            if re.search(regex_pattern, pokemon['name'], re.IGNORECASE):
                cache_key = f"pokemon_detail:{pokemon['name']}"
                cached_details = r.get(cache_key)
                if cached_details:
                    details = json.loads(cached_details)
                else:
                    details_response = requests.get(pokemon['url'])
                    if details_response.status_code != 200:
                        continue
                    details = details_response.json()
                    r.setex(cache_key, 86400, json.dumps(details))

                # Fetch encounter locations
                locations = []
                encounters_response = requests.get(f"{POKE_API_BASE_URL}{details['id']}/encounters")
                if encounters_response.status_code == 200:
                    encounters = encounters_response.json()
                    for encounter in encounters:
                        location_name = encounter['location_area']['name'].replace('-', ' ').title()
                        for version_detail in encounter['version_details']:
                            version_name = version_detail['version']['name'].replace('-', ' ').title()
                            locations.append(f"{location_name} ({version_name})")

                matching_pokemon.append({
                    'name': details['name'],
                    'id': details['id'],
                    'height': details['height'],
                    'weight': details['weight'],
                    'base_experience': details.get('base_experience'),
                    'types': [t['type']['name'] for t in details.get('types', [])],
                    'abilities': [a['ability']['name'] + (' (Hidden)' if a['is_hidden'] else '') for a in details.get('abilities', [])],
                    'stats': {s['stat']['name']: s['base_stat'] for s in details.get('stats', [])},
                    'image': details['sprites']['front_default'] or '/static/placeholder.png',
                    'locations': locations,
                })

        return jsonify({"matches": matching_pokemon})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


async def fetch_pokemon_details(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return await response.json()
        return {}


@app.route('/encyclopedia')
def encyclopedia():
    # Because Flask does not fully support async routes well,
    # use sync code here for simplicity or use Quart/async framework.
    try:
        cached_list = r.get("pokemon_list")
        if cached_list:
            pokemon_list = json.loads(cached_list)
        else:
            response = requests.get(f"{POKE_API_BASE_URL}?limit=1008")
            if response.status_code != 200:
                return f"Failed to load Pokémon data, status code: {response.status_code}", 500
            pokemon_list = response.json().get('results', [])
            r.setex("pokemon_list", 86400, json.dumps(pokemon_list))

        pokemon_details = []
        for pokemon in pokemon_list:
            cache_key = f"pokemon_detail:{pokemon['name']}"
            cached = r.get(cache_key)
            if cached:
                detail = json.loads(cached)
            else:
                detail_resp = requests.get(pokemon['url'])
                if detail_resp.status_code != 200:
                    continue
                detail = detail_resp.json()
                r.setex(cache_key, 86400, json.dumps(detail))

            image_url = detail['sprites']['front_default'] or '/static/placeholder.png'
            pokemon_details.append({
                'name': detail['name'],
                'id': detail['id'],
                'image': image_url,
            })

        return render_template('encyclopedia.html', pokemon_list=pokemon_details)

    except Exception as e:
        return f"An error occurred: {e}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
