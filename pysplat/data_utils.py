import csv
from io import StringIO
import requests


LAPOSTE_HEXASMAL_CSV_URL = "https://datanova.laposte.fr/explore/dataset/laposte_hexasmal/download/?format=csv&timezone=Europe/Berlin&lang=fr&use_labels_for_header=true&csv_separator=%3B"


def france_cities(output_filepath="./fr-cities.dat"):
    print("Downloading data (this might take some minutes)...")
    csv_blob = requests.get(LAPOSTE_HEXASMAL_CSV_URL).text
    print("Data downloaded")

    with open(output_filepath, "w") as outputfile:
        for r in csv.reader(StringIO(csv_blob), delimiter=";"):
            if "," in r[-1]:
                lat, lon = map(float, r[-1].split(","))
                outputfile.write(f"{r[1]},{lat},{(365-lon)}\n")

    print(f"{output_filepath} written!")
