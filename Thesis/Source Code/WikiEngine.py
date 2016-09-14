import os
import pickle
import re
from pprint import pprint

import wikipedia as wiki
from bs4 import BeautifulSoup
from nltk.tag.stanford import StanfordNERTagger
from nltk.tokenize import word_tokenize
from unidecode import unidecode
from datetime import datetime

from indexers import TextCollection, TextGroup

# Path to java
jpath2 = 'C:/Program Files (x86)/Java/jre1.8.0_73/bin'
# Setting Java environment
os.environ['JAVAHOME'] = jpath2

# initializing stanford NER
st = StanfordNERTagger('C:\stanford-ner-2014-06-16\classifiers\english.muc.7class.distsim.crf.ser.gz',
                       'C:\stanford-ner-2014-06-16\stanford-ner.jar', encoding='UTF-8')


def clean(in_txt: str) -> str:
    in_txt = re.sub("/.*/; ", "", in_txt)
    in_txt = re.sub("–", "-", in_txt)
    in_txt = re.sub(r"\\", "", in_txt)
    in_txt = re.sub("Â\xa0", " ", in_txt)
    in_txt = unidecode(in_txt)
    indices = [m.start() for m in re.finditer('(\d{4}(-|/)\d{2})', in_txt)]
    for i in reversed(indices):
        in_txt = in_txt[0:(i + 4)] + " to " + in_txt[i:i + 2] + in_txt[i + 5:]

    indices = [m.start() for m in re.finditer(r'\d{4}(-|/)\d{4}', in_txt)]
    for i in reversed(indices):
        in_txt = in_txt[:i + 4] + ' to ' + in_txt[i + 5:]

    out_txt = ''
    bo = False
    for c in in_txt:
        if c == '(':
            bo = True
        if c == ')':
            bo = False
            continue
        if not bo:
            out_txt += c

    return out_txt.strip()


# function to strip out the paragraph text for a subsection
def get_text(link: str, my_soup: BeautifulSoup) -> tuple:
    """
    :param my_soup: beautifulSoup obj containing html document
    :param link: link to heading in html document
    :rtype: list or empty list
    """
    new_content = list()
    html_text = my_soup.find("span", id=link)

    if bool(html_text):
        html_text = html_text.find_parent().find_next_sibling()

        while html_text.name[0] != 'h':
            if html_text.name == "p":
                txt = re.sub(r'\[([^]]*)\](:\d+)?', "", html_text.text)
                txt = clean(txt)
                new_content.append(txt)
            html_text = html_text.find_next_sibling()

    return new_content


def get_summary_pars(summary: str)->list:
    iters = re.finditer('\n', summary)
    pars = [TextGroup('Head-Summary', 'Summary')]
    all_txt = 'Summary '
    s_pos = 0
    for i in iters:
        e_pos = i.span()[0]
        p = clean(summary[s_pos: e_pos])
        all_txt += p + ' '
        pars.append(TextGroup('paragraph', p))
        s_pos = i.span()[1]
    p = clean(summary[s_pos:])
    all_txt += p
    pars.append(TextGroup('paragraph', p))
    return pars, all_txt


def level_pop(lvls: list, fragments: list):
    raw_str = ''
    ret_list = list()
    lvl = lvls[0]
    nxt_lvl = None
    if len(lvls) > 1:
        nxt_lvl = lvls[1]

    for f in fragments:
        head = f.find("span", {"class": "toctext"}).text

        # Skipping useless and external links
        skip = ['references', 'external links', 'See also', 'Notes', 'Further reading', 'Bibliography', 'Books',
                'Tributes', 'Writings']
        if any(x.lower() in head.lower() for x in skip):
            continue
        # Cleaning the header text and processing it
        head = clean(head)
        raw_str += head + ' '
        ret_list.append(TextGroup('Head-{0}'.format(lvl), head))

        # Checking for any text under the header and processing it
        link = f.find("a", href=True)["href"][1:]
        content = get_text(link, soup)
        if content:
            for c in content:
                ret_list.append(TextGroup('paragraph', c))
                raw_str += c + ' '

        if nxt_lvl:
            sub_lst = f.find_all("li", {"class": "toclevel-{0}".format(nxt_lvl)})
            t_list, t_raw = level_pop(lvls[1:], sub_lst)
            ret_list += t_list
            raw_str += t_raw

    return ret_list, raw_str


POI = "Enoch Powell"
startTime = datetime.now()
# Getting the wikipedia page obj
page = wiki.page(POI)
# getting the html for the page
html = page.html()
# loading the html into a beautifulSoup obj
soup = BeautifulSoup(html, "lxml")

print('Processing Text')

# Processing and extracting relevant text
sections_html = soup.find_all("div", id="toc")[0]
li = sections_html.find_all('li')
section_ids = {int(li[i]['class'][0][len(li[i]['class'][0]) - 1]) for i in range(len(li))}
lvl_ids = sorted(list(section_ids))
t1 = 'toclevel-' + str(lvl_ids[0])
l1 = sections_html.find_all('li', {'class': t1})
tgs, raw = level_pop(lvl_ids, l1)
stags, sraw = get_summary_pars(page.summary)
tgs = stags + tgs
raw = sraw + ' ' + raw
TC = TextCollection(tgs, raw)

# Tagging the text and updating the structured text
print('Tagging Text')
ner = st.tag(word_tokenize(raw))
print('Updating Structure')
TC.update_ner(ner)
pickle.dump(TC, open(POI.replace(" ", "_")+"TC.p", "wb"))
print('Data Dumped')

# test display
pprint(TC)

print(datetime.now() - startTime)