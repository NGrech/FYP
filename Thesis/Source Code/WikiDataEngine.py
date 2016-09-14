import json
import os
import pickle
import sys

from datetime import datetime

from WikiData import WikiData
from indexers import RelationCollection
from indexers import TimeIndex

# POI to test with
person = 'Nelson Mandela'


startTime = datetime.now()


SkipList = ['P1412', 'P910', 'P103', 'P155', 'P31', 'P27', 'P21', 'P1477', 'P856', 'P735']
DataTypeSkip = ['commonsMedia', 'external-id', 'string']

# Testing Var
coldStart = True


def get_time(time_str: str, precision: int) -> tuple:
    month = 0
    day = 0

    if precision <= 9:
        year = int(time_str[1:5])
        time = (year, month, day)
        return time
    elif precision == 10:
        year = int(time_str[1:5])
        month = int(time_str[6:8])
        time = (year, month, day)
        return time
    elif precision >= 11:
        year = int(time_str[1:5])
        month = int(time_str[6:8])
        day = int(time_str[9:11])
        time = (year, month, day)
        return time


def create_json_timeline(ti: TimeIndex, rc: RelationCollection) -> dict:
    json_file = dict()

    # Creating the title card
    json_file['title'] = dict()
    json_file['title']['text'] = dict()
    if ti.birth:
        birth = "{0}/{1}/{2}".format(ti.birth[2], ti.birth[1], ti.birth[0])
    else:
        birth = "????"
    if ti.death:
        death = "{0}/{1}/{2}".format(ti.death[2], ti.death[1], ti.death[0])
    else:
        death = 'Present'
    json_file['title']['text']['headline'] = person + '<br/>' + birth + "-" + death
    json_file['title']['text']['text'] = "A timeline for {0} generated with data from WikiData".format(person)

    # Creating the events
    json_file['events'] = list()

    for e in ti.point.keys():
        for rel in ti.point[e]:
            x = dict()

            # Assign Date point
            x['start_date'] = dict()
            x['start_date']['year'] = e[0]
            if e[1] > 0:
                x['start_date']['month'] = e[1]
            if e[2] > 0:
                x['start_date']['day'] = e[2]

            # Assign Text
            if 'P570' in rel[0]:
                txt = 'Died'
            elif 'P569' in rel:
                txt = 'Born'
            else:
                prep = rc.prepositions[rel[0]]
                obj = rc.entities[rel[1]]
                rel_obj = rc.relations[rel]
                txt = "<p>Relation discovered: {0} -> {1} from {2} </p> </br>".format(prep, obj, rel_obj.source)

                # Adding Qualifiers to text
                if rel_obj.sub:
                    sub_text = "Relation Qualifiers: </br>"
                    for s in rel_obj.sub:
                        p = rc.prepositions[s[0]]
                        o = rc.entities[s[1]]
                        s = s[2]
                        sub_text += "{0} -> {1} from {2} </br>".format(p, o, s)
                    txt += "<p>" + sub_text + "</p>"
            x['text'] = dict()
            x['text']['text'] = txt
            # Add x to timeline
            json_file['events'].append(x)

    for s in ti.range_start.keys():
        for e in ti.range_start[s].keys():
            for rel in ti.range_start[s][e]:
                x = dict()

                # Assign Start point
                x['start_date'] = dict()
                x['start_date']['year'] = s[0]
                if s[1] > 0:
                    x['start_date']['month'] = s[1]
                if s[2] > 0:
                    x['start_date']['day'] = s[2]

                # Assign Endpoint
                x['end_date'] = dict()
                x['end_date']['year'] = e[0]
                if s[1] > 0:
                    x['end_date']['month'] = e[1]
                if s[2] > 0:
                    x['end_date']['day'] = e[2]

                # Assign Text
                if 'P570' in rel[0]:
                    txt = 'Died'
                elif 'P569' in rel:
                    txt = 'Born'
                else:
                    prep = rc.prepositions[rel[0]]
                    obj = rc.entities[rel[1]]
                    rel_obj = rc.relations[rel]
                    txt = "<p>Relation discovered: {0} -> {1} from {2} </p> </br>".format(prep, obj, rel_obj.source)
                    if rel_obj.sub:
                        sub_text = "Relation Qualifiers: </br>"
                        for sub in rel_obj.sub:
                            p = rc.prepositions[sub[0]]
                            o = rc.entities[sub[1]]
                            src = sub[2]
                            sub_text += "{0} -> {1} from {2} </br>".format(p, o, src)
                        txt += "<p>" + sub_text + "</p>"
                x['text'] = dict()
                x['text']['text'] = txt

                # Add x to timeline
                json_file['events'].append(x)
    return json_file

# Deceleration of file names for current person
ti_file = person.replace(" ", "_") + "timeIndex.pickle"
ri_file = person.replace(" ", "_") + "relationIndex.pickle"
wd_file = person.replace(" ", "_") + "WikiData.pickle"

# Initializing Indexes and data
timeIndex = None
relationIndex = None
wiki = None

if os.path.isfile(ti_file) and os.path.isfile(wd_file) and os.path.isfile(ri_file) and not coldStart:
    with open(ti_file, 'rb') as handle:
        timeIndex = pickle.load(handle)
    with open(wd_file, 'rb') as handle:
        wiki = pickle.load(handle)
    with open(ri_file, 'rb') as handle:
        relationIndex = pickle.load(handle)
else:
    timeIndex = TimeIndex()
    relationIndex = RelationCollection(person)
    wiki = WikiData(person)

    # looping through all relations
    while wiki.claims:
        claim = wiki.claims.popitem()
        if claim[0] not in SkipList:
            for item in claim[1]:
                if item['mainsnak']['datatype'] not in DataTypeSkip:

                    # Creating basic relation
                    prop_id = item['mainsnak']['property']

                    if prop_id == 'P570':

                        tim_str = item['mainsnak']['datavalue']['value']['time']
                        prec = item['mainsnak']['datavalue']['value']['precision']
                        date = get_time(tim_str, prec)
                        timeIndex.add_death(date[0], date[1], date[2])
                        timeIndex.add_point((prop_id, 'DEATH'), date[0], date[1], date[2])
                        relationIndex.entities['DEATH'] = 'died'
                        relationIndex.prepositions['P570'] = 'death'

                    elif prop_id == 'P569':

                        tim_str = item['mainsnak']['datavalue']['value']['time']
                        precision = item['mainsnak']['datavalue']['value']['precision']
                        date = get_time(tim_str, precision)
                        timeIndex.add_birth(date[0], date[1], date[2])
                        timeIndex.add_point((prop_id, 'BIRTH'), date[0], date[1], date[2])
                        relationIndex.entities['BIRTH'] = 'bourn'
                        relationIndex.prepositions['P569'] = 'birth'

                    elif 'numeric-id' in item['mainsnak']['datavalue']['value']:

                        entity_id = 'Q' + str(item['mainsnak']['datavalue']['value']['numeric-id'])
                        relationIndex.add_relation(prop_id, entity_id, 'WikiData')

                        # Looking for time components
                        if 'qualifiers-order' in item:
                            # checking for a point in time
                            if 'P585' in item['qualifiers-order']:
                                time_qual = item['qualifiers'].pop('P585')
                                item['qualifiers-order'].remove('P585')
                                time_string = time_qual[0]['datavalue']['value']['time']
                                prec = time_qual[0]['datavalue']['value']['precision']
                                date = get_time(time_string, int(prec))
                                timeIndex.add_point((prop_id, entity_id), date[0], date[1], date[2])
                                relationIndex.update_time((prop_id, entity_id), date, prec)

                            # Checking for start of range
                            if 'P580' in item['qualifiers-order']:
                                start_qual = item['qualifiers'].pop('P580')
                                item['qualifiers-order'].remove('P580')
                                start_time_str = start_qual[0]['datavalue']['value']['time']
                                start_precision = start_qual[0]['datavalue']['value']['precision']
                                start_date = get_time(start_time_str, int(start_precision))

                                # Checking for end of range
                                if 'P582' in item['qualifiers-order']:
                                    try:
                                        end_qual = item['qualifiers'].pop('P582')
                                        item['qualifiers-order'].remove('P582')
                                        end_time_str = end_qual[0]['datavalue']['value']['time']
                                        end_precision = end_qual[0]['datavalue']['value']['precision']
                                        end_date = get_time(end_time_str, int(end_precision))

                                        # Adding the range to the index
                                        timeIndex.add_rage((prop_id, entity_id), start_date[0], end_date[0], start_date[1],
                                                           end_date[1], start_date[2], end_date[2])
                                        relationIndex.update_time((prop_id, entity_id), start_date, start_precision, end_date)
                                    except:
                                        print(item)
                                        print("Unexpected error:", sys.exc_info()[0])
                                else:
                                    timeIndex.add_point((prop_id, entity_id), start_date[0], start_date[1], start_date[2])
                                    relationIndex.update_time((prop_id, entity_id), start_date, start_precision)

                            # Looping thorough any remaining qualifiers
                            for sub in item['qualifiers-order']:
                                for qual in item['qualifiers'][sub]:
                                    if qual['datavalue']['type'] == 'wikibase-entityid':
                                        q_prop = qual['property']
                                        q_entity = 'Q' + str(qual['datavalue']['value']['numeric-id'])
                                        relationIndex.update_sub_relation((prop_id, entity_id),
                                                                          (q_prop, q_entity), 'WikiData')


# saving time index
with open(ti_file, 'wb') as handle:
    pickle.dump(timeIndex, handle)

# saving relational index
with open(ri_file, 'wb') as handle:
    pickle.dump(relationIndex, handle)

# saving WikiData
with open(wd_file, 'wb') as handle:
    pickle.dump(wiki, handle)

# Creating the Timeline
timeline = create_json_timeline(timeIndex, relationIndex)

# Saving the Timeline
file = person.replace(" ", "_") + "_t1.json"
with open(file, 'w') as outfile:
    json.dump(timeline, outfile)

# Pickling the discovered properties
with open('propLabels.pickle', 'wb') as handle:
    pickle.dump(relationIndex.prepositions, handle)


print(datetime.now() - startTime)