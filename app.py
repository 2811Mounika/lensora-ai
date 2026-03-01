from flask import Flask, render_template, request, send_file
import requests
import os
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GOOGLE_API_KEY")


def get_place_details(place_id):
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"

    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website",
        "key": API_KEY
    }

    response = requests.get(details_url, params=params)
    result = response.json().get("result", {})

    return {
        "phone": result.get("formatted_phone_number", "Not Available"),
        "website": result.get("website", "Not Available")
    }


def get_photographers(city):
    search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    params = {
        "query": f"wedding photographers in {city}",
        "key": API_KEY
    }

    response = requests.get(search_url, params=params)
    data = response.json()

    photographers = []

    for place in data.get("results", [])[:30]:
        place_id = place.get("place_id")
        details = get_place_details(place_id)

        photo_url = None
        if "photos" in place:
            photo_reference = place["photos"][0]["photo_reference"]
            photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_reference}&key={API_KEY}"

        photographers.append({
            "name": place.get("name"),
            "address": place.get("formatted_address"),
            "rating": place.get("rating", 0),
            "phone": details.get("phone"),
            "website": details.get("website"),
            "maps_link": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "photo": photo_url
        })

    # Sort by rating (highest first)
    photographers.sort(key=lambda x: x["rating"], reverse=True)

    return photographers


@app.route("/", methods=["GET", "POST"])
def index():
    photographers = []
    city = ""

    if request.method == "POST":
        city = request.form["city"].strip()
        photographers = get_photographers(city)

    return render_template("index.html",
                           photographers=photographers,
                           city=city)


@app.route("/download", methods=["POST"])
def download_excel():
    city = request.form["city"].strip()
    photographers = get_photographers(city)

    df = pd.DataFrame(photographers)

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name=f"{city}_photographers.xlsx",
        as_attachment=True
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)