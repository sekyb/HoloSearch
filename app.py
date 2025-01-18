from flask import Flask, request, jsonify, render_template
import re
import requests

app = Flask(__name__)

POKE_API_BASE_URL = "https://pokeapi.co/api/v2/pokemon/"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_pokemon():
    try:
        regex_pattern = request.form.get('regex', '')

        # Validate the regex pattern
        try:
            re.compile(regex_pattern)
        except re.error:
            return jsonify({"error": "Invalid regex pattern"}), 400

        # Fetch Pokémon list from the API
        response = requests.get(f"{POKE_API_BASE_URL}?limit=10000")
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch Pokémon data"}), 500

        pokemon_list = response.json().get('results', [])

        # Filter Pokémon names using the regex
        matching_pokemon = []
        for pokemon in pokemon_list:
            if re.search(regex_pattern, pokemon['name'], re.IGNORECASE):
                # Fetch additional details for the Pokémon to get all details
                details_response = requests.get(pokemon['url'])
                if details_response.status_code == 200:
                    details = details_response.json()
                    matching_pokemon.append({
                        'name': pokemon['name'],
                        'id': details['id'],
                        'height': details['height'],
                        'weight': details['weight'],
                        'types': [t['type']['name'] for t in details['types']],
                        'abilities': [a['ability']['name'] for a in details['abilities']],
                        'stats': {s['stat']['name']: s['base_stat'] for s in details['stats']},
                        'image': details['sprites']['front_default'],
                    })

        return jsonify({"matches": matching_pokemon})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
