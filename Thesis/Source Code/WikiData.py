import requests
import sys


# TODO: comments and docstring
class WikiData:
    """
        Wrapper class for WikiData endpoints
    """

    def __init__(self, poi):
        self.poi_label = poi
        self.poi_id = self.get_wiki_data_id(poi)
        self.raw = self.get_raw()
        self.claims = self.raw['claims']

    @staticmethod
    def get_label(item_id):
        """
            :param item_id: the item to be searched for on WikiData
            :return: string label returned by WikiData
        """

        # search parameters
        search_params = {'format': 'json',
                         'ids': item_id, 'props': 'labels', 'action': 'wbgetentities'}
        # Search url
        search_url = "https://www.wikidata.org/w/api.php"
        # Generating and executing the search request
        r = requests.post(search_url, params=search_params)
        # Extracting label information
        try:
            v = r.json()['entities'][item_id]['labels']['en']['value']
            return v
        except:
            print(r.json())
            print("Unexpected error:", sys.exc_info()[0])

    @staticmethod
    def get_wiki_data_id(poi):
        """
            Method which returns the WikiData id for any given label (in this case a persons name)
            :param poi: string, the name of a person to search for on WikiData
            :return: the QID of the POI
        """
        # search parameters
        search_params = {'format': 'json', 'language': 'en', 'search': poi, 'action': 'wbsearchentities'}
        # Search url
        search_url = "https://www.wikidata.org/w/api.php"
        # Generating and executing the search request
        r = requests.post(search_url, params=search_params)
        # Returning the WikiData QID
        return r.json()['search'][0]['id']

    def get_raw(self):
        uri = "https://www.wikidata.org/wiki/Special:EntityData/" + self.poi_id + ".json"
        return requests.get(uri).json()['entities'][self.poi_id]
