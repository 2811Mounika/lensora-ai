from io import BytesIO
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GOOGLE_API_KEY")
REQUEST_TIMEOUT = 20


def format_google_error(status, error_message):
    status_messages = {
        "REQUEST_DENIED": "Google Places request denied. Check API key restrictions and billing.",
        "OVER_QUERY_LIMIT": "Google Places quota exceeded. Try again later or raise your quota.",
        "INVALID_REQUEST": "Invalid Google Places request. Please try another city.",
        "UNKNOWN_ERROR": "Google Places returned an unknown error. Please retry.",
    }

    base = status_messages.get(status, f"Google Places returned status: {status}")
    if error_message:
        return f"{base} Details: {error_message}"
    return base


def get_place_details(place_id):
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website",
        "key": API_KEY,
    }

    try:
        response = requests.get(details_url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json().get("result", {})
    except requests.RequestException:
        result = {}

    return {
        "phone": result.get("formatted_phone_number", "Not Available"),
        "website": result.get("website", "Not Available"),
    }


def get_photographers(city):
    if not API_KEY:
        return [], "Missing GOOGLE_API_KEY in .env."

    search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    photographers = []
    next_page_token = None
    page_count = 0

    while page_count < 3:
        params = {
            "query": f"wedding photographers in {city}",
            "key": API_KEY,
        }
        if next_page_token:
            params["pagetoken"] = next_page_token

        try:
            response = requests.get(search_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return [], "Unable to reach Google Places API. Check internet/firewall and try again."

        status = data.get("status")
        if status == "ZERO_RESULTS":
            break
        if status != "OK":
            return [], format_google_error(status, data.get("error_message"))

        for place in data.get("results", []):
            place_id = place.get("place_id")
            details = get_place_details(place_id)

            photo_url = None
            if "photos" in place:
                photo_reference = place["photos"][0]["photo_reference"]
                photo_url = (
                    "https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=400&photo_reference={photo_reference}&key={API_KEY}"
                )

            photographers.append(
                {
                    "name": place.get("name"),
                    "address": place.get("formatted_address"),
                    "rating": place.get("rating", 0),
                    "phone": details.get("phone"),
                    "website": details.get("website"),
                    "maps_link": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    "photo": photo_url,
                }
            )

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

        page_count += 1
        time.sleep(2)

    photographers.sort(key=lambda x: x["rating"], reverse=True)
    return photographers, ""


@app.route("/", methods=["GET", "POST"])
def index():
    photographers = []
    city = ""
    error_message = ""
    searched = False

    if request.method == "POST":
        searched = True
        city = request.form.get("city", "").strip()
        if city:
            photographers, error_message = get_photographers(city)
        else:
            error_message = "Please enter a city."

    return render_template(
        "index.html",
        photographers=photographers,
        city=city,
        error_message=error_message,
        searched=searched,
    )


@app.route("/download", methods=["POST"])
def download_excel():
    city = request.form.get("city", "").strip()
    if not city:
        return "City is required.", 400

    photographers, error_message = get_photographers(city)
    if error_message:
        return error_message, 400
    if not photographers:
        return f"No photographers found for {city}.", 404

    df = pd.DataFrame(photographers)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    filename = f"{city.replace(' ', '_')}_photographers.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
