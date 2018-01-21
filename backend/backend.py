import json
import uuid

from flask import Flask, request
import requests

from templates.user_infos import user_infos
from secrets import HC_KEY
app = Flask(__name__)


HOTELS_COMBINED_AUTOSUGGEST = "http://sandbox.hotelscombined.com/api/2.0/search/full?query={city}&limit=10&languageCode=EN&countryCode=ES&apiKey={apikey}"

HOTELS_COMBINED_SEARCH = "http://sandbox.hotelscombined.com/api/2.0/hotels?destination={user_destination}&checkin={ci}&checkout={co}&rooms={rooms}&apiKey={api_key}&sessionID={session_id}&starRating={starRating}"

HOTELS_COMBINED_BOOKING = "https://www.hotelscombined.com/{redirect_path}"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)"
HC_HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)'}

PRICE_SENSITIVITY_MAPPING = {
    0: 5,
    1: 4,
    2: 3,
    3: 2,
    2: 1,
    1: 1
}


@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/user/<user_id>')
def get_user_info(user_id):
    return json.dumps(user_infos[user_id])

@app.route('/search/<city>/<sensitivity>')
def get_custom_hotels(city, sensitivity):
    place_id = get_hotels_combined_place_id(city)
    recommended_hotel_cat = PRICE_SENSITIVITY_MAPPING[sensitivity]
    hotel_results = get_hotels_combined_results(place_id, starRating=recommended_hotel_cat)

    # pois =

    final_response = {}
    final_response['hotels'] = hotel_results
    # final_response['pois'] =
    return json.dumps(hotel_results)


def get_hotels_combined_place_id(city):
    hotels_combined_autosuggest_url = HOTELS_COMBINED_AUTOSUGGEST.format(city=city, apikey=HC_KEY)
    hotels_combined_autosuggest_response = requests.get(hotels_combined_autosuggest_url)
    hotels_combined_autosuggest_response_json = json.loads(hotels_combined_autosuggest_response._content)
    hotel_code = hotels_combined_autosuggest_response_json[0].get('key')
    return hotel_code

def request_til_complete(url, headers=None):
    hotels_results = requests.get(url, headers=headers)
    hotels_results_json = json.loads(hotels_results._content)
    while not hotels_results_json['isComplete']:
        if headers is not None:
            hotels_results = requests.get(url, headers=headers)
        else:
           hotels_results = requests.get(url)
        hotels_results_json = json.loads(hotels_results._content)
    return hotels_results_json

def get_hotels_combined_results(place_id, guests=2, rooms=1, checkin='2018-04-03', checkout='2018-04-06', starRating=4):
    session_id = uuid.uuid4()
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)'}
    hotels_combined_search_url = HOTELS_COMBINED_SEARCH.format(user_destination=place_id, ci=checkin, co=checkout,
                                                               rooms=rooms, api_key=HC_KEY, session_id=session_id,
                                                               starRating=starRating)
    hotels_results_json = request_til_complete(hotels_combined_search_url, HC_HEADERS)
    hotels_list = hotels_results_json['results']

    cleaned_hotel_results = []

    for hotel in hotels_list:
        cleaned_hotel = {}
        cleaned_hotel['lat'] = hotel['latitude']
        cleaned_hotel['long'] = hotel['longitude']
        cleaned_hotel['stars'] = hotel['starRating']
        cleaned_hotel['name'] = hotel['name']
        price, booking_uri = get_hotel_details(hotel['href'])
        cleaned_hotel['price'] = price
        cleaned_hotel['booking_url'] = booking_uri
        cleaned_hotel_results.append(cleaned_hotel)

    return cleaned_hotel_results


def get_hotel_details(href):
    hotel_details_json = request_til_complete(href, HC_HEADERS)
    hotel_details_results = hotel_details_json['results']
    first_offer = hotel_details_results[0]
    price, preformatted_uri = first_offer['totalRate'], first_offer['bookUri']
    formatted_uri = HOTELS_COMBINED_BOOKING.format(redirect_path=preformatted_uri)
    return price, formatted_uri


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
