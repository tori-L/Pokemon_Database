from django.db import models


class RawPokeData(models.Model):
    """Class that holds data on a specific Pokemon and their favorite status."""

    name = models.CharField(max_length=20)
    data = models.JSONField()
    fave = models.BooleanField(False)
    evs = models.JSONField()

    def __str__(self):
        return self.name

    def setEV(self):
        """Determine effort values that are granted by this Pokemon and set as attribute."""

        evs = {}
        for stat in self.data["stats"]:
            if stat["effort"] != 0:
                evs[stat["stat"]["name"]] = stat["effort"]
        self.evs = evs


class Evolution(models.Model):
    """Class that organizes the evolution chain for a branch of Pokemon and relates to the RawPokeData object
    for the specific Pokemon."""

    poke_name = models.CharField(max_length=20)
    poke_data = models.ForeignKey(RawPokeData, on_delete=models.CASCADE)
    evo_data = models.JSONField()
    evo_tier = models.IntegerField(default=0)

    def __str__(self):
        return self.poke_name
