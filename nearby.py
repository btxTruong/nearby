import json
import os
import requests
import log

logger = log.get_logger(__name__)


def requests_(url, params=None, timeout=10):
    response = requests.get(url, params=params, timeout=timeout)
    response = response.json()

    if not response:
        raise ValueError('No data found')

    return response


def extract_data(obj, key, **kwargs):
    """
    Find all values of key if key in obj

    :param obj: (json) Json need to parse
    :param key: (string) key in obj need to extract
    :param exclude: (string) (optional) Avoide parse specific item in json
    :return: (list) value of key in obj
    """

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
                continue
            if k in kwargs.get('exclude', []):
                continue
            if isinstance(v, (dict, list)):
                yield from extract_data(v, key, **kwargs)
    elif isinstance(obj, list):
        for i in obj:
            yield from extract_data(i, key, **kwargs)


class HEREAPI:
    """
    Interact with HERE map API
    """

    def __init__(self, app_id, app_code, **kwargs):
        """
        Initial parameter to connect to HERE API
        :param app_id: (string) provided by HERE map
        :param app_code: (string) provided by HERE map
        :param path_geo: (string) (optional) version geocoding api
            default of 6.2 is current
        :param path_place: (string) (optional) version searching places api
            default of v1 is current
        """

        self._app_id = app_id
        self._app_code = app_code
        self._path_geo = kwargs.get('path_geo', '6.2')
        self._path_place = kwargs.get('path_place', 'v1')

    def geocoding_api(self, location):
        params = {
            'app_id': self._app_id,
            'app_code': self._app_code,
            'searchtext': location,
        }

        geo_url = 'https://geocoder.api.here.com/{}/geocode.json'
        base = geo_url.format(self._path_geo)

        return base, params

    def places_api(self, nearby, location, radius):
        params = {
            'app_id': self._app_id,
            'app_code': self._app_code,
            'q': nearby,
            'at': '{},{};r={}'.format(location['Latitude'],
                                      location['Longitude'],
                                      radius)

        }

        discover_url = ('https://places.cit.api.here.com'
                        '/places/{}/discover/search')
        base = discover_url.format(self._path_place)

        return base, params


class RequesAPI:
    def __init__(self, location, cls_map_api, radius=2000):
        """
        Initial request to map api
        :param location: (dict) **require** contain latitude, longtitude
        :param radius: (int) Search range
        :param cls_map_api: instance MAP API, it provided information to
            request to api
        """

        self.map_api = cls_map_api
        self.radius = radius
        self.location = self.retrive_coordinate(location)

    def retrive_coordinate(self, location):
        """
        Get coordinate of specific place
        :param location: (string) **(required)**
            Address of place need to find coordinate
        :return: (dict) A dictionay contains longtitude, latitude
        """

        base, params = self.map_api.geocoding_api(location)
        response = requests_(base, params=params)

        coordinate = list(extract_data(response, "DisplayPosition"))[0]
        if not coordinate:
            raise ValueError('No coordinate found')

        return coordinate

    def nearby_coor(self, nearby):
        """
        dictionry is response from discover search api.
        It contains coordinate of nearby places around specific place

        :param nearby: (list, tuple) places need to retrieve coordinate
        :return: (dict) A dictionary contains response from search api
        """

        base, params = self.map_api.places_api(nearby,
                                               location=self.location,
                                               radius=self.radius)

        response = requests_(base, params=params)
        if not response['results']['items']:
            logger.debug("Can't find any %s", nearby)

        return response['results']['items']


class GeoJsonFeatureCollection:
    """ Make geojsonfeaturecollection"""

    def __init__(self):
        self._collection = {
            'type': "FeatureCollection",
            'features': []
        }
        self.count_feature = 0

    def add_features(self, longtitude, latitude, vicinity, title):
        features = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [longtitude, latitude]
            },
            'properties': {
                'address': vicinity,
                'name': title,
            },
        }

        if features not in self._collection['features']:
            self.count_feature += 1
            self._collection['features'].append(features)
            return True
        return False

    @property
    def get_geojson(self):
        return self._collection

    @classmethod
    def dump(cls, geojson, filename='geofile'):
        """ Write to GEOJSON file"""

        if not isinstance(geojson, cls):
            raise ValueError('No geojson object provided')

        data = getattr(geojson, 'get_geojson')

        with open(filename + '.geojson', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class Nearby(RequesAPI):
    """ Return file geojson contains coordinates of places
        around specific address
    """

    def __init__(self, location, nearby, cls_map_api, radius=2000):
        super().__init__(location=location,
                         cls_map_api=cls_map_api,
                         radius=radius)
        self.nearby = nearby

    def run(self, size=20):
        if not isinstance(self.nearby, (list, tuple)):
            self.nearby = [self.nearby]

        geojson = GeoJsonFeatureCollection()

        for n in self.nearby:
            response = self.nearby_coor(n)
            cmp_size = 0
            for p in response:
                if cmp_size > size:
                    break

                try:
                    latitude, longitude = p.get('position')
                except TypeError:
                    logger.debug('---No coordinate found---')
                    latitude, longitude = 0, 0

                if geojson.add_features(longitude,
                                        latitude,
                                        p.get('vicinity'),
                                        p.get('title')):
                    cmp_size += 1

        GeoJsonFeatureCollection.dump(geojson, 'pymi')


def main():
    app_id = os.environ.get('APP_ID')
    app_code = os.environ.get('APP_CODE')

    funny_place = ('beer', 'club', 'restaurant')
    address = '2 Vo Oanh, Phuong 25, Binh Thanh, Ho Chi Minh'

    here_api = HEREAPI(app_id, app_code)
    f = Nearby(location=address,
               cls_map_api=here_api,
               nearby=funny_place)
    f.run()


if __name__ == '__main__':
    main()
