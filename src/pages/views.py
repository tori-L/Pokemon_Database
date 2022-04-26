from django.shortcuts import render
import requests
from pokemon import models, views
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import OperationalError
from requests.exceptions import JSONDecodeError


def home_view(request):
    """Requests home template."""
    return render(request, "pages/home.html", {})


def type_chart_view(request):
    """Requests type chart template."""
    return render(request, "pages/typechart.html", {})


def nature_chart_view(request):
    """Requests nature chart template."""
    return render(request, "pages/naturechart.html", {})


def search(request):
    """
    Search function that pulls POST request and filters through database for matching Pokemon based on
    the selector ('move', 'pokemon', 'type', 'effort value') and search term.

    Input: None

    Output: A render request to the search template with the search term, selector, and matching search queries
    as input.

    Modifications: None

    """
    search_term = request.POST["search_term"]
    if search_term == "":
        return render(request, "pages/home.html", {"error": "You must include a search term!"})
    selector = request.POST["selector"]
    search_list = {}
    # If the user selected Moves as their search identifier
    if selector == "moves":
        search_move = search_term.replace(' ', '-').lower()
        response = requests.get(f"https://pokeapi.co/api/v2/move/{search_move}/")
        if response.status_code == 404:
            return render(request, "pages/home.html", {"error": "Not a valid Move!"})
        else:
            move_data = response.json()
            poke_by_move = move_data["learned_by_pokemon"]
            for pokemon in poke_by_move:
                if check_or_add(pokemon["name"]) is None:
                    poke_sprite_url = models.RawPokeData.objects.get(name__icontains=pokemon["name"].lower()).data["sprites"]\
                    ["front_default"]
                    search_list[pokemon["name"].capitalize()] = poke_sprite_url
            return render(request, "pages/search.html", {"search_term": search_term.upper, "search_list": search_list,\
                                                   "selector": selector})
    # If the user selected Type as their identifier
    if selector == "type":
        mono_list = {}
        dual_list = {}
        search_type = search_term.lower()
        response = requests.get(f"https://pokeapi.co/api/v2/type/{search_type}/")
        if response.status_code == 404:
            return render(request, "pages/home.html", {"error": "Not a valid Type!"})
        else:
            type_data = response.json()
            poke_by_type = type_data["pokemon"]
            for pokemon in poke_by_type:
                if check_or_add(pokemon["pokemon"]["name"]) is None:
                    poke_data = models.RawPokeData.objects.get(name__icontains=pokemon["pokemon"]["name"].lower()).data
                    poke_sprite_url = poke_data["sprites"]["front_default"]
                    if len(poke_data["types"]) == 1:
                        mono_list[poke_data["name"].capitalize()] = poke_sprite_url
                    else:
                        dual_list[poke_data["name"].capitalize()] = poke_sprite_url
            return render(request, "pages/search.html", {"search_term": search_term.upper, "mono_list": mono_list,\
                                                   "dual_list": dual_list, "selector": selector})
    # User selected Effort Value to be selector
    if selector == "ev":
        ev_dict = {1: {}, 2: {}, 3: {}}
        search_ev = search_term.replace(' ', '-').lower()
        if search_ev in ["attack", "defense", "hp", "speed"]:
            poke_by_ev = models.RawPokeData.objects.filter(evs__icontains=search_ev).exclude(evs__icontains='special')
        elif search_ev in ["special-attack", "special-defense"]:
            poke_by_ev = models.RawPokeData.objects.filter(evs__icontains=search_ev)
        else:
            return render(request, "pages/home.html", {"error": "Please use the full name (i.e. special attack)"})
        for pokemon in poke_by_ev:
            poke_data = pokemon.data
            poke_sprite_url = poke_data["sprites"]["front_default"]
            ev_dict[pokemon.evs[search_ev]][pokemon.name.capitalize()] = poke_sprite_url
        return render(request, "pages/search.html", {"search_term": search_term.upper, "ev_dict": ev_dict, \
                       "selector": selector})
    # If the user wanted to find a specific Pokemon
    if selector == "pokemon":
        result = check_or_add(search_term)
        if result is None:
            return views.poke_view(request, search_term)
        elif bool(result):
            for query in result:
                query_data = query.data
                sprite_url = query_data["sprites"]["front_default"]
                search_list[query.name.capitalize()] = sprite_url
            return render(request, "pages/search.html", {"search_term": search_term.upper, "search_list": search_list,\
                                                         "selector": selector})
        else:
            return render(request, "pages/home.html", {"error": "Not a valid Pokemon!"})


def check_or_add(name):
    """
    Helper function that searches the database for the given Pokemon. If not in the database, tries to add it
    by requesting the Pokemon from PokeAPI.

    Input: Name of a Pokemon

    Returns: None if the Pokemon is in the database or it was successfully added, a list of Pokemon with the search
    query in their name, or an empty list if none of the above actions were successful

    Modifies: the Pokemon database if the Pokemon is not already in the database

    """
    try:
        alt_list = models.RawPokeData.objects.filter(name__icontains=name.lower())
        if len(alt_list) == 1:
            return None
        elif len(alt_list) > 1:
            return alt_list
        else:
            raise ObjectDoesNotExist
    except ObjectDoesNotExist:
        try:
            # GET request to PokeAPI for info on searched Pokemon
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{name.lower()}")
            new_data = response.json()
            new_poke = models.RawPokeData(name=new_data["name"], data=new_data, fave=False, evs="")
            new_poke.setEV()
            # Save raw data to database with pokemon name as an identifier
            new_poke.save()
        except JSONDecodeError:
            return []


def favorite_list(request):
    """
    Filters out the Pokemon in the database that have been favorited and returns them as input to the
    favorite_list template.
    """
    fave_list = models.RawPokeData.objects.filter(fave=True)
    context = {}
    for pokemon in fave_list:
        context[pokemon.name] = pokemon.data["sprites"]["front_default"]
    return render(request, "pages/favorites.html", {"favorite_list": context})


def reset_database(request):
    """
    Resets the database by deleting all Pokemon from it currently and requesting all new data from the API.
    """
    if request.method == "POST":
        try:
            # Check if database is currently empty or has Pokemon objects
            if bool(models.RawPokeData.objects.all()):
                models.RawPokeData.objects.all().delete()
            ID = 1
            # API jumps to ID 10001 after a certain point, ensuring all Pokemon are entered
            to_10000 = True
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{ID}/")
            while response.status_code != 404:
                new_data = response.json()
                new_poke = models.RawPokeData(name=new_data["name"], data=new_data, fave=False, evs="")
                new_poke.setEV()
                new_poke.save()
                ID += 1
                response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{ID}/")
                if response.status_code == 404 and to_10000:
                    ID = 10001
                    response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{ID}/")
                    to_10000 = False
            return render(request, "pages/home.html", {"message_reset": "Database reset successful!"})
        except Exception as err:
            return render(request, "pages/home.html", {"message_reset": f"Database reset failed due to {err}!"})
