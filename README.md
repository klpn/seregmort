# seregmort
This program can be used to analyze cause-specific regional Swedish mortality data at county or municipality level using the Statistics Sweden API ([API documentation in English](http://www.scb.se/Grupp/OmSCB/API/API-description.pdf)). The database accessible via the API covers deaths from 1969 to 1996 (a database covering cause-specific deaths at the county level occurring since 1997 is publicly accessible via [The National Board of Health and Welfare](http://www.socialstyrelsen.se/statistik/statistikdatabas/dodsorsaker) but cannot be used with the API). Data are retrieved in the [JSON-stat format](http://json-stat.org/) and saved into Pandas DataFrames using the [pyjstat](https://github.com/predicador37/pyjstat) library. HTTP requests are made with [requests](https://github.com/kennethreitz/requests/), and diagrams are plotted with [matplotlib](https://github.com/matplotlib/matplotlib). 

Possible values for regions, age groups, sexes and causes of death can be retrieved by `metadata(morturl)` which sends a GET request to the [mortality table](http://api.scb.se/OV0104/v1/doris/sv/ssd/START/HS/HS0301/DodaOrsak).

##Examples
Save data on deaths from circulatory disorders in Västmanland County for the whole period in a dictionary, and plot a smoothed diagram showing the time trend for proportion of deaths due to this cause group for females and males in the age interval of 70--74 years.

```python
pardict = catot_yrsdict('19', '23-28')
propplotyrs(**pardict, age = '70-74')
```
Save data on deaths from circulatory disorders in all municipalities in Norrbotten County for the period 1981--86, and make a scatterplot of female vs male proportion of all deaths due to this cause group during the period in the age interval of 75--79 years. Note that data for single years are often not very useful due to the small numbers of deaths, especially at the municipality level.

```python
pardict = catot_sexesdict(munis_incounty('25', metadata(morturl)), '23-28', 1981, 1986)
propscatsexes(**pardict, age = '75-79')
```
