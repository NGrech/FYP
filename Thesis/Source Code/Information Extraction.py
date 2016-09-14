import json
import logging
import os
import pickle
import re
import string
from pprint import pprint

import dateutil.parser
import nltk
from fuzzywuzzy import fuzz
from nltk.chunk import RegexpParser
from datetime import datetime

from indexers import TextCollection

TEST = True


# ----- DATE FINDING ---------------------


class DateHolder:
    def __init__(self, date: list, end_date: list = None):
        date_str = ' '.join([d for d in date])
        parsed_date = dateutil.parser.parse(date_str)
        self.precision = 8 + len(date)
        if end_date:
            self.date_type = 'range'
            end_date_str = ' '.join(d for d in end_date)
            parsed_end_date = dateutil.parser.parse(end_date_str)
            if self.precision == 9:
                self.start = (parsed_date.year, 0, 0)
                self.end = (parsed_end_date.year, 0, 0)
            elif self.precision == 10:
                self.start = (parsed_date.year, parsed_date.month, 0)
                self.end = (parsed_end_date.year, parsed_end_date.month, 0)
            else:
                self.start = (parsed_date.year, parsed_date.month, parsed_date.day)
                self.end = (parsed_end_date.year, parsed_end_date.month, parsed_end_date.day)
        else:
            if self.precision == 9:
                self.point = (parsed_date.year, 0, 0)
            elif self.precision == 10:
                self.point = (parsed_date.year, parsed_date.month, 0)
            else:
                self.point = (parsed_date.year, parsed_date.month, parsed_date.day)
            self.date_type = 'point'

    def pprint(self):
        if self.date_type == 'point':
            print('Type: Point \n\t Value: {0}'.format(self.point))
        else:
            print('Type: Range \n\t S: \t{0} \n\t E: \t{1}'.format(self.start, self.end))

    def log_ds(self):
        if self.date_type == 'point':
            return 'Type: Point \n\t Value: {0}'.format(self.point)
        else:
            return 'Type: Range \n\t S: \t{0} \n\t E: \t{1}'.format(self.start, self.end)

    def get_date_str(self):
        months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                  'september', 'october', 'november', 'december']
        if self.date_type == 'point':
            if self.precision == 9:
                return '{0}'.format(self.point[0])
            elif self.precision == 10:
                return '{1} {0}'.format(self.point[0], months[self.point[1] - 1])
            else:
                return '{2} {1} {0}  '.format(self.point[0], months[self.point[1] - 1], self.point[2])
        else:
            if self.precision == 9:
                return '{0}'.format(self.start[0])
            elif self.precision == 10:
                return '{1} {0}'.format(self.start[0], months[self.start[1] - 1])
            else:
                return '{2} {1} {0}  '.format(self.start[0], months[self.start[1] - 1], self.start[2])


class DateMiner:
    def __init__(self, dob: tuple = None, dod: tuple = None):
        self.dob = dob
        self.dod = dod
        self.previous_year = None
        self.months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                       'september', 'october', 'november', 'december']
        self.short_months = [m[:3] for m in self.months]
        self.n_dates = 0
        self.range_mid_words = ['and', 'until', 'to']

    def clear_memory(self):
        self.previous_year = None

    def date_type(self, item: str):

        if item.isdigit():
            if len(item) == 4:
                if self.dob:
                    if int(item) >= self.dob[0]:
                        return 'Y'
                    else:
                        return 'OR'
                else:
                    return 'Y'
            elif len(item) in range(3) and int(item) <= 31:
                return 'D'
        elif item.lower() in self.months or item.lower() in self.short_months:
            return 'M'
        elif len(item) == 5 and item[4:] == 's' and item[:len(item) - 1].isdigit():
            return 'Ys'
        else:
            return 'ND'

    def process_year(self, i: int, s: list):
        # Last Date Left
        if self.n_dates == 1:
            dh = DateHolder([s[i][0]])
            self.n_dates -= 1
            self.previous_year = str(dh.point[0])
            return [dh], i
        c = i + 1
        # Year -> Range case
        if s[c][0] in self.range_mid_words:
            # Year -> AND
            if s[c][0] == 'and':
                p = i - 1
                # Checking for preceding range word
                if s[p][0].lower() == 'between':
                    if s[c + 1][1] == 'DATE' and self.date_type(s[c + 1][0]) == 'Y':
                        start = [s[i][0]]
                        c += 1
                        end = [s[c][0]]
                        dh = DateHolder(start, end)
                        self.n_dates -= 2
                        self.previous_year = str(dh.start[0])
                        return [dh], c
                    else:
                        dh = DateHolder([s[i][0]])
                        self.n_dates -= 1
                        self.previous_year = str(dh.point[0])
                        return [dh], i
                else:
                    dh = DateHolder([s[i][0]])
                    self.n_dates -= 1
                    self.previous_year = str(dh.point[0])
                    return [dh], i
            # Year -> Range word (not and)
            else:
                c += 1
                if s[c][1] == 'DATE' and self.date_type(s[c][0]) == 'Y':
                    start = [s[i][0]]
                    end = [s[c][0]]
                    dh = DateHolder(start, end)
                    self.n_dates -= 2
                    self.previous_year = str(dh.start[0])
                    return [dh], c
        # Year -> (',',DATE)+('and',DATE)
        elif s[c][0] == ',' and s[c + 1][1] == 'DATE' and self.date_type(s[c + 1][0]) == 'Y':
            dates = list()
            dh = DateHolder([s[i][0]])
            dates.append(dh)
            self.n_dates -= 1
            self.previous_year = str(dh.point[0])
            flag = True
            c += 1
            while flag:
                if s[c][1] == 'DATE':
                    dh = DateHolder([s[c][0]])
                    dates.append(dh)
                    self.n_dates -= 1
                    self.previous_year = str(dh.point[0])
                    c += 1
                elif s[c][0] == ',':
                    c += 1
                elif s[c][0] == 'and':
                    if s[c + 1][1] == 'DATE':
                        c += 1
                        dh = DateHolder([s[c][0]])
                        dates.append(dh)
                        self.n_dates -= 1
                        self.previous_year = str(dh.point[0])
                        flag = False

            return dates, c
        # Year -> terminal
        else:
            dh = DateHolder([s[i][0]])
            self.n_dates -= 1
            self.previous_year = str(dh.point[0])
            return [dh], i

    def month_point(self, y, m, d):
        if not y and self.previous_year:
            y = self.previous_year
        if y and m and d:
            return [d, m, y]
        else:
            return [m, y]

    def month_range(self, sy, sm, sd, ey, em, ed):
        start = self.month_point(sy, sm, sd)

        if not ey and sy:
            ey = sy
        elif not ey and self.previous_year:
            ey = self.previous_year

        end = self.month_point(ey, em, ed)

        return start, end

    def process_month_point(self, month, day, i, s, ri):
        s_year = None
        if s[i + 1][1] == 'DATE' and self.date_type(s[i + 1][0]) == 'Y':
            # year present in start date
            ri = i + 1
            s_year = s[ri][0]
            self.n_dates -= 1
        date = self.month_point(s_year, month, day)
        dh = DateHolder(date)
        self.previous_year = str(dh.point[0])
        return [dh], ri

    def process_month(self, i: int, s: list):
        # Checking for day
        s_month = s[i][0]
        self.n_dates -= 1
        s_day = None
        if i - 1 >= 0:
            if self.date_type(s[i - 1][0]) == 'D':
                s_day = s[i - 1][0]
                self.n_dates -= 1

        # Checking if range or point
        if s[i + 1][1] == 'DATE':
            ri = i + 2
        else:
            ri = i + 1
        if s[ri][0] in self.range_mid_words:
            # Range Case
            if s[ri][0] == 'and':
                if s[i - 1][0].lower() == 'between':
                    # Range case not multiple event
                    return self.process_month_range(s, i, s_month, s_day, ri)
                else:
                    return self.process_month_point(s_month, s_day, i, s, ri)
            # range case goes here also
            elif s[ri][0] == 'to' and s[ri + 1][0] != 'DATE':
                return self.process_month_point(s_month, s_day, i, s, ri)
            else:
                return self.process_month_range(s, i, s_month, s_day, ri)
        else:
            # Point Case
            return self.process_month_point(s_month, s_day, i, s, ri)

    def process_month_range(self, s, i, s_month, s_day, ri):
        s_year = None
        if s[i + 1][1] == 'DATE' and self.date_type(s[i + 1][0]) == 'Y':
            # year present in start date
            s_year = s[i + 1][0]
            self.n_dates -= 1
            # Collecting end day if present
        e_day = None
        if s_day:
            if self.date_type(s[ri + 1][0]) == 'D':
                ri += 1
                e_day = s[ri]
                self.n_dates -= 1
        e_month = None
        if s[ri + 1][1] == 'DATE' and self.date_type(s[ri + 1][0]) == 'M':
            ri += 1
            e_month = s[ri][0]
            self.n_dates -= 1
        e_year = None
        if s[ri + 1][1] == 'DATE' and self.date_type(s[ri + 1][0]) == 'Y':
            ri += 1
            e_year = s[ri][0]
            self.n_dates -= 1

        # building dates:
        start, end = self.month_range(s_year, s_month, s_day, e_year, e_month, e_day)
        dh = DateHolder(start, end)
        self.previous_year = str(dh.start[0])
        return [dh], ri

    def process_decade(self, i, s):
        year = s[i][0][:len(s[i][0]) - 1]
        end_year = year[:len(year) - 1] + '9'
        dh = DateHolder([year], [end_year])
        self.n_dates -= 1
        self.previous_year = str(dh.start[0])
        return [dh], i

    def process_sent(self, s: list) -> list:
        methods = {
            'Y': self.process_year,
            'M': self.process_month,
            'Ys': self.process_decade
        }

        dates = list()
        self.n_dates = len([n for n in s if n[1] == 'DATE'])

        i = 0
        while i < len(s):
            if s[i][1] == 'DATE':
                w_type = self.date_type(s[i][0])
                if w_type in methods:
                    date_lst, ni = methods[w_type](i, s)
                    i = ni
                    dates += date_lst
                    if self.n_dates <= 0:
                        break
                else:
                    self.n_dates -= 1
                    print('Warning:', s[i])
            i += 1

        return dates

    @staticmethod
    def remove_duplicate_dates(dates: list) -> list:
        start = dates
        end = []
        while start:
            c = start.pop(0)
            for n in start:
                if c.date_type == n.date_type:
                    if c.date_type == 'range':
                        '''handling ranges'''
                        if c.start[0] == n.start[0] and c.end[0] == n.end[0]:
                            if c.precision - n.precision == 1:
                                start.pop(0)
                            elif n.precision - c.precision == 1:
                                c = start.pop(0)
                    else:
                        '''handling points'''
                        if c.point[0] == n.point[0]:
                            if c.precision - n.precision == 1:
                                start.pop(0)
                            elif n.precision - c.precision == 1:
                                c = start.pop(0)

            end.append(c)
        return end


# --- Text Processing ------------------
class EventInfo:
    def __init__(self, date: DateHolder, txt: str, raw: list, match: tuple = None):
        self.txt = txt
        self.raw = raw
        self.match = match
        if date.date_type == 'point':
            self.date = date.point
            self.date_range = None
            self.precision = date.precision
        else:
            self.date = date.start
            self.date_range = date.end
            self.precision = date.precision

    def format_txt(self):
        txt = self.txt.split()
        my_txt = "".join([" "+i if not i.startswith("'") and i not in string.punctuation else i for i in txt])
        return my_txt.strip()

    def pprint(self):
        print('{0} {1} {2}'.format(self.date[2], self.date[1], self.date[0]))
        if self.date_range:
            print('{0} {1} {2}'.format(self.date_range[2], self.date_range[1], self.date_range[0]))
        print('txt: {}'.format(self.txt))
        if self.match:
            print('Matched')


class Determiner:
    def __init__(self, poi):
        self.default = poi
        self.name_frags = set(poi.split())
        self.references = list()
        self.guessed_gender = ''

    @staticmethod
    def group_runs(li):
        out = []
        last = li[0]
        for x in li:
            if x - last > 1:
                yield out
                out = []
            out.append(x)
            last = x
        yield out

    def find_names(self, s: list) -> list:
        # checking correctly tagged people
        names = list()
        checked = list()
        temp_index = [i for i in range(len(s)) if s[i][2] == 'PERSON']

        if temp_index:
            index_groups = self.group_runs(temp_index)
            for group in index_groups:
                checked += group
                name = ' '.join([s[p][0] for p in group])

                # checking right
                n = group[-1] + 1

                while n <= len(s) - 1 and s[n][1] == 'NNP' and s[n][0] in self.name_frags:
                    name += ' ' + s[n][0]
                    checked.append(n)
                    n += 1
                # checking left

                n = group[0] - 1
                while n >= 0 and s[n][1] == 'NNP' and s[n][0] in self.name_frags:
                    name = s[n][0] + ' ' + name
                    checked.append(n)
                    n -= 1

                if name not in names:
                    names.append(name.strip())

        # checking if name fragments are known
        for n in names:
            for nf in n.split():
                if nf not in self.name_frags:
                    self.name_frags.add(nf)

        # checking for organizations
        temp_index = [i for i in range(len(s)) if s[i][2] == 'ORGANIZATION']

        if temp_index:

            index_groups = self.group_runs(temp_index)

            for group in index_groups:
                name = ''
                for i in group:
                    if s[i][0] in self.name_frags and i not in checked:
                        name += s[i][0] + ' '
                    else:
                        break
                    if name not in names:
                        names.append(name)

        # checking for untagged names
        name = ''
        for n in range(len(s)):
            if s[n][0] in self.name_frags and n not in checked:
                name += s[n][0] + ' '
            elif name:
                names.append(name)
                name = ''

        if names:
            return names
        else:
            return []

    def update_state(self, s):
        names = self.find_names(s)
        if names:
            self.references.append(names)
            return names
        else:
            return []

    def clean_state(self):
        self.references = list()


class EventExtractor:
    def __init__(self, poi):

        self.poi = poi
        # Loading first step data structures
        ti_file = poi.replace(" ", "_") + "timeIndex.pickle"
        ri_file = poi.replace(" ", "_") + "relationIndex.pickle"

        with open(ti_file, 'rb') as handle:
            self.time_index = pickle.load(handle)
        with open(ri_file, 'rb') as handle:
            self.relation_index = pickle.load(handle)

        dob = None
        dod = None

        if self.time_index.birth:
            dob = self.time_index.birth
        if self.time_index.death:
            dod = self.time_index.death

        self.determiner = Determiner(self.poi)
        self.dm = DateMiner(dob, dod)
        self.chunker = Chunker()
        self.tl = dict()

    @staticmethod
    def strict_match_date(date: tuple, s_dict: dict, d_type: str) -> list:
        if date in s_dict:
            if d_type == 'range':
                matches = []
                for l in s_dict[date].values():
                    matches += l
                return matches
            else:
                return s_dict[date]
        else:
            return []

    @staticmethod
    def precision_descent_match(precision: int, date: tuple, s_dict: dict, d_type: str):
        p = precision - 8
        key_lst = {k for k in s_dict.keys()}
        p_matches = set()

        if p == 1:
            for k in key_lst:
                if date[:1] == k[:1]:
                    p_matches.add(k)
        elif p > 1:
            for p in [2, 1]:
                for k in key_lst:
                    if date[:p] == k[:p]:
                        p_matches.add(k)

        matches = []
        if p_matches:
            for pm in p_matches:
                if d_type == 'range':
                    for l in s_dict[pm].values():
                        matches += l
                else:
                    matches += s_dict[pm]
            return matches
        else:
            return []

    def match_date_type(self, date: tuple, precision: int, dict_type: str):
        if dict_type == 'point':
            matches = self.strict_match_date(date, self.time_index.point, 'point')
            if matches:
                return matches
            else:
                matches = self.precision_descent_match(precision, date, self.time_index.point, 'point')
                if matches:
                    return matches
                else:
                    return []
        elif dict_type == 'start':
            matches = self.strict_match_date(date, self.time_index.range_start, 'range')
            if matches:
                return matches
            else:
                matches = self.precision_descent_match(precision, date, self.time_index.range_start, 'range')
                if matches:
                    return matches
                else:
                    return []
        else:
            matches = self.strict_match_date(date, self.time_index.range_end, 'range')
            if matches:
                return matches
            else:
                matches = self.precision_descent_match(precision, date, self.time_index.range_end, 'range')
                if matches:
                    return matches
                else:
                    return []

    def match_date(self, date: DateHolder):
        if date.date_type == 'point':
            matches = self.match_date_type(date.point, date.precision, 'point')
            if matches:
                return matches
            else:
                matches = self.match_date_type(date.point, date.precision, 'start')
                if matches:
                    return matches
                else:
                    matches = self.match_date_type(date.point, date.precision, 'end')
                    if matches:
                        return matches
                    else:
                        return []
        else:
            matches = self.match_date_type(date.start, date.precision, 'start')
            if matches:
                return matches
            else:
                matches = self.match_date_type(date.end, date.precision, 'end')
                if matches:
                    return matches
                else:
                    matches = self.match_date_type(date.start, date.precision, 'point')
                    matches += self.match_date_type(date.end, date.precision, 'point')
                    if matches:
                        return matches
                    else:
                        return []

    def poi_ref_by_name(self, names):
        for name in names:
            score = fuzz.partial_ratio(self.poi, name)
            if score >= 90:
                return True
        return False

    def match_rel(self, txt: str, rels: list):

        entity = self.relation_index.entities[rels[0][1]]
        score = fuzz.partial_ratio(entity, txt)
        cb = (rels[0], score)

        for r in rels[1:]:
            entity = self.relation_index.entities[r[1]]
            score = fuzz.partial_ratio(entity, txt)
            if score > cb[1]:
                cb = (r, score)

        if cb[1] > 80:
            return cb[0]
        else:
            return None

    def pick_best_date(self, date: DateHolder, rel: tuple):
        try:
            wd_date_temp = self.relation_index.relations[rel].time
            wd_precision = wd_date_temp.precision
            wd_date = tuple(wd_date_temp.date.split('/'))

            if date.date_type == 'point':
                if wd_date[0] != date.point[0]:
                    return date
                if date.precision > wd_precision:
                    return date
                else:
                    date.point = tuple(wd_date_temp.date.split('/'))
                    return date
            else:
                if wd_date[0] != date.start[0]:
                    return date
                if date.precision < wd_precision:
                    date.start = tuple(wd_date_temp.date.split('/'))
                    date.end = tuple(wd_date_temp.range.split('/'))
                    return date
                else:
                    return date
        except:
            return date

    @staticmethod
    def prp_test(s: list):
        for n in s:
            if re.match(r'(PRP.*|WP.*)', n[1]):
                return True
            elif n[2] == 'ORGANIZATION':
                return False

    def resolve_prp(self, s: list, people: list):
        print('\t\tTrying to resolve prepositions')
        if people:
            print('\t\t People found to resolve')
            for n in s:
                if re.match(r'(PRP.*|WP.*)', n[1]):
                    person = people[0]
                    if n[0].lower() in ['he', 'she', 'his', 'her']:
                        if not self.determiner.guessed_gender:
                            print('\t\tAssigning Gender')
                            if n[0].lower() in ['he', 'his']:
                                self.determiner.guessed_gender = ['he', 'his']
                            else:
                                self.determiner.guessed_gender = ['she', 'her']
                            print(self.determiner.guessed_gender)

                        if n[0].lower() in self.determiner.guessed_gender:
                            print('\t\tPreposition matched guessed gender')
                            if fuzz.partial_ratio(self.poi, person) > 90:
                                print('\t\t Matched preposition to poi, updating string')
                                txt = ' '.join([w[0] for w in s[:s.index(n) + 1]]).strip()
                                txt += ' (' + person + ')'
                                txt += ' ' + ' '.join([w[0] for w in s[s.index(n) + 1:]]).strip()
                                return txt
                    elif n[0].lower() in ['who', 'whom']:
                        if fuzz.partial_ratio(self.poi, person) > 90:
                            print('\t\t Matched preposition to poi, updating string')
                            txt = ' '.join([w[0] for w in s[:s.index(n) + 1]]).strip()
                            txt += ' (' + person + ')'
                            txt += ' ' + ' '.join([w[0] for w in s[s.index(n) + 1:]]).strip()
                            return txt
        else:
            print('\t\tNo people found to resolve, using default')
            for n in s:
                if re.match(r'(PRP.*|WP.*)', n[1]):
                    person = self.determiner.default
                    if n[0].lower() in ['he', 'she', 'his', 'her']:
                        if n[0].lower() in self.determiner.guessed_gender:
                            print('\t\t Matched preposition to poi, updating string')
                            txt = ' '.join([w[0] for w in s[:s.index(n) + 1]]).strip()
                            txt += ' (' + person + ')'
                            txt += ' ' + ' '.join([w[0] for w in s[s.index(n) + 1:]]).strip()
                            return txt
                    elif n[0].lower() in ['who', 'whom']:
                        print('\t\t Matched preposition to poi, updating string')
                        txt = ' '.join([w[0] for w in s[:s.index(n) + 1]]).strip()
                        txt += ' (' + person + ')'
                        txt += ' ' + ' '.join([w[0] for w in s[s.index(n) + 1:]]).strip()
                        return txt
        return None

    def add_event(self, dh: DateHolder, ei: EventInfo):
        if dh.date_type == 'point':
            if dh.point in self.tl:
                self.tl[dh.point].append(ei)
            else:
                self.tl[dh.point] = [ei]
        else:
            if dh.start in self.tl:
                self.tl[dh.start].append(ei)
            else:
                self.tl[dh.start] = [ei]

    def no_match_resolution(self, c_state: list, txt: str, date: DateHolder, sent: list):
        if c_state:
            if self.poi_ref_by_name(c_state):
                print('\t\t POI ref')
                print('\t\t Indexing New Event')
                print(txt)
                self.add_event(date, EventInfo(date, txt, sent))
                return True
            else:
                if self.prp_test(sent):
                    print('\t\tContains Preposition')
                    txt = self.resolve_prp(sent, [])
                    if txt:
                        print('\t\tPrep resolved to poi')
                        print('\t\tIndexing New Event')
                        print(txt)
                        self.add_event(date, EventInfo(date, txt, sent))
                        return True
        else:
            print('\t\tChecking for prepositional reference')
            if self.prp_test(sent):
                print('\t\tContains Preposition')
                txt = self.resolve_prp(sent, self.determiner.references[-1])
                if txt:
                    print('\t\tPrep resolved to poi')
                    print('\t\tIndexing New Event')
                    print(txt)
                    self.add_event(date, EventInfo(date, txt, sent))
                    return True
        return False

    @staticmethod
    def extract_date_phrases(tree: nltk.tree.Tree):
        date_phrases = list()
        for st in tree:
            if isinstance(st, nltk.tree.Tree) and re.match(r'.*D-CLAUSE.*', st.label()):
                date_phrases.append([w for w in st.leaves()])
            elif isinstance(st, nltk.tree.Tree):
                print('Warning Unhandled chunk : {0}'.format(st.label()))

        return date_phrases

    def single_date_process(self, date: DateHolder, txt: str, sent: list, c_state: list, ):
        print('\tSingle Date Processing')
        rels = self.match_date(date)
        if rels:
            print('\t\t Date Matched, analyzing matches')
            rel = self.match_rel(txt, rels)
            if rel:
                print('\t\t!! Match found !!')
                print('\t\tIndexing Match')
                print(txt)
                print(self.relation_index.prepositions[rel[0]], self.relation_index.entities[rel[1]])
                date = self.pick_best_date(date, rel)
                self.add_event(date, EventInfo(date, txt, sent, rel))
            else:
                print('\t\t No Match Found (rel)!!')
                if not self.no_match_resolution(c_state, txt, date, sent):
                    print('\t\tDate Not Indexed')
                    pprint(txt)
        else:
            print('\t\t No Match Found (Date)!!')
            if not self.no_match_resolution(c_state, txt, date, sent):
                print('\t\tDate Not Indexed')
                pprint(txt)

    @staticmethod
    def bind_dates(dates: list, phrases: list):
        bound_dates = list()
        for d in dates:
            d_str = d.get_date_str()

            p_txt = ' '.join([w[0] for w in phrases[0]])
            score = fuzz.partial_ratio(d_str, p_txt)
            cb = (phrases[0], score)

            for p in phrases[1:]:
                p_txt = ' '.join([w[0] for w in p])
                score = fuzz.partial_ratio(d_str, p_txt)
                if score > cb[1]:
                    cb = (p, score)

            if cb[1] > 80:
                bound_dates.append((d, cb[0]))
        return bound_dates

    def process_text(self, tc: TextCollection):
        ns = 1
        for frag in tc.txt:
            if frag.txt_type == 'paragraph':
                print('Processing next Paragraph\n ====================== \n')

                for s in frag.sentences:
                    print('\t Processing next sentence {0}\n ----------------- \n'.format(ns))
                    de_logger.info('Phrase # {0}-------------------------------'.format(ns))
                    de_logger.info('Phrase:')

                    ns += 1

                    print('\t\t Final preprocess on sentence')
                    sent = self.chunker.prepare_sentence(s)
                    txt = ' '.join([w[0] for w in s])
                    de_logger.info(txt)
                    print('\t\t Finding last referenced people')
                    c_state = self.determiner.update_state(sent)
                    print(c_state)
                    print('\t\t Extracting Dates')

                    try:
                        dates = self.dm.process_sent(s)
                    except:
                        print('\t\t DATE Extraction warning for {0}'.format(s))
                        continue

                    if dates:
                        de_logger.info('Dates extracted:')
                        for d in dates:
                            de_logger.info(d.log_ds())
                    else:
                        de_logger.info('No Dates Extracted')

                    if len(dates) == 1:
                        self.single_date_process(dates[0], txt, sent, c_state)

                    elif len(dates) > 1:
                        print('\t Multi Date Case')
                        md_logger.info('\nMulti Date Case--------------------------------')
                        md_logger.info('Original Phrase: {0}'.format(txt))

                        tree = self.chunker.generate_tree(sent)
                        # extracting date phrases
                        print('\t\t Extracting Date phrases')
                        date_phrases = self.extract_date_phrases(tree)
                        if date_phrases:
                            print('Date phrases found:')
                            md_logger.info('Date Phrases:')
                            for dp in date_phrases:
                                md_logger.info(' '.join([w[0] for w in dp]))

                            # binding phrases to dates
                            bound_dates = self.bind_dates(dates, date_phrases)
                            if bound_dates:
                                md_logger.info('Bound Dates:')
                                print('\t\t Dates Bound')
                                for d, p in bound_dates:
                                    md_logger.info('{0} - {1}'.format(d.get_date_str(), ' '.join([w[0] for w in p])))
                                    # processing bound pairs
                                    txt = ' '.join([w[0] for w in p])
                                    self.single_date_process(d, txt, p, c_state)

                    else:
                        print('\tNo Date Case')

    @staticmethod
    def build_date_object(date: tuple):
        date_obj = dict()
        date_obj['year'] = date[0]
        if date[2] != 0:
            date_obj['day'] = date[2]
            date_obj['month'] = date[1]
        elif date[1] != 0:
            date_obj['month'] = date[1]

        return date_obj

    @staticmethod
    def find_range_groups(ranges: list):
        range_groups = list()

        while ranges:
            cg = [ranges.pop(0)]
            for r in ranges:
                if r.date_range == cg[0].date_range:
                    cg.append(ranges.pop(ranges.index(r)))
            range_groups.append(cg)

        return range_groups

    def build_timeline(self):

        heading = ''

        json_file = dict()
        json_file['title'] = dict()
        json_file['title']['text'] = dict()
        json_file['title']['text']['headline'] = self.poi
        json_file['title']['text']['text'] = "A timeline for {0} generated with data from WikiData " \
                                             "and Wikipedia".format(self.poi)

        # Creating the events
        json_file['events'] = list()
        json_file['era'] = list()
        for k, v in self.tl.items():

            if self.dm.dob and self.dm.dob[0] > int(k[0]):
                continue
            if self.dm.dod and self.dm.dod[0] < int(k[0]):
                continue

            ranges = [ei for ei in v if ei.date_range is not None]
            points = [ei for ei in v if ei.date_range is None]

            # processing points
            if points:
                seen = list()
                event = dict()
                event['start_date'] = self.build_date_object(k)

                event_text = dict()
                event_text['headline'] = heading

                e_txt = ''
                for i in range(len(points)):
                    txt = points[i].format_txt()
                    if points[i].match:
                        prep = self.relation_index.prepositions[points[i].match[0]]
                        ent = self.relation_index.entities[points[i].match[1]]
                        match_logger.info('\nMatched item -------------------')
                        match_logger.info('Display Phrase: {0}'.format(txt))
                        match_logger.info('Matched to: {0} {1} {2} '.format(self.poi, prep, ent))
                    if txt in seen:
                        continue
                    else:
                        seen.append(txt)
                        event_logger.info('\nTime line Item -------------')
                        event_logger.info('Date: {0}'.format(k))
                        event_logger.info('Display Phrase: {0}'.format(txt))
                    e_txt += '{0}) {1} (from Wikipedia) <br>'.format(i + 1, txt)
                    if points[i].match:
                        prep = self.relation_index.prepositions[points[i].match[0]]
                        ent = self.relation_index.entities[points[i].match[1]]
                        e_txt += 'Matched to WikiData statement: {0} {1} {2}'.format(self.poi, prep, ent)

                    e_txt += '<br>'
                event_text['text'] = e_txt
                event['text'] = event_text
                json_file['events'].append(event)

            if ranges:
                range_groups = self.find_range_groups(ranges)
                seen = list()

                for rg in range_groups:
                    era = dict()
                    era['start_date'] = self.build_date_object(rg[0].date)
                    era['end_date'] = self.build_date_object(rg[0].date_range)

                    era_text = dict()
                    era_text['headline'] = heading

                    e_txt = ''
                    for i in range(len(rg)):
                        txt = rg[i].format_txt()
                        if rg[i].match:
                            prep = self.relation_index.prepositions[rg[i].match[0]]
                            ent = self.relation_index.entities[rg[i].match[1]]
                            match_logger.info('\nMatched item -------------------')
                            match_logger.info('Display Phrase: {0}'.format(txt))
                            match_logger.info('Matched to: {0} {1} {2} '.format(self.poi, prep, ent))
                        if txt in seen:
                            continue
                        else:
                            event_logger.info('\nTime line Item -------------')
                            event_logger.info('Date: {0} to {1}'.format(rg[0].date, rg[0].date_range))
                            event_logger.info('Display Phrase: {0}'.format(txt))
                            seen.append(txt)
                        e_txt += '{0}) {1} (from Wikipedia) <br>'.format(i + 1, txt)
                        if rg[i].match:
                            prep = self.relation_index.prepositions[rg[i].match[0]]
                            ent = self.relation_index.entities[rg[i].match[1]]
                            e_txt += 'Matched to WikiData statement: {0} {1} {2} '.format(self.poi, prep, ent)
                            match_logger.info('\nMatched item -------------------')
                            match_logger.info('Display Phrase: {0}'.format(txt))
                            match_logger.info('Matched to: {0} {1} {2} '.format(self.poi, prep, ent))
                        e_txt += '<br>'
                    era_text['text'] = e_txt
                    era['text'] = era_text
                    json_file['events'].append(era)

        with open(self.poi.replace(" ", "_") + "TL.json", 'w') as handle:
            json.dump(json_file, handle)

        with open('timeline.html') as infile, open(self.poi.replace(" ", "_") + "TL.html", 'w') as outfile:
            for line in infile:
                if '!!REPLACE_ME!!' in line:
                    line = re.sub('!!REPLACE_ME!!', self.poi.replace(" ", "_") + "TL.json", line)
                outfile.write(line)


# ----- CHUNKING -------------------------


class Chunker:
    def __init__(self):
        grammar = r'''
            R-DATE: {<IN><CD><TO><CD>}
            R-DATE: {<IN><CD><IN><CD>}
            R-DATE: {<JJ><CD><CC><CD>}
            FULL-DATE: {<IN><CD><NNP><CD>}
            FULL-DATE: <VB.*>{<CD><NNP><CD>}
            MONTH-DATE: {(<IN|DT>)?<NNP><CD>}
            NP: {<JJR><IN><CD><NNS>}
            NP: {<IN><CD><NNS>}
            NP: {<CD><IN><DT><CD><NNS>(<JJ>)?}
            DM_DATE: {<IN><CD><NNP>}(<,>|<NN.*>)
            DATE: {<IN>(<DT>)?<CD>}
            DT-DATE: {<DT><CD>}
            POS-DATE: <POS>{<CD>}
            V-DATE: {<IN|CD><JJ><CD>}
            DATE: (<,>)?{<CD>}<,>
            N-DATE: (<,>)?{((<.*DATE><,>)+)?<CD><CC><CD>}

            NN-LST: {<NN.*>(<,><NN.*>)+(<,>)?<CC><NN.*>}
            NP: {(<RP|IN|NN.*|.*DT|RB|JJ.*|RB.*|POS|``|"|''|FW|POS-DATE|CD|TO|WRB>)*<NN.*>(<TO>(<DT>)?<NN.*>)?(<RB>)?(<IN>)?(<JJ|RB|CD|DT|POS>)*}
            NP: {<P-DATE><NP>}
            NP: {<NP><NP>}
            NP: {<NP><,><NP><,>}
            CC-NP: {<NP>(<CC><NP>)+}

            PP: {((<PDT>)?<DT>)?(<RB|IN|WRB|WDT|TO|JJ|PRP>)*<PRP.*>(<MD>)?}
            PP: {<WP|WRB>}
            PP: {<IN><WDT>(<DT|RBR>)*}
            PP: <,>{<DT><JJ>}

            NP: {<NP><PP><NP>}
            P-NP: {<PP><NP>(<,><NP><,>)?}
            C-PP: {(<CD><PP>|<PP><CD>)}
            CC-P-NP: {<P-NP|PP><CC><NP>}
            NP: {<NP><,>((<,|CC>)*<.*NP>)*<,>}

            VP: {<VB.*><IN><TO><DT><VB.*>}
            VP: {<VB.*><RP>}
            VP: {(<IN|TO|VB.*|.*DT|RB|JJ|EX|MD>)*<VB.*>(<JJ>)?(<RB>(<TO|JJ|>)?)?}
            VP: {<IN><DT><VB.*>(<RB><TO>)?}
            VP: {<RB|VB.*|MD|TO>*<VB.*><RB|VB.*|MD|TO>*}
            VP: {<VP><IN>}
            VP: {<IN><VP>(<RP>)?<TO>}
            VP: {((<DT>)?<IN>)?<WDT><VP>}
            VP: {<IN><DT-DATE><VP>}
            Y-DATE: <JJ>{<CD>}
            VP: {<JJ>}<Y-DATE>
            CC-VP: {<VP><NP><CC><VP><NP>}

            CC-NP: <VP>{<NP>(<,><NP>)*<CC><NP>}
            D-NP : <VP>{<.*DATE><.*NP>}

            CLAUSE-P: <,|CC>{<VP><P-NP>}(<,>|<CC>|<.*DATE>)
            CLAUSE-NS: <,>(<CC>)?{(<VP><.*NP>)+}<,>
            CLAUSE-NS: <CC>{(<VP><.*NP>)+}
            CLAUSE: {<NP>(<VP><.*NP>|<CC-VP>)+(.*P-NP)?}
            CLAUSE-P: {<PP|P-NP>(<VP><.*NP>|<CC-VP>)+}
            CLAUSE-P: <,>{<PP|P-NP><VP>}<,>
            CLAUSE-P: <,>{<PP|P-NP><VP><CLAUSE>}
            CLAUSE: <CC>{<NP><VP><CLAUSE-P>}
            CLAUSE-NS: <,>{<VP><.*NP>}
            CLAUSE-OSL: <CLAUSE-P><CC><,>{<NP>}<,>
            CLAUSE-OSR: <,>{<NP>}<CLAUSE-P>
            CLAUSE: {<NP><CLAUSE-P>}

            D-CLAUSE-P: {<CLAUSE-P><.*DATE>}
            D-CLAUSE-P: <,>{<DATE><CLAUSE-P>}<,>
            D-CLAUSE-P: <,>{<CLAUSE-P><,><VP><.*DATE>}
            D-CLAUSE: {<CLAUSE><.*DATE>}
            D-CLAUSE: {<.*DATE><,><CLAUSE>}<,>
            CLAUSE-NS: {<VP><.*NP>}
            D-CLAUSE-NS: {<CLAUSE-NS><.*DATE>}
            D-CLAUSE-NS: {<VP><NP><.*DATE>}<,>
            D-CLAUSE-NS: <CC>{<.*DATE>(<,>)?<CLAUSE-NS>}
            D-CLAUSE-P: {<P-NP><VP><.*DATE>}


            D-CLAUSE-M-P: {<.*DATE><,><CLAUSE-P>((<,|CC>)+<CLAUSE-P>)+}
            D-CLAUSE-M: {<.*DATE><,><CLAUSE-P>(<,>(<CC>)?<CLAUSE-NS>)+}
            D-CC-CLAUSE: {<.*DATE><CLAUSE><,><CC><CLAUSE>}
            D-CLAUSE: {<.*NP><.*VP><.*DATE>}
            D-CLAUSE: <,>{<.*DATE><.*CLAUSE.*>}
            D-CLAUSE-P: {<CLAUSE-P>(<,>)?(<.*NP>)?<.*DATE>}
            D-CLAUSE-P-L: <D-CLAUSE-P>(<,|CC>)+{<NP>(<,><NP>)*<.*DATE>}
            D-CLAUSE-P: {<.*DATE><,><CLAUSE-P>}
            D-CLAUSE-NS: <.*CLAUSE.*>(<,|CC>)*{<.*DATE>(<,>)?<CLAUSE-NS>}
            DD-CLAUSE: {<D-CLAUSE.*>(<,|CC>)+(<RB>)?<.*DATE>}
            D-CLAUSE-P: {<.*DATE><CLAUSE-P>}(<,>)?
            D-CLAUSE-P: (<,>)?{<CLAUSE-P><CC><D-CLAUSE-NS>}
             '''
        self.chunker = RegexpParser(grammar, loop=1)
        self.exclude = {s for s in string.punctuation if s not in [';', ':', '&', ',', ]}
        self.exclude.add('``')
        self.exclude.add("''")

    def prepare_sentence(self, s: list) -> list:
        s = [n for n in s if n[0] not in self.exclude]
        txt = [w[0] for w in s]
        pos = nltk.pos_tag(txt)
        return [(w, ps, net) for (w, ps), (_, net) in zip(pos, s)]

    @staticmethod
    def tree_label_fix(tree: nltk.tree.Tree) -> nltk.tree.Tree:

        for st in tree:
            if isinstance(st, nltk.tree.Tree):
                if bool(re.match(r'.*CLAUSE.*', st.label())):
                    if not bool(re.match('.*D-.*CLAUSE.*', st.label())):
                        leafs = st.leaves()
                        if any([n for n in leafs if n[2] == 'DATE']):
                            # Fixing the label of the tree
                            new_lbl = 'D-' + st.label()
                            st.set_label(new_lbl)
                            st.label()
                    else:
                        leafs = st.leaves()
                        if not any([n for n in leafs if n[2] == 'DATE']):
                            oldlbl = st.label()
                            new_lbl = re.sub(r'D-', '', oldlbl)
                            st.set_label(new_lbl)
        return tree

    def generate_tree(self, s: list) -> nltk.tree.Tree:
        # noinspection PyTypeChecker
        t1 = self.chunker.parse(s)
        return self.tree_label_fix(t1)


# ---- Testing Code-----

POI = "Dom Mintoff"
startTime = datetime.now()
# ------ loggers

formatter = logging.Formatter('%(message)s')
directory = 'C:/FYP/LOGS/'+POI.replace(" ", "_") + '_LOGS'
filename = POI.replace(" ", "_")

if not os.path.exists(directory):
    os.makedirs(directory)

# Date Extraction logger
de_logger = logging.getLogger('date_extraction_logger')
hdlr_de = logging.FileHandler(directory + '/' + filename + '_date_extraction.log')
hdlr_de.setFormatter(formatter)
de_logger.addHandler(hdlr_de)
de_logger.setLevel(logging.INFO)

# structured match logger
match_logger = logging.getLogger('match_logger')
hdlr_mtch = logging.FileHandler(directory + '/' + filename + '_matches.log')
hdlr_mtch.setFormatter(formatter)
match_logger.addHandler(hdlr_mtch)
match_logger.setLevel(logging.INFO)

# multi date logger
md_logger = logging.getLogger('md_logger')
hdlr_md = logging.FileHandler(directory + '/' + filename + '_multidate.log')
hdlr_md.setFormatter(formatter)
md_logger.addHandler(hdlr_md)
md_logger.setLevel(logging.INFO)

# Event extraction logger
event_logger = logging.getLogger('event_logger')
hdlr_e = logging.FileHandler(directory + '/' + filename + '_events.log')
hdlr_e.setFormatter(formatter)
event_logger.addHandler(hdlr_e)
event_logger.setLevel(logging.INFO)


# -----------------------


TC = pickle.load(open(POI.replace(" ", "_") + "TC.p", "rb"))
eventex = EventExtractor(POI)
eventex.process_text(TC)
eventex.build_timeline()


with open('eventex.pickle', 'wb') as handlex:
    pickle.dump(eventex, handlex)

print(datetime.now() - startTime)