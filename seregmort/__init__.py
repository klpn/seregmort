import requests
import json
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import cartopy.io.shapereader as shpreader
import cartopy.crs as ccrs
import statsmodels.api as sm
import pandas as pd
from pyjstat import pyjstat
from collections import OrderedDict
from sqlalchemy import create_engine

mpl.rcParams['axes.formatter.use_locale'] = True
mpl.style.use('ggplot')
morturl = 'http://api.scb.se/OV0104/v1/doris/sv/ssd/START/HS/HS0301/DodaOrsak'
popurl = 'http://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy'
g_units = pd.read_csv('naddata/g_units_names.csv', index_col = 'ref')

def scb_to_unit(scb):
    """Convert codes used by Statistics Sweden to units used by the NAD GIS files."""
    scbform = 'SE/' + '{:0<9}'.format(scb)
    if scbform in g_units.index:
        return g_units.loc[scbform, 'G_unit']
    else:
        return 0

def metadata(url):
    """Fetch JSON metadata from url."""
    req = requests.get(url)
    return json.loads(req.content.decode('utf-8'), object_pairs_hook = OrderedDict)

def svreg_engine(dbfile):
    return create_engine('sqlite:///' + dbfile) 

def save_frame(ndeaths, dbfile):
    """Save a dataframe into a SQLite database."""
    engine = svreg_engine(dbfile)
    ndeaths['frame'].to_sql('regdeaths', engine, if_exists = 'append')

def save_dimension(ndeaths, filename):
    """Save returned metadata into a JSON file."""
    with open(filename, 'w') as f:
        json.dump(ndeaths['dimension'], f, ensure_ascii=False)

def is_county(region):
    return len(region) == 2 and region != '00'

def is_municipality(region):
    return len(region) == 4

def allages(ageformat = 'mort'):
    """Returns the age groups used by Statistics Sweden."""
    if ageformat == 'mort':
        startint = '0'
        startages = [1] + list(range(5, 90, 5))
        endages = [4] + list(range(9, 94, 5))
        endint = '90+'
    elif ageformat == 'pop':
        startint = '-4'
        startages = list(range(5, 100, 5))
        endages = list(range(9, 104, 5))
        endint = '100+'
    midints = ['{0}-{1}'.format(s, e) for s, e in zip(startages, endages)]
    return [startint] + midints + [endint]

def ageintmerge():
    return pd.DataFrame({'mortAlder': allages() + [allages()[-1]]*2, 
        'Alder': [allages('pop')[0]] + allages('pop')})

def agesplitter(age):
    if '-' in age:
        return age.split('-')
    else:
        return [age]

def ageslice(startage, endage):
    ages = allages()
    startind = ages.index(startage)
    endind = ages.index(endage)
    if startage == endage:
        alias = startage.replace('-', '\u2013')
    else:
        alias = agesplitter(startage)[0] + '\u2013' + agesplitter(endage)[-1]
    agelist = ages[startind:endind+1]
    return {'agelist': agelist, 'alias': alias}

def causealias(cause, dim):
    if cause == 'POP':
        return dim['ContentsCode']['category']['label']['BE0101N1']
    else:
        return dim['Dodsorsak']['category']['label'][cause]

def allregions(level, metadict):
    """Return all regions at county or municipality level."""
    regvalues = metadict['variables'][0]['values']
    if level == 'county':
        return list(filter(is_county, regvalues))
    elif level == 'municipality':
        return list(filter(is_municipality, regvalues))

def munis_incounty(county, metadict):
    """Return all municipalities in the county given."""
    regvalues = metadict['variables'][0]['values']
    return [region for region in regvalues
            if is_municipality(region) and region.startswith(county)]

def yearrange(start = 1969, end = 1996):
    return [str(year) for year in range(start, end+1)]

def mortreqjson(regvalues, causevalues, agevalues = allages(), 
        sexvalues = ['1', '2'], yearvalues = yearrange()):
    """Prepare a JSON request to return number of deaths."""

    if '-' in causevalues[0]:
        causefilter = 'agg:DödsorsakKapitel'
    else:
        causefilter = 'item'

    if is_county(regvalues[0]):
        regfilter = 'vs:RegionLän'
    elif is_municipality(regvalues[0]):
        regfilter = 'vs:RegionKommun95'
    
    return {'response': {'format': 'json-stat'}, 
            'query': [{'selection': {'filter': regfilter, 'values': regvalues}, 
                'code': 'Region'},
                {'selection': {'filter': causefilter, 'values': causevalues},  
                    'code': 'Dodsorsak'},
                {'selection': {'filter': 'item', 'values': agevalues},  'code': 'Alder'},
                {'selection': {'filter': 'item', 'values': sexvalues},  'code': 'Kon'},
                {'selection': {'filter': 'item', 'values': yearvalues},  'code': 'Tid'}]}

def popreqjson(regvalues, agevalues = allages('pop'), 
        sexvalues = ['1', '2'], yearvalues = yearrange()):
    """Prepare a JSON request to return population size."""
    
    if is_county(regvalues[0]):
        regfilter = 'vs:RegionLän07'
    elif is_municipality(regvalues[0]):
        regfilter = 'vs:RegionKommun07'

    return {'response': {'format': 'json-stat'}, 
            'query': [{'selection': {'filter': regfilter, 'values': regvalues}, 
                'code': 'Region'},
                {'selection': {'filter': 'agg:Ålder5år', 'values': agevalues},  'code': 'Alder'},
                {'selection': {'filter': 'item', 'values': sexvalues},  'code': 'Kon'},
                {'selection': {'filter': 'item', 'values': ['BE0101N1']},  'code': 'ContentsCode'},
                {'selection': {'filter': 'item', 'values': yearvalues},  'code': 'Tid'}]}

            
def ndeaths(regvalues, causevalues, agevalues = allages(), 
        sexvalues = ['1', '2'], yearvalues = yearrange()):
    """Send a JSON request to return number of deaths."""
    qjson = mortreqjson(regvalues, causevalues, agevalues, sexvalues, yearvalues)
    req = requests.post(morturl, json = qjson)
    req.raise_for_status()
    respstr = req.content.decode('utf-8')
    respjson = json.loads(respstr, object_pairs_hook = OrderedDict)
    return {'dimension': respjson['dataset']['dimension'], 
            'frame': pyjstat.from_json_stat(respjson, naming = 'id')[0]}

def npop(regvalues, agevalues = allages('pop'),
        sexvalues = ['1', '2'], yearvalues = yearrange()):
    """Send a JSON request to return population size."""
    qjson = popreqjson(regvalues, agevalues, sexvalues, yearvalues)
    req = requests.post(popurl, json = qjson)
    req.raise_for_status()
    respstr = req.content.decode('utf-8')
    respjson = json.loads(respstr, object_pairs_hook = OrderedDict)
    popframe = pyjstat.from_json_stat(respjson, naming = 'id')[0]
    popmerged = pd.merge(ageintmerge(), popframe, on = 'Alder')
    return {'dimension': respjson['dataset']['dimension'], 
            'frame': popmerged}

def smoother(col, index):
    """Smooth time trends."""
    return sm.nonparametric.lowess(col, index, frac = 0.4)

def propplotyrs(numframe, denomframe, numdim, denomdim, numcause, denomcause, 
        region, startage, endage, years = yearrange(), sexes = ['2', '1']):
    """Plot a time trend for the number of deaths of one cause relative to another."""
    plt.close()
    numcausealias = causealias(numcause, numdim)
    denomcausealias = causealias(denomcause, denomdim)
    regalias = numdim['Region']['category']['label'][region].replace(region, '').lstrip()
    ages = ageslice(startage, endage)
    agealias = ages['alias']
    agelist = ages['agelist']
    yrints = list(map(int, years))
    for sex in sexes:
        sexalias = numdim['Kon']['category']['label'][sex]
        numframe_sub = numframe[(numframe.Kon == sex) & (numframe.Dodsorsak == numcause)
                & (numframe.Region == region) & (numframe.Alder.isin(agelist)) 
                & (numframe.Tid.isin(years))].groupby(['Tid'])
        if denomcause == 'POP':
            denomframe_sub = denomframe[(denomframe.Kon == sex) & 
                    (denomframe.Region == region) & (denomframe.Alder.isin(agelist))
                    & (denomframe.Tid.isin(years))].groupby(['Tid'])
        else:
            denomframe_sub = denomframe[(denomframe.Kon == sex) & 
                    (denomframe.Dodsorsak == denomcause) & 
                    (denomframe.Region == region) & (denomframe.Alder.isin(agelist))
                    & (denomframe.Tid.isin(years))].groupby(['Tid'])
        prop = numframe_sub.value.sum() / denomframe_sub.value.sum()
        plt.plot(yrints, prop, label = sexalias)
        sex_smo = smoother(prop, yrints)
        plt.plot(sex_smo[:, 0], sex_smo[:, 1], label = sexalias + ' jämnad')
    plt.legend(framealpha = 0.5)
    plt.xlim(yrints[0], yrints[-1])
    plt.ylim(ymin = 0)
    plt.title('Döda {numcausealias}/{denomcausealias}\n{agealias} {regalias}'
            .format(**locals()))

def prop_reggrp(numframe, numcause, denomframe, denomcause, sex, agelist):
    numframe_sub = numframe[(numframe.Kon == sex) & 
            (numframe.Dodsorsak == numcause) 
            & (numframe.Alder.isin(agelist))].groupby(['Region'])
    if denomcause == 'POP':
        denomframe_sub = denomframe[(denomframe.Kon == sex) & 
            (denomframe.Alder.isin(agelist))].groupby(['Region'])
    else:
        denomframe_sub = denomframe[(denomframe.Kon == sex) & 
            (denomframe.Dodsorsak == denomcause) & 
            (denomframe.Alder.isin(agelist))].groupby(['Region'])
    
    return {'prop': numframe_sub.value.sum() / denomframe_sub.value.sum(),
            'regvalues': list(numframe_sub.Region.all())}

def propscatsexes(numframe, denomframe, numdim, denomdim, numcause, denomcause, 
        startage, endage, **kwargs):
    """Plot the number of deaths of one cause relative to another for females vs males."""
    plt.close()
    numcausealias = causealias(numcause, numdim)
    denomcausealias = causealias(denomcause, denomdim)
    ages = ageslice(startage, endage)
    agealias = ages['alias']
    agelist = ages['agelist']
    startyear = min(numframe.Tid)
    endyear = max(numframe.Tid)
    sexframes = dict()
    for sex in ['2', '1']:
        sexframes[sex] = dict()
        sexframes[sex]['alias'] = numdim['Kon']['category']['label'][sex]
        propdict = prop_reggrp(numframe, numcause, denomframe, denomcause, sex, agelist)
        sexframes[sex]['prop'] = propdict['prop'] 
        sexframes[sex]['regvalues'] = propdict['regvalues']
    plt.scatter(sexframes['2']['prop'], sexframes['1']['prop'])
    for i, code in enumerate(sexframes['2']['regvalues']):
        plt.annotate(code, (sexframes['2']['prop'][i], sexframes['1']['prop'][i]))
    plt.xlabel(sexframes['2']['alias'])
    plt.ylabel(sexframes['1']['alias'])
    plt.title('Döda {numcausealias}/{denomcausealias}\n'
    '{agealias} {startyear}\u2013{endyear}'.format(**locals()))

def perc_round(value):
    return str(np.round(value, 4)).replace('.', ',')
        
def propmap(numframe, denomframe, numdim, denomdim, numcause, denomcause,
        startage, endage, sex, shapefname):
    """Draw a map with percentiles of deaths of one cause relative to another."""
    plt.close()
    ages = ageslice(startage, endage)
    agealias = ages['alias']
    agelist = ages['agelist']
    sexalias = numdim['Kon']['category']['label'][sex]
    numcausealias = causealias(numcause, numdim)
    denomcausealias = causealias(denomcause, denomdim)
    startyear = min(numframe.Tid)
    endyear = max(numframe.Tid)
    region_shp = shpreader.Reader(shapefname)
    propdict = prop_reggrp(numframe, numcause, denomframe, denomcause, sex, agelist)
    prop = propdict['prop']
    regvalues = propdict['regvalues']
    units = list(map(scb_to_unit, regvalues))
    regdict = dict(zip(units, regvalues))
    percentiles = [{'col': 'lightsalmon', 'value': np.nanpercentile(prop, 1/3*100)},
            {'col': 'tomato', 'value': np.nanpercentile(prop, 2/3*100)},
            {'col': 'red', 'value': np.nanpercentile(prop, 100)}]

    ax = plt.axes(projection = ccrs.TransverseMercator())

    boundlist = []
    for region_rec in region_shp.records():
        regcode = region_rec.attributes['G_UNIT']
        regend = region_rec.attributes['GET_END_YE']
        if (regcode in regdict.keys() and regend > 1995):
            i = regvalues.index(regdict[regcode])
            boundlist.append(region_rec.bounds)
            for percentile in percentiles:
                if prop[i] <= percentile['value']:
                    facecolor = percentile['col']
                    break
            ax.add_geometries([region_rec.geometry],  ccrs.TransverseMercator(),
                edgecolor = 'black', facecolor = facecolor)

    xmin = min([bound[0] for bound in boundlist])
    xmax = max([bound[2] for bound in boundlist])
    ymin = min([bound[1] for bound in boundlist])
    ymax = max([bound[3] for bound in boundlist])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    percpatches = []
    perclabels = []
    for i, percentile in enumerate(percentiles):
        percpatch = mpatches.Rectangle((0, 0), 1, 1, 
                facecolor = percentile['col'])
        percpatches.append(percpatch)
        if i == 0:
            perclabel = str('\u2265' + perc_round(min(prop)) + 
                    '\n\u2264' + perc_round(percentile['value']))
        else:
            perclabel = '\u2264' + perc_round(percentile['value'])
        perclabels.append(perclabel)
    plt.legend(percpatches, perclabels, loc = 'lower left', framealpha = 0.75)
    plt.title('Döda {numcausealias}/{denomcausealias}\n'
    '{sexalias} {agealias} {startyear}\u2013{endyear}'.format(**locals()))

    plt.show()

def catot_yrsdict(region, cause):
    """Return a dictionary for deaths due to a cause and all deaths over time."""
    cadeaths = ndeaths([region], [cause])
    totdeaths = ndeaths([region], ['TOT'])
    return {'numframe': cadeaths['frame'], 'denomframe': totdeaths['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': totdeaths['dimension'],
            'numcause': cause, 'denomcause': 'TOT', 'region': region}

def capop_yrsdict(region, cause):
    """Return a dictionary for deaths due to a cause and population over time."""
    cadeaths = ndeaths([region], [cause])
    pop = npop([region])
    return {'numframe': cadeaths['frame'], 'denomframe': pop['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': pop['dimension'],
            'numcause': cause, 'denomcause': 'POP', 'region': region}

def catot_mapdict(regvalues, cause, startyear, endyear, 
        shapefname = 'naddata/2504/__pgsql2shp2504_tmp_table.shp'):
    """Return a dictionary for deaths due to a cause and all deaths for a set of regions."""
    cadeaths = ndeaths(regvalues, [cause], yearvalues = yearrange(startyear, endyear))
    totdeaths = ndeaths(regvalues, ['TOT'], yearvalues = yearrange(startyear, endyear))
    return {'numframe': cadeaths['frame'], 'denomframe': totdeaths['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': totdeaths['dimension'],
            'numcause': cause, 'denomcause': 'TOT', 'shapefname': shapefname}

def capop_mapdict(regvalues, cause, startyear, endyear, 
        shapefname = 'naddata/2504/__pgsql2shp2504_tmp_table.shp'):
    """Return a dictionary for deaths due to a cause and population for a set of regions."""
    cadeaths = ndeaths(regvalues, [cause], yearvalues = yearrange(startyear, endyear))
    pop = npop(regvalues, yearvalues = yearrange(startyear, endyear))
    return {'numframe': cadeaths['frame'], 'denomframe': pop['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': pop['dimension'],
            'numcause': cause, 'denomcause': 'POP', 'shapefname': shapefname}

def reglabels(pardict):
    """Return region labels."""
    return pardict['numdim']['Region']['category']['label']
