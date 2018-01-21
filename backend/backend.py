import json
import uuid

from flask import Flask, request
import requests

from templates.user_infos import user_infos, cities_1, cities_2
from secrets import HC_KEY, MINUBE_KEY
from templates.categories import clean_cats
app = Flask(__name__)


HOTELS_COMBINED_AUTOSUGGEST = "http://sandbox.hotelscombined.com/api/2.0/search/full?query={city}&limit=10&languageCode=EN&countryCode=ES&apiKey={apikey}"

HOTELS_COMBINED_SEARCH = "http://sandbox.hotelscombined.com/api/2.0/hotels?destination={user_destination}&checkin={ci}&checkout={co}&rooms={rooms}&apiKey={api_key}&sessionID={session_id}&starRating={starRating}&ResponseOptions=images"

HOTELS_COMBINED_BOOKING = "https://www.hotelscombined.com/{redirect_path}"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)"
HC_HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)'}

MI_NUBE = "https://www.minube.net/ajax/call?call_method=ajax/multi_searcher&limit=6&input={input}&api_key={apikey}"
MINUBE_URL_POIS = "http://papi.minube.com/pois?lang=es&zone_id={zone_id}&order_by=score&api_key={apikey}"


# http://sandbox.hotelscombined.com/api/2.0/hotels?destination=place:Barcelona&apikey=AF0C07FC-5E6A-4BD9-B803-AB91710CE02C&sessionid=testsession1&rooms=1&adults_1=2&checkin=2018-02-05&checkout=2018-02-15&ResponseOptions=destination%2Ctoprates%2Cimages

PRICE_SENSITIVITY_MAPPING = {
    '0': 5,
    '1': 4,
    '2': 3,
    '3': 2,
    '4': 1,
    '5': 1
}


@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/user/<user_id>')
def get_user_info(user_id):
    returned_user_infos = user_infos[user_id]
    returned_user_infos['name'] = user_id
    return json.dumps(returned_user_infos)

@app.route('/search/<city>/<sensitivity>')
def get_custom_hotels(city, sensitivity):
    place_id = get_hotels_combined_place_id(city)
    recommended_hotel_cat = PRICE_SENSITIVITY_MAPPING[sensitivity]
    hotel_results = get_hotels_combined_results(place_id, starRating=recommended_hotel_cat)

    mi_nube_auto_headers = {'X-Requested-With': 'XMLHttpRequest'}
    mi_nube_url = MI_NUBE.format(input=city, apikey=MINUBE_KEY)
    mi_nube_respose = requests.get(mi_nube_url, headers = mi_nube_auto_headers)
    mi_nube_zone_id= json.loads(mi_nube_respose._content)['response']['data'][0]['zone_id']

    mi_nube_url_pois = MINUBE_URL_POIS.format(zone_id=mi_nube_zone_id, apikey=MINUBE_KEY)
    mi_nube_pois_resp_json = json.loads(requests.get(mi_nube_url_pois)._content)

    pois_list = []
    for poi in mi_nube_pois_resp_json[0:50]:
        clean_poi = {}
        clean_poi['name'] = poi["name"]
        clean_poi['lat'] = poi["latitude"]
        clean_poi['long'] = poi["longitude"]
        clean_poi['image'] = poi['picture_url']
        clean_poi['subcategory'] = clean_cats[str(poi['subcategory_id'])]
        pois_list.append(clean_poi)

    city_info={}
    city_info['name'] = city
    cities_1.extend(cities_2)
    for available_city in cities_1:
        if available_city['name'].lower() == city.lower():
            city_info['lat'] = available_city['lat']
            city_info['long'] = available_city['long']

    # final_response['pois'] =

    final_response = {}
    final_response['hotels'] = hotel_results
    final_response['pois'] = pois_list
    final_response['city']  = city_info

    return json.dumps(final_response)


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
        cleaned_hotel['images'] = extract_images(hotel['images'])
        cleaned_hotel['description'] = 'great hotel in the city center'

        cleaned_hotel_results.append(cleaned_hotel)
    return cleaned_hotel_results

def extract_images(images_list):
    clean_images = []
    for image in images_list[:5]:
        clean_images.append(image['small'])
    return clean_images



def get_hotel_details(href):
    hotel_details_json = request_til_complete(href, HC_HEADERS)
    hotel_details_results = hotel_details_json['results']
    first_offer = hotel_details_results[0]
    price, preformatted_uri = first_offer['totalRate'], first_offer['bookUri']
    formatted_uri = HOTELS_COMBINED_BOOKING.format(redirect_path=preformatted_uri)
    return price, formatted_uri


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
