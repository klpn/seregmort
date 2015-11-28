import requests
import json
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import cartopy.io.shapereader as shpreader
import cartopy.crs as ccrs
import statsmodels.api as sm
from pyjstat import pyjstat
from collections import OrderedDict
from sqlalchemy import create_engine

mpl.rcParams['axes.formatter.use_locale'] = True
mpl.style.use('ggplot')
morturl = 'http://api.scb.se/OV0104/v1/doris/sv/ssd/START/HS/HS0301/DodaOrsak'

def metadata(url):
    req = requests.get(url)
    return json.loads(req.content.decode('utf-8'), object_pairs_hook = OrderedDict)

def svreg_engine(dbfile):
    return create_engine('sqlite:///' + dbfile) 

def save_frame(ndeaths, dbfile):
    engine = svreg_engine(dbfile)
    ndeaths['frame'].to_sql('regdeaths', engine, if_exists = 'append')

def save_dimension(ndeaths, filename):
    with open(filename, 'w') as f:
        json.dump(ndeaths['dimension'], f, ensure_ascii=False)

def is_county(region):
    return len(region) == 2 and region != '00'

def is_municipality(region):
    return len(region) == 4

def allages():
    startages = [1] + list(range(5, 90, 5))
    endages = [4] + list(range(9, 94, 5))
    ageints = ['{0}-{1}'.format(s, e) for s, e in zip(startages, endages)]
    return ['0'] + ageints + ['90+']

def allregions(level, metadict):
    regvalues = metadict['variables'][0]['values']
    if level == 'county':
        return list(filter(is_county, regvalues))
    elif level == 'municipality':
        return list(filter(is_municipality, regvalues))

def munis_incounty(county, metadict):
    regvalues = metadict['variables'][0]['values']
    return [region for region in regvalues
            if is_municipality(region) and region.startswith(county)]

def yearrange(start = 1969, end = 1996):
    return [str(year) for year in range(start, end+1)]

def mortreqjson(regvalues, causevalues, agevalues = allages(), 
        sexvalues = ['1', '2'], yearvalues = yearrange()):

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

def ndeaths(regvalues, causevalues, agevalues = allages(), 
        sexvalues = ['1', '2'], yearvalues = yearrange()):
    qjson = mortreqjson(regvalues, causevalues, agevalues, sexvalues, yearvalues)
    req = requests.post(morturl, json = qjson)
    req.raise_for_status()
    respstr = req.content.decode('utf-8')
    respjson = json.loads(respstr, object_pairs_hook = OrderedDict)
    return {'dimension': respjson['dataset']['dimension'], 
            'frame': pyjstat.from_json_stat(respjson, naming = 'id')[0]}

def smoother(frame, col):
    return sm.nonparametric.lowess(frame[col], frame.index, frac = 0.4)

def propplotyrs(numframe, denomframe, numdim, denomdim, numcause, denomcause, 
        region, age, years = yearrange(), sexes = ['2', '1']):
    plt.close()
    numcausealias = numdim['Dodsorsak']['category']['label'][numcause]
    denomcausealias = denomdim['Dodsorsak']['category']['label'][denomcause]
    regalias = numdim['Region']['category']['label'][region].replace(region, '').lstrip()
    agealias = age.replace('-', '\u2013')
    for sex in sexes:
        sexalias = numdim['Kon']['category']['label'][sex]
        numframe_sub = numframe[(numframe.Kon == sex) & (numframe.Dodsorsak == numcause)
                & (numframe.Region == region) & (numframe.Alder == age) 
                & (numframe.Tid.isin(years))].copy()
        denomframe_sub = denomframe[(denomframe.Kon == sex) & 
                (denomframe.Dodsorsak == denomcause) & 
                (denomframe.Region == region) & (denomframe.Alder == age)
                & (denomframe.Tid.isin(years))].copy()
        numframe_sub['prop'] = numframe_sub.value / denomframe_sub.value
        numframe_sub['Tid'] = numframe_sub['Tid'].astype(int).copy()
        numframe_sub = numframe_sub.set_index('Tid').copy()
        numframe_sub['prop'].plot(label = sexalias)
        sex_smo = smoother(numframe_sub, 'prop')
        plt.plot(sex_smo[:, 0], sex_smo[:, 1], label = sexalias + ' jämnad')
    plt.legend(framealpha = 0.5)
    plt.ylim(ymin = 0)
    plt.title('Döda {numcausealias}/{denomcausealias}\n{agealias} {regalias}'
            .format(**locals()))

def propscatsexes(numframe, denomframe, numdim, denomdim, numcause, denomcause, 
        age):
    plt.close()
    numcausealias = numdim['Dodsorsak']['category']['label'][numcause]
    denomcausealias = denomdim['Dodsorsak']['category']['label'][denomcause]
    agealias = age.replace('-', '\u2013')
    startyear = min(numframe.Tid)
    endyear = max(numframe.Tid)
    sexframes = dict()
    for sex in ['2', '1']:
        sexframes[sex] = dict()
        sexframes[sex]['alias'] = numdim['Kon']['category']['label'][sex]
        numframe_sub =  numframe[(numframe.Kon == sex) & 
                (numframe.Dodsorsak == numcause) 
                & (numframe.Alder == age)].groupby(['Region'])
        denomframe_sub =  denomframe[(denomframe.Kon == sex) & 
                (denomframe.Dodsorsak == denomcause) & 
                (denomframe.Alder == age)].groupby(['Region'])
        sexframes[sex]['prop'] = numframe_sub.value.sum() / denomframe_sub.value.sum()
        sexframes[sex]['regvalues'] = numframe_sub.Region.all()
    plt.scatter(sexframes['2']['prop'], sexframes['1']['prop'])
    for i, code in enumerate(sexframes['2']['regvalues']):
        plt.annotate(code, (sexframes['2']['prop'][i], sexframes['1']['prop'][i]))
    plt.xlabel(sexframes['2']['alias'])
    plt.ylabel(sexframes['1']['alias'])
    plt.title('Döda {numcausealias}/{denomcausealias}\n'
    '{agealias} {startyear}\u2013{endyear}'.format(**locals()))

def propmap(numframe, denomframe, numdim, denomdim, numcause, denomcause,
        age, sex, shapefname):
    plt.close()
    numcausealias = numdim['Dodsorsak']['category']['label'][numcause]
    denomcausealias = denomdim['Dodsorsak']['category']['label'][denomcause]
    agealias = age.replace('-', '\u2013')
    sexalias = numdim['Kon']['category']['label'][sex]
    startyear = min(numframe.Tid)
    endyear = max(numframe.Tid)
    region_shp = shpreader.Reader(shapefname)
    numframe_sub =  numframe[(numframe.Kon == sex) & 
            (numframe.Dodsorsak == numcause) 
            & (numframe.Alder == age)].groupby(['Region'])
    denomframe_sub =  denomframe[(denomframe.Kon == sex) & 
            (denomframe.Dodsorsak == denomcause) & 
            (denomframe.Alder == age)].groupby(['Region'])
    prop = numframe_sub.value.sum() / denomframe_sub.value.sum()
    regvalues = list(numframe_sub.Region.all())
    percentiles = [{'col': 'lightsalmon', 'value': np.percentile(prop, 1/3*100)},
            {'col': 'tomato', 'value': np.percentile(prop, 2/3*100)},
            {'col': 'red', 'value': np.percentile(prop, 100)}]

    ax = plt.axes(projection = ccrs.TransverseMercator())

    boundlist = []
    for region_rec in region_shp.records():
        regcode = region_rec.attributes['ID']
        if regcode in regvalues:
            i = regvalues.index(regcode)
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
    for percentile in percentiles:
        percpatch = mpatches.Rectangle((0, 0), 1, 1, 
                facecolor = percentile['col'])
        percpatches.append(percpatch)
        perclabel = '\u2264' + str(np.round(percentile['value'], 4)).replace('.', ',')
        perclabels.append(perclabel)
    plt.legend(percpatches, perclabels, loc = 'lower left')
    plt.title('Döda {numcausealias}/{denomcausealias}\n'
    '{sexalias} {agealias} {startyear}\u2013{endyear}'.format(**locals()))

    plt.show()

def catot_yrsdict(region, cause):
    cadeaths = ndeaths([region], [cause])
    totdeaths = ndeaths([region], ['TOT'])
    return {'numframe': cadeaths['frame'], 'denomframe': totdeaths['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': totdeaths['dimension'],
            'numcause': cause, 'denomcause': 'TOT', 'region': region}

def catot_sexesdict(regvalues, cause, startyear, endyear):
    cadeaths = ndeaths(regvalues, [cause], yearvalues = yearrange(startyear, endyear))
    totdeaths = ndeaths(regvalues, ['TOT'], yearvalues = yearrange(startyear, endyear))
    return {'numframe': cadeaths['frame'], 'denomframe': totdeaths['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': totdeaths['dimension'],
            'numcause': cause, 'denomcause': 'TOT'}

def catot_mapdict(regvalues, cause, startyear, endyear, shapefname):
    cadeaths = ndeaths(regvalues, [cause], yearvalues = yearrange(startyear, endyear))
    totdeaths = ndeaths(regvalues, ['TOT'], yearvalues = yearrange(startyear, endyear))
    return {'numframe': cadeaths['frame'], 'denomframe': totdeaths['frame'],
            'numdim': cadeaths['dimension'], 'denomdim': totdeaths['dimension'],
            'numcause': cause, 'denomcause': 'TOT', 'shapefname': shapefname}

def reglabels(pardict):
    return pardict['numdim']['Region']['category']['label']
