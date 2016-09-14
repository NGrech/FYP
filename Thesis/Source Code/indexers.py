import os
import pickle

from nltk.tokenize import word_tokenize, sent_tokenize

from WikiData import WikiData


class TimeQualifier:

    """
        This class is responsible for storing points in time and ranges.
    """

    def __init__(self, precision: int, t0: str, t1=""):
        """
            :param t0:  point in times expected as YYYY/MM/DD
            :param t1:  point in times expected as YYYY/MM/DD, optional

            NOTE:   If t1 is not specified then the time object is treated as a point in time
                    otherwise it is treated as a range
        """

        self.date = t0
        self.precision = precision
        self.range = None
        """ Extracting the starting point in time"""
        if t1:
            self.range = t1


class RelationInformation:

    """ This class is used to store information about the relations which have been discovered
        this object must at least contain the primary source of the relation
        all other fields may be null
    """

    def __init__(self, source):

        """
            :param source: the source from which the original relation was extracted
        """

        self.source = source
        self.time = None
        self.text = None
        self.sub = None

    # TODO: comments & docstring
    def add_text(self, txt: str, source: str) -> None:
        if self.text:
            self.text.append((txt, source))
        else:
            self.text = [(txt, source)]

    # TODO: comments & docstring
    def add_time(self, start_time: str, precision: int, end_time="") -> None:
        self.time = TimeQualifier(precision, start_time, end_time)

    # TODO: comments & docstring
    def add_sub_rel(self, prop, entity, source):
        if self.sub:
            self.sub.append((prop, entity, source))
        else:
            self.sub = [(prop, entity, source)]


class RelationCollection:

    """ RelationCollection class is responsible for cataloging the resolved entities (RDF subjects and objects) and
        Propositions resolved from structured and unstructured data
    """

    def __init__(self, poi):

        """
        :type poi: str
        """
        self.poi = poi
        """ Label for the person of interest (poi)"""

        self.entities = dict()
        """ Dictionary of entities, Key = entity id, entity label"""

        self.prepositions = dict()
        """ Dictionary of prepositions Key = preposition id, preposition label"""

        self.relations = dict()
        """ Dictionary of relations key is the tuple of the preposition and object
            value is a relation information object"""

        if os.path.isfile('propLabels.pickle'):
            with open('propLabels.pickle', 'rb') as handle:
                self.stored_labels = pickle.load(handle)
        else:
            self.stored_labels = dict()
        ''' Attempting to load master list of property labels'''

    def add_entity(self, entity):

        """
        :param entity: Id for the entity being added to the dictionary

        This method will add the
        """

        if entity not in self.entities:
            label = WikiData.get_label(entity)
            self.entities[entity] = label

    def add_prop(self, prop):
        """
            :param prop: the id for the preposition to be added to the list
        """

        if prop not in self.stored_labels:
            label = WikiData.get_label(prop)
            self.stored_labels[prop] = label
            self.prepositions[prop] = label
        else:
            if prop not in self.prepositions:
                self.prepositions[prop] = self.stored_labels[prop]

    def add_relation(self, prop, entity, source):
        """
        :param prop: The preposition of the main relation
        :param entity: The object of the main relation
        :param source: The source of the main relation
        """

        if (prop, entity) not in self.relations:

            if prop not in self.prepositions:
                self.add_prop(prop)
            if entity not in self.entities:
                self.add_entity(entity)

            ri = RelationInformation(source)
            self.relations[(prop, entity)] = ri

    def update_time(self, rel, start: tuple, precision: str, end=None)-> None:
        time_str = "{}/{}/{}".format(start[0], start[1], start[2])
        if end:
            end_str = "{}/{}/{}".format(end[0], end[1], end[2])
            self.relations[rel].add_time(time_str, precision, end_str)
        else:
            self.relations[rel].add_time(time_str, precision)

    def update_sub_relation(self, rel, sub, source):
        self.add_prop(sub[0])
        self.add_entity(sub[1])
        self.relations[rel].add_sub_rel(sub[0], sub[1], source)


# TODO: comments & docstring
class TimeIndex:

    def __init__(self):
        self.point = dict()
        self.range_start = dict()
        self.range_end = dict()
        self.birth = None
        self.death = None

    def add_birth(self, year, month, day):
        self.birth = (year, month, day)

    def add_death(self, year, month, day):
        self.death = (year, month, day)

    def add_point(self, rel, year: int, month=0, day=0):
        pit = (year, month, day)
        if pit in self.point:
            self.point[pit].append(rel)
        else:
            self.point[pit] = [rel]

    def add_rage(self, rel, s_year: int, e_year: int, s_month=0, e_month=0, s_day=0, e_day=0):
        start = (s_year, s_month, s_day)
        end = (e_year, e_month, e_day)

        if start in self.range_start:
            if end in self.range_start[start]:
                self.range_start[start][end].append(rel)
            else:
                self.range_start[start][end] = [rel]
        else:
            self.range_start[start] = dict()
            self.range_start[start][end] = [rel]

        if end in self.range_end:
            if start in self.range_end[end]:
                self.range_end[end][start].append(rel)
            else:
                self.range_end[end][start] = [rel]
        else:
            self.range_end[end] = dict()
            self.range_end[end][start] = [rel]


class TextGroup:

    def __init__(self, txt_type: str, txt: str):
        self.txt_type = txt_type

        if txt_type is 'paragraph':
            self.sentences = [word_tokenize(w) for w in sent_tokenize(txt)]
        else:
            self.title = word_tokenize(txt)


class TextCollection:

    def __init__(self, txt: list, raw: str):
        self.txt = txt
        self.raw = raw

    def update_ner(self, ner: list)-> None:
        for t in self.txt:
            if t.txt_type is 'paragraph':
                for i in range(len(t.sentences)):
                    t.sentences[i] = ner[:len(t.sentences[i])]
                    ner = ner[len(t.sentences[i]):]
            else:
                t.title = ner[:len(t.title)]
                ner = ner[len(t.title):]


class TimeLine:

    def __init__(self):
        self.events = dict()

    def add_to_events(self, date: tuple, txt: str, tags, src, wd: tuple=None, end: tuple=None):
        if date in self.events:
            if end:
                if end in self.events[date]:
                    if wd:
                        if wd in self.events[date][end]['matched']:
                            self.events[date][end]['matched'][wd].append((txt, tags, src))
                        else:
                            self.events[date][end]['matched'][wd] = [(txt, tags, src)]
                    else:
                        self.events[date][end]['unmatched'].append((txt, tags, src))
                else:
                    if wd:
                        self.events[date][end] = {'matched': {wd: [(txt, tags, src)]}, 'unmatched': dict()}
                    else:
                        self.events[date][end] = {'matched': dict(), 'unmatched': [(txt, tags, src)]}
            else:
                if wd:
                    if wd in self.events[date]['matched']:
                        self.events[date]['matched'][wd].append((txt, tags, src))
                    else:
                        self.events[date]['matched'][wd] = [(txt, tags, src)]
                else:
                    self.events[date]['unmatched'].append((txt, tags, src))
        else:
            if wd:
                self.events[date] = {'matched': {wd: [(txt, tags, src)]}, 'unmatched': dict()}
            else:
                self.events[date] = {'matched': dict(), 'unmatched': [(txt, tags, src)]}
