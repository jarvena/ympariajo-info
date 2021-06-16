import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import geopandas as gpd
import logging

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
kunnat = gpd.read_file('./data/kunnat.geojson').to_crs(epsg=4326)
statsit = pd.read_csv('./data/ympäriajostatsit.csv', delimiter=';')

# Formatting data
logger.info('formatting data')
kunnat["Rajaviivan pituus"] = kunnat["Rajaviivan pituus"] / 1000
kunnat['Ajettu'] = kunnat['NAMEFIN'].isin(statsit["Kunta"].values)

statsit['Lähteneet'] = statsit['Lähteneet'].str.strip(' ').str.split(',')
statsit['Selvinneet'] = statsit['Selvinneet'].str.strip(' ').str.split(',')
statsit['Lähteneet lkm'] = statsit['Lähteneet'].apply(len)
statsit['Selvinneet lkm'] = statsit['Selvinneet'].apply(len)

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
  yaxis={'title_text': 'Selkkausten lukumäärä'}
)

fig_osallistuneet = px.bar(statsit, x='Kunta', y=['Lähteneet lkm', 'Selvinneet lkm'], barmode='group')
fig_osallistuneet.update_layout(
  margin={"r":0,"t":0,"l":0,"b":0},
  xaxis={'title_text': None},
  yaxis={'title_text': 'Lukumäärä'},
  legend=dict(title_text='Selite:', orientation='h', yanchor='bottom', y=1, xanchor='right', x=1)
)
fig_osallistuneet.update_traces(hovertemplate='Kunta=%{x}<br>Lähteneet=%{y}<extra></extra>', selector={'name': 'Lähteneet lkm'})
fig_osallistuneet.update_traces(hovertemplate='Kunta=%{x}<br>Selvinneet=%{y}<extra></extra>', selector={'name': 'Selvinneet lkm'})

logger.info('defining layout')
app.layout = dbc.Container([
    dbc.Row(dbc.Col(dbc.NavbarSimple(brand='Ympäriajotilastot', color='primary', dark=True), width=12), className='shadow mb-3'),
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
    ])
  ],
  fluid=True
)


if __name__ == '__main__':
  logger.info('running development server')
  app.run_server(debug=True)