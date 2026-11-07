from pathlib import Path
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html, dash_table

ROOT = Path(__file__).resolve().parent
DATA = ROOT
FILES = {'sales':'sales_data_cleaned.csv','products':'product_data_cleaned.csv','prices':'price_observations_cleaned.csv','survey':'survey_public_summary.csv'}

def read_data():
    missing = [name for name in FILES.values() if not (DATA / name).exists()]
    if missing:
        raise FileNotFoundError('Missing data files in data/processed: ' + ', '.join(missing) + '. Run setup_data.ps1 or copy the four public CSV files from PeriodWise_Deployment.')
    return {key:pd.read_csv(DATA / filename) for key,filename in FILES.items()}

D = read_data()
sales, products, prices, survey = (D[k] for k in ('sales','products','prices','survey'))
for c in ['Units_Sold','Sales_Value']:
    sales[c] = pd.to_numeric(sales[c],errors='coerce')
for c in ['MRP','Selling_Price','Discount_Percent','Price_Per_Unit']:
    prices[c] = pd.to_numeric(prices[c],errors='coerce')
for c in ['Count','Sum']:
    survey[c] = pd.to_numeric(survey[c],errors='coerce')
if products['Product_ID'].duplicated().any():
    raise ValueError('Duplicate Product_ID found: cannot safely merge price observations')
joined = prices.merge(products[['Product_ID','Product_Type','Brand','Reusable']],on='Product_ID',how='left',validate='many_to_one')

PINK='#d14b8f'
PALETTE=['#d14b8f','#7b68d9','#46a6a1','#e5a45c','#7292c9']

def options(df,col):
    return [{'label':v,'value':v} for v in sorted(df[col].dropna().astype(str).unique())]

def chart(fig):
    fig.update_layout(template='plotly_white',font=dict(family='Inter, Segoe UI, Arial',color='#27334b'),colorway=PALETTE,margin=dict(l=28,r=20,t=62,b=35),paper_bgcolor='white',plot_bgcolor='white',legend_title_text='')
    return dcc.Graph(figure=fig,config={'displaylogo':False},responsive=True)

def empty(message='No matching records for these filters.'):
    return html.Div(message,className='empty')

def card(label,value):
    return html.Div([html.Span(label,className='metric-label'),html.Div(str(value),className='metric-value')],className='metric')

def cards(*items):
    return html.Div([card(k,v) for k,v in items],className='metrics')

def panel(content):
    return html.Div(content,className='panel')

def grid(*items):
    return html.Div([panel(item) for item in items],className='charts')

def dropdown(id,label,opts):
    return html.Div([html.Label(label),dcc.Dropdown(id=id,options=opts,value=[o['value'] for o in opts],multi=True,placeholder='Select options',className='selector')],className='filter')

def table(df):
    safe=df.copy().fillna('')
    return html.Div([html.H3('Filtered records'),dash_table.DataTable(data=safe.to_dict('records'),columns=[{'name':c,'id':c} for c in safe.columns],page_size=10,sort_action='native',filter_action='native',style_table={'overflowX':'auto'},style_cell={'fontFamily':'Segoe UI, Arial','fontSize':'12px','textAlign':'left','padding':'10px','maxWidth':'260px','overflow':'hidden','textOverflow':'ellipsis'},style_header={'backgroundColor':'#f8f1f7','fontWeight':'bold'},style_data_conditional=[{'if':{'row_index':'odd'},'backgroundColor':'#fafbfd'}])],className='panel')

def catfig(df,col,title,max_items=18):
    counts=df[col].dropna().astype(str).value_counts().head(max_items).sort_values()
    if counts.empty: return empty()
    f=px.bar(x=counts.values,y=counts.index,orientation='h',title=title,labels={'x':'Listings','y':''})
    f.update_traces(marker_color=PINK)
    return chart(f)

def summary_count(metric):
    rows=survey.loc[survey['Metric'].eq(metric),'Count']
    return int(rows.iloc[0]) if len(rows) else 0

def summary_avg(metric):
    rows=survey.loc[survey['Metric'].eq(metric)]
    if rows.empty or not rows.iloc[0]['Count']: return 'N/A'
    return f"{rows.iloc[0]['Sum']/rows.iloc[0]['Count']:.2f}"

def survey_fig(metric,title):
    df=survey.loc[survey['Metric'].eq(metric),['Category','Count']].copy()
    if df.empty: return empty()
    f=px.bar(df,x='Count',y='Category',orientation='h',title=title,text='Count')
    f.update_traces(marker_color=PINK,textposition='outside')
    f.update_layout(yaxis={'categoryorder':'total ascending'})
    return chart(f)

app = Dash(
    __name__,
    title='PeriodWise | Dash Analytics',
    suppress_callback_exceptions=True
)

server=app.server
NAV=[('overview','Overview'),('sales','Sales Analytics'),('products','Product Analytics'),('pricing','Pricing Analytics'),('survey','Survey Analytics')]
app.layout=html.Div([
    html.Aside([html.Div('✿ PeriodWise',className='brand'),html.P('DATA ANALYTICS',className='brand-sub'),html.Div([html.Button(label,id='nav-'+key,n_clicks=0,className='nav-btn') for key,label in NAV],className='nav'),html.Div(['Four public datasets',html.Br(),'Survey shown as aggregates'],className='sidebar-note')],className='sidebar'),
    html.Main([html.Div([html.Div([html.H1(id='page-title'),html.P('Menstrual product sales, pricing, product characteristics & consumer preferences',className='subtitle')]),html.Span('PUBLIC DATA',className='tag')],className='topbar'),dcc.Store(id='current-page',data='overview'),html.Div(id='page-content')],className='main')
],className='shell')

@app.callback(Output('current-page','data'),*[Input('nav-'+k,'n_clicks') for k,_ in NAV],prevent_initial_call=True)
def navigate(*clicks):
    from dash import ctx
    return ctx.triggered_id.removeprefix('nav-')

@app.callback(Output('page-title','children'),Output('page-content','children'),*[Output('nav-'+k,'className') for k,_ in NAV],Input('current-page','data'))
def render(page):
    title=dict(NAV).get(page,'Overview')
    active=['nav-btn active' if k==page else 'nav-btn' for k,_ in NAV]
    if page=='overview':
        body=html.Div([cards(('Sales records',len(sales)),('Catalog products',len(products)),('Price observations',len(prices)),('Survey respondents',summary_count('Responses'))),grid(catfig(products,'Product_Type','Catalog product types'),catfig(prices,'Retailer','Retail price observations')),html.P('Sales reports, product listings, and retailer observations are separate sources. Do not combine their counts as a single market total.',className='notice')])
    elif page=='sales':
        body=html.Div([html.Div([dropdown('sales-year','Financial year',options(sales,'Financial_Year')),dropdown('sales-period','Reporting period',options(sales,'Reporting_Period'))],className='filters'),html.Div(id='sales-results')])
    elif page=='products':
        body=html.Div([html.Div([dropdown('product-type','Product types',options(products,'Product_Type'))],className='filters'),html.Div(id='products-results')])
    elif page=='pricing':
        body=html.Div([html.Div([dropdown('price-retailer','Retailers',options(joined,'Retailer')),dropdown('price-type','Product types',options(joined,'Product_Type'))],className='filters'),html.Div(id='pricing-results')])
    else:
        body=html.Div([cards(('Survey respondents',summary_count('Responses')),('Avg. price importance (1–5)',summary_avg('Price_Importance')),('Avg. satisfaction (1–5)',summary_avg('Product_Satisfaction'))),grid(survey_fig('Monthly_Spending','Reported monthly spending'),survey_fig('Primary_Product','Primary product used'),survey_fig('Switched_Due_To_Price','Switched due to price'),survey_fig('Reusable_Willingness','Willingness to use reusable products')),html.P('Convenience sample of 69 respondents, concentrated among young students. These results are not nationally representative. Only aggregate data is included.',className='notice')])
    return title,body,*active

@app.callback(Output('sales-results','children'),Input('sales-year','value'),Input('sales-period','value'))
def sales_update(years,periods):
    df=sales.loc[sales['Financial_Year'].astype(str).isin(years or []) & sales['Reporting_Period'].astype(str).isin(periods or [])]
    state=df.groupby('State',as_index=False)['Units_Sold'].sum().nlargest(15,'Units_Sold').sort_values('Units_Sold')
    fy=df.groupby(['Financial_Year','Reporting_Period'],as_index=False)['Units_Sold'].sum()
    f1=px.bar(state,x='Units_Sold',y='State',orientation='h',title='Top states by recorded units sold') if not state.empty else None
    f2=px.bar(fy,x='Financial_Year',y='Units_Sold',color='Reporting_Period',barmode='group',title='Recorded units by year and reporting period') if not fy.empty else None
    return html.Div([cards(('Records',len(df)),('Recorded units sold',f"{df['Units_Sold'].sum():,.0f}"),('Rows with sales value',df['Sales_Value'].notna().sum())),grid(chart(f1) if f1 else empty(),chart(f2) if f2 else empty()),html.P('Reporting periods may differ in duration. Totals are descriptive, not directly comparable annual growth figures.',className='notice'),table(df)])

@app.callback(Output('products-results','children'),Input('product-type','value'))
def product_update(types):
    df=products.loc[products['Product_Type'].isin(types or [])]
    return html.Div([cards(('Catalog listings',len(df)),('Brands represented',df['Brand'].nunique()),('Product types',df['Product_Type'].nunique())),grid(catfig(df,'Product_Type','Products by type'),catfig(df,'Brand','Top brands in catalog'),catfig(df,'Reusable','Recorded reusable classifications')),html.P('These are collected catalog listings, not product sales or market share.',className='notice'),table(df.drop(columns=['Source_Product_URL'],errors='ignore'))])

@app.callback(Output('pricing-results','children'),Input('price-retailer','value'),Input('price-type','value'))
def price_update(retailers,types):
    df=joined.loc[joined['Retailer'].isin(retailers or []) & joined['Product_Type'].isin(types or [])]
    med=df['Selling_Price'].median()
    plots=[]
    if not df.empty:
        plots.append(chart(px.box(df,x='Product_Type',y='Selling_Price',color='Retailer',title='Selling price by product type')))
        unit=df.dropna(subset=['Price_Per_Unit'])
        if not unit.empty: plots.append(chart(px.box(unit,x='Product_Type',y='Price_Per_Unit',title='Price per unit by product type')))
        disc=df.dropna(subset=['Discount_Percent'])
        if not disc.empty: plots.append(chart(px.histogram(disc,x='Discount_Percent',nbins=20,title='Recorded discount distribution')))
    return html.Div([cards(('Price observations',len(df)),('Median selling price',f'₹{med:,.2f}' if pd.notna(med) else 'N/A'),('Recorded discounts',df['Discount_Percent'].notna().sum())),grid(*(plots or [empty()])),html.P('Retailers have different sampled product mixes. Unit prices for reusable and disposable products are not directly equivalent.',className='notice'),table(df.drop(columns=['Source_URL'],errors='ignore'))])

if __name__=='__main__':
    app.run(debug=True)
