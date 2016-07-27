# seregmort
This program can be used to analyze cause-specific regional Swedish mortality data at county or municipality level using the Statistics Sweden API ([API documentation in English](http://www.scb.se/Grupp/OmSCB/API/API-description.pdf)). The database accessible via the API covers deaths from 1969 to 1996 (a database covering cause-specific deaths at the county level occurring since 1997 is publicly accessible via [The National Board of Health and Welfare](http://www.socialstyrelsen.se/statistik/statistikdatabas/dodsorsaker) but cannot be used with the API). Data are retrieved in the [JSON-stat format](http://json-stat.org/) and saved into Pandas DataFrames using the [pyjstat](https://github.com/predicador37/pyjstat) library. HTTP requests are made with [requests](https://github.com/kennethreitz/requests/), and diagrams are plotted with [matplotlib](https://github.com/matplotlib/matplotlib). 

Possible values for regions, age groups, sexes and causes of death can be retrieved by `metadata(morturl)` which sends a GET request to the [mortality table](http://api.scb.se/OV0104/v1/doris/sv/ssd/START/HS/HS0301/DodaOrsak).

If the cause of death given contains a hyphen, it is assumed to be a chapter
rather than a single cause of death (the `agg:DödsorsakKapitel` level). The
following multi-cause chapters are supported:

| Chapter | Description
| ------- | -----------
| 1-2 | Infections
| 3-16 | Tumors
| 17-18 | Endocrine disorders
| 20-21 | Mental disorders
| 23-28 | Circulatory disorders
| 29-32 | Respiratory disorders
| 33-35 | Digestive disorders
| 36-39 | Genitourinary disorders
| 44-45 | Ill-defined causes
| 46-52 | External causes

##Examples
Save data on deaths from circulatory disorders in Västmanland County for the
whole period in a dictionary, and plot a smoothed diagram showing the time
trend for proportion of deaths due to this cause group for females and males in
age intervals above 70 years:

```python
pardict = catot_yrsdict('19', '23-28')
propplotyrs(**pardict, startage = '70-74', endage = '90+')
```
Save data on deaths from circulatory disorders in all municipalities in
Norrbotten County for the period 1981--86, and make a scatterplot of female vs
male proportion of all deaths due to this cause group during the period in the
age intervals between 75--79 and 85--89 years: 
```python
pardict = catot_mapdict(munis_incounty('25', metadata(morturl)), '23-28', 1981, 1986)
propscatsexes(**pardict, startage = '75-79', endage = '85-89')
```
Note that data for single years and narrow age bands are often not very useful due to the small numbers of deaths, especially at the municipality level.

Using [cartopy](https://github.com/SciTools/cartopy), it is also possible to plot maps showing regions with a lower or higher proportion of deaths from a given cause. 

The script has been adapted to work with the shapefiles available (under a
CCZero license) from National Archives of Sweden. You may download a [ZIP
archive](http://riksarkivet.se/psi/NAD_Topografidata.zip) with these files and
unzip it in the directory `naddata` under the `seregmort` directory. [One of the Excel
metadata files](http://riksarkivet.se/psi/g_units_names.xls) is included in this
repository in CSV format (under `naddata`); this file is used to translate the
geographical codes used by Statistics Sweden into the unit codes used in the
shapefiles.

Plot a map of the proportion of female deaths due to circulatory disorders in
all municipalities in Västernorrland County during the period 1981--86 in the
age intervals between 75--79 and 85--89 years (note that
`naddata/2504/__pgsql2shp2504_tmp_table.shp` is default shapefile path):
```python
pardict = catot_mapdict(munis_incounty('22', metadata(morturl)), '23-28', 1981, 1986)
propmap(**pardict, startage = '75-79', endage = '85-89', sex = '2') 
```

There is limited support for visualizing mortality rates by using population
size in the denominator (based on data from a [population
table](http://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy).
However, this is difficult to implement fully, because the tables use differing
age formats and (more importantly) because the population table uses a newer
regional divsion. Currently, it should work for age groups between 5--9 and
85--89 years and regions which have not changed since 1996. For example, to
plot a map of male mortality rates from circulatory disordes in the municipalities
in Västerbotten County during the period 1981--86 in the age intervals between
50--54 and 65--69 years:
```python
pardict = capop_mapdict(munis_incounty('24', metadata(morturl)), '23-28', 1981, 1986)
propmap(**pardict, startage = '50-54', endage = '70-74', sex = '1')
```

The `capop_mapdict` wrapper can also be used with `propscatsexes` for drawing
scatterplots, as in the example with `catot_mapdict`. The `capop_yrsdict`
wrapper can be used with `propplotyrs`.
