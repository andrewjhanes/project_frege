import setup
data = setup.statcast(start_dt='2017-06-24', end_dt='2017-06-27')
data.info()
data.head(10)
data.head(100).to_csv('sample_data.csv')
