from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import RawPokeData, Evolution
import requests


def poke_view(request, name):
    """
    Requests the poke_view template and populates it with the information of the Pokemon being shown.

    Input: Name of Pokemon

    Output: Render request to poke_view template with information

    Modifies: None
    """
    # Get the Pokemon from the database
    curr_poke = RawPokeData.objects.filter(name__icontains=name.lower())[0]

    # Get basic data
    name = curr_poke.data["name"]
    id = curr_poke.data["id"]

    # Find Type
    type_data = curr_poke.data["types"]
    poke_types = []
    for p_type in type_data:
        poke_types.append(p_type["type"]["name"])
    # Find url for official artwork
    url = curr_poke.data["sprites"]["other"]["official-artwork"]["front_default"]
    # Find EV Yield and Base Stats
    base_stats = {}
    evs = curr_poke.evs
    for stat in curr_poke.data["stats"]:
        base_stats[stat["stat"]["name"]] = stat["base_stat"]
    context = {"name": name.capitalize(), "national_id": id, "type": poke_types, "artwork": url,\
               "base": base_stats, "EV": evs, "fav": curr_poke.fave}

    #Get Evolution data
    try:
        evo_details = {}
        evos = Evolution.objects.get(poke_name__icontains=name)
        for pokemon, details in evos.evo_data.items():
            if bool(details):
                if pokemon not in evo_details:
                    evo_details[pokemon] = {"sprite": RawPokeData.objects.get(name=pokemon).data["sprites"]["front_default"]}
                    evo_details[pokemon]["tier"] = Evolution.objects.get(poke_name__icontains=pokemon).evo_tier
                for next_evo, next_details in details.items():
                    if next_evo not in evo_details:
                        evo_details[next_evo] = {"sprite": RawPokeData.objects.get(name=next_evo).data["sprites"]["front_default"]}
                        evo_details[next_evo]["tier"] = Evolution.objects.get(poke_name__icontains=next_evo).evo_tier
                        evo_details[next_evo]["to_evolve"] = next_details
        context["evolutions"] = evo_details
        return render(request, 'pokemon/poke_view.html', context)
    except ObjectDoesNotExist:
        return render(request, 'pokemon/poke_view.html', context)


def to_favorite(request, name):
    """
    Favorites or unfavorites a Pokemon.
    """
    if request.method == "POST":
        poke = RawPokeData.objects.get(name=name.lower())
        if poke.fave:
            poke.fave = False
        else:
            poke.fave = True
        poke.save()
    return HttpResponseRedirect(reverse('pokemon:poke_view', args=(name,)))


def pull_evolutions(request):
    """
    Pulls all evolutions from the PokeAPI website and formats them in a way specific to this database. Adds each
    Evolution to the database and links it to the correct Pokemon involved in the evolution.

    Input: None

    Output: None

    Modifications: Adds Evolution objects to the database
    """
    # Counter to iterate through evolution IDs in url
    if request.method == 'POST':
        try:
            evo_id = 1
            json_evo = requests.get(f"https://pokeapi.co/api/v2/evolution-chain/{evo_id}/")
            # Evo_id set to 500 because the API will skip some numbers and doesn't go further than 500
            while evo_id < 500:
                if json_evo.status_code == 404:
                    evo_id += 1
                    json_evo = requests.get(f"https://pokeapi.co/api/v2/evolution-chain/{evo_id}/")
                else:
                    json_evo_data = json_evo.json()
                    next_evo = json_evo_data["chain"]["evolves_to"]
                    # The Pokemon can evolve
                    if next_evo:
                        base_form = json_evo_data["chain"]["species"]["name"]
                        # Prevent double-adding
                        if not bool(Evolution.objects.filter(poke_name=base_form)):
                            # Add base form to main details to append secondary form data as value
                            evolution_details = {base_form: {}}
                            evolution_tiers = {base_form: 1}
                            # Check if there are multiple second forms
                            for second_form in next_evo:
                                second_form_details = {}
                                try:
                                    for condition, need in second_form["evolution_details"][0].items():
                                        if condition == "trigger":
                                            second_form_details["trigger"] = need["name"]
                                        elif need is not None and need is not False and need != '':
                                            if isinstance(need, dict):
                                                second_form_details[condition] = need["name"]
                                            else:
                                                second_form_details[condition] = need
                                # Some Pokemon don't have evolution details, throws off list indexing
                                except IndexError:
                                    pass
                                # Add second form details to base form key in evolution_details
                                evolution_details[base_form][second_form["species"]["name"]] = second_form_details
                                evolution_tiers[second_form["species"]["name"]] = 2
                                # There is a third evolution
                                if bool(second_form["evolves_to"]):
                                    evolution_details[second_form["species"]["name"]] = {}
                                    for final_form in second_form["evolves_to"]:
                                        final_form_details = {}
                                        for condition, need in final_form["evolution_details"][0].items():
                                            if condition == "trigger":
                                                final_form_details["trigger"] = need["name"]
                                            elif need is not None and need is not False and need != '':
                                                if isinstance(need, dict):
                                                    final_form_details[condition] = need["name"]
                                                else:
                                                    final_form_details[condition] = need
                                        evolution_details[second_form["species"]["name"]][final_form["species"]["name"]] = final_form_details
                                        evolution_details[final_form["species"]["name"]] = {}
                                        evolution_tiers[final_form["species"]["name"]] = 3
                                else:
                                    evolution_details[second_form["species"]["name"]] = {}
                            for pokemon in evolution_details.keys():
                                raw_poke_data = RawPokeData.objects.filter(name__icontains=pokemon)[0]
                                new_evolution = Evolution(poke_name=pokemon, poke_data=raw_poke_data, evo_data=evolution_details,\
                                                          evo_tier=evolution_tiers[pokemon])
                                new_evolution.save()
                    evo_id += 1
                    json_evo = requests.get(f"https://pokeapi.co/api/v2/evolution-chain/{evo_id}/")
            return render(request, "pages/home.html", {"message_evo": "Pulled Evolutions successfully!"})
        except:
            return render(request, "pages/home.html", {"message_evo": "Pulling Evolutions failed!"})
