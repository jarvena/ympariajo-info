import dash
from dash.dependencies import Output
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import geopandas as gpd
import pymongo
import os
import logging
import datetime

DB_URL = os.getenv('DB_URL')
LIVE_LENGTH = datetime.timedelta(days=2)
AJETTAVA = 'Kauniainen'

logging.basicConfig(
    level=logging.INFO,
    filename='app.log',
    format=
    '%(asctime)s [%(levelname)s] [%(pathname)s line %(lineno)d @%(thread)d] - %(message)s '
)
logger = logging.getLogger(__name__)

logger.info('app script starts')

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = 'Ympäriajojen suoritustilanneseuranta'

server = app.server

# Reading data
logger.info('reading data')
kunnat = gpd.read_file('./data/kunnatwgs84simplified.geojson')
statsit = pd.read_csv('./data/ympäriajostatsit.csv', delimiter=';')

# Setting up db connection
def parse_locationdata(collection): # A function for reading location information from Mongo
  data = collection.find({})
  reitit = {'times': [], 'names': [], 'lats': [], 'lons': []}
  kuvat = {}

  for object in data:
    if (datetime.datetime.now() - object['route'][-1][-1] < LIVE_LENGTH) and (len(object['route'])>0):
      reitit['lons'] = reitit['lons'] + list(map(lambda x: x[1], object['route']))
      reitit['lats'] = reitit['lats'] + list(map(lambda x: x[0], object['route']))
      reitit['times'] = reitit['times'] + list(map(lambda x: x[2] + datetime.timedelta(hours=3), object['route']))
      reitit['names'] = reitit['names'] + [object['details']['name']['first']]*len(object['route'])
      kuvat[object['details']['name']['first']] = object['details']['photo']
  
  reittiDf = pd.DataFrame(reitit)
  return reittiDf, kuvat

client = pymongo.MongoClient(DB_URL)
collection = client.routedata.routes

# Formatting data
logger.info('formatting data')
kunnat['Ajettu'] = kunnat['NAMEFIN'].isin(statsit["Kunta"].values)

statsit['Lähteneet'] = statsit['Lähteneet'].str.strip(' ').str.split(',')
statsit['Selvinneet'] = statsit['Selvinneet'].str.strip(' ').str.split(',')
statsit['Lähteneet lkm'] = statsit['Lähteneet'].apply(len)
statsit['Selvinneet lkm'] = statsit['Selvinneet'].apply(len)
statsit['Keskeyttäneet lkm'] = statsit['Lähteneet lkm'] - statsit['Selvinneet lkm']

statsit_osallistujittain = pd.DataFrame(statsit['Selvinneet'].explode().value_counts()).rename(columns={'Selvinneet': 'Selviytymiset'})

logger.info('creating graphs')
kartta = px.choropleth_mapbox(kunnat,
  geojson=kunnat.geometry,
  locations=kunnat.index,
  opacity=0.5,
  zoom=6
  ,
  color="Ajettu",
  mapbox_style="carto-positron",
  center={"lat":60.18, "lon":24.93},

  hover_name="NAMEFIN",
  hover_data={'Rajaviivan pituus': ':.0f'} #["Rajaviivan pituus"]
)
kartta.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  legend=dict(yanchor='top', y=0.99, xanchor='left', x=0.01))
kartta.update_traces(hovertemplate='<b>%{hovertext}</b><br><br>Rajaviivan pituus: %{customdata[0]:.0f}km<extra></extra>')

fig_selkkaukset = px.bar(statsit, x='Kunta', y='Selkkaukset')
fig_selkkaukset.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  xaxis={'title_text': None},
  yaxis={'title_text': 'Selkkausten lukumäärä'},
  dragmode='select'
)

fig_osallistuneet = px.bar(statsit, x='Kunta', y=['Selvinneet lkm', 'Keskeyttäneet lkm'] )#barmode='group')
fig_osallistuneet.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  xaxis={'title_text': None},
  yaxis={'title_text': 'Lukumäärä'},
  legend=dict(title_text='Selite:', orientation='h', yanchor='bottom', y=1, xanchor='right', x=1),
  dragmode='select'
)
fig_osallistuneet.update_traces(hovertemplate='Kunta=%{x}<br>Selvinneet=%{y}<extra></extra>', selector={'name': 'Selvinneet lkm'})
fig_osallistuneet.update_traces(hovertemplate='Kunta=%{x}<br>Keskeyttäneet=%{y}<extra></extra>', selector={'name': 'Keskeyttäneet lkm'})

fig_kaatumiset = px.bar(statsit, x='Kunta', y='Kaatumiset')
fig_kaatumiset.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  xaxis={'title_text': None},
  yaxis={'title_text': 'Lukumäärä'},
  dragmode='select'
)

fig_osallistujaselviytymiset = px.bar(statsit_osallistujittain, x=statsit_osallistujittain.index.values, y='Selviytymiset')
fig_osallistujaselviytymiset.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  xaxis={'title_text': None},
  yaxis={'title_text': 'Lukumäärä'},
  dragmode='select'
  )
fig_osallistujaselviytymiset.update_traces(hovertemplate='<b>%{x}</b><br>Selviytymiset=%{y}<extra></extra>')

liveTracking = dbc.Row([
  dbc.Col(
    id='live-tracking-column',
    width=12
  ),
  dcc.Interval(id='interval-component', interval=30*1000, n_intervals=0)
])

logger.info('defining layout')
app.layout = dbc.Container([
    dbc.Row(dbc.Col(dbc.NavbarSimple(brand='Ympäriajotilastot', color='primary', dark=True), width=12), className='shadow mb-3'),
    liveTracking,
    dbc.Row(
      dbc.Col(
        dbc.Card([
          dbc.CardHeader('Suoritustilanne kartalla'),
          dbc.CardBody(dcc.Graph(
            id='ajetut-kartta',
            figure=kartta
          ))
        ], className='mb-3'),
        width=12
      )
    ),
    dbc.Row([
      dbc.Col(
        dbc.Card([
          dbc.CardHeader('Selkkaukset kunnittain'),
          dbc.CardBody(dcc.Graph(
            id='selkkaukset-fig',
            figure=fig_selkkaukset,
            config={'displayModeBar': False}
          ))
        ]),
        width=6
      ),
      dbc.Col(
        dbc.Card([
          dbc.CardHeader('Osallistujamäärät kunnittain'),
          dbc.CardBody(dcc.Graph(
            id='osallistuneet-fig',
            figure=fig_osallistuneet,
            config={'displayModeBar': False}
          ))
        ]),
        width=6
      )
    ], className='mb-3'),
    dbc.Row([
      dbc.Col(
        dbc.Card([
          dbc.CardHeader('Kaatumiset kunnittain'),
          dbc.CardBody(dcc.Graph(
            id='kaatumiset-fig',
            figure=fig_kaatumiset,
            config={'displayModeBar': False}
          ))
        ]),
        width=6
      ),
      dbc.Col(
        dbc.Card([
          dbc.CardHeader('Selviytymismäärä osallistujittain'),
          dbc.CardBody(dcc.Graph(
            id='selvitymiset-fig',
            figure=fig_osallistujaselviytymiset,
            config={'displayModeBar': False}
          ))
        ]),
        width=6
      )
    ])
  ],
  fluid=True
)

@app.callback(
  Output('live-tracking-column', 'children'),
  Input('interval-component', 'n_intervals'))
def updateLive(n):
  liveData, photos = parse_locationdata(collection)
  if liveData.size == 0:
    return None
  
  logger.info('Creating/updating live location tracking')

  liveData = liveData[liveData.times > datetime.datetime.now() - LIVE_LENGTH - datetime.timedelta(days=1)]
  #print(liveData.head())

  liveKartta = px.line_mapbox(liveData,
    lat='lats',
    lon='lons',
    line_group='names',
    mapbox_style="carto-positron",
    hover_data={'names': True, 'times': "|%X"}
  )
  # liveKartta.update_layout(
  #   margin={"r":0,"t":0,"l":0,"b":0},
  #   legend=dict(yanchor='top', y=0.99, xanchor='left', x=0.01),
  #   legend_title_text='Selite',
  #   mapbox={
  #     'zoom': 10,
  #     'center': {"lat":60.5425, "lon":25.61}
  #   },
  #   uirevision='static' # to prevent ui reset at each update
  # )
  liveKartta.update_traces(hovertemplate='<b>%{customdata[0]}</b><br>Nähty: %{customdata[1]|%H:%M}<extra></extra>')

  # Highlighting the latest location update
  #print('latest update: ', liveData['times'].idxmax())
  latest_update = liveData.loc[liveData['times'].idxmax()]
  liveKartta.add_trace(
    go.Scattermapbox(
      lat=[latest_update.lats],
      lon=[latest_update.lons],
      name='Reitti ja sijainti',
      mode='lines+markers',
      marker=dict(
        size=10,
        color='#636dfa'
      ),
      hoverinfo='skip'
    )
  )

  

  # Adding municipality border to the map
  geometry=kunnat[kunnat['NAMEFIN']==AJETTAVA].geometry.iloc[0]
  lats=geometry.boundary.coords.xy[1]
  lons=geometry.boundary.coords.xy[0]
  liveKartta.add_trace(
    go.Scattermapbox(
      lat=list(lats),
      lon=list(lons),
      mode='lines',
      name='Kunnanraja',
      hovertemplate=f'<b>{AJETTAVA}</b><extra></extra>',
      line_color='#00cc96'
    )
  )

  # Set layout properties
  liveKartta.update_layout(
    margin={"r":0,"t":0,"l":0,"b":0},
    legend=dict(yanchor='top', y=0.99, xanchor='left', x=0.01),
    legend_title_text='Selite',
    mapbox={
      'zoom': 9.5,
      'center': {"lat":geometry.centroid.y, "lon":geometry.centroid.x}
    },
    uirevision='static' # to prevent ui reset at each update
  )

  if datetime.datetime.now() - latest_update.times + datetime.timedelta(hours=3) < datetime.timedelta(minutes=5):
    badgeText = 'Live'; badgeColor='success'
  else:
    badgeText = 'Offline'; badgeColor='danger'

  children = dbc.Card([
    dbc.CardHeader([dbc.Badge(badgeText, color=badgeColor, className="mr-1"), 'Reaaliaikainen tilanneseuranta']),
    dbc.CardBody([dcc.Graph(
      id='live-kartta',
      figure=liveKartta
      )
    ])
  ], className='mb-3')

  return children


if __name__ == '__main__':
  logger.info('running development server')
  app.run_server(debug=True)