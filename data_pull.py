##########################################################################################
# Import and Setup
##########################################################################################
# General info on stats
    # wOBA: https://library.fangraphs.com/offense/woba/
# import setup as s
import logging
import sys
import pandas as pd
import numpy as np
from IPython import display
import datetime as dt
from datetime import date, datetime
import matplotlib.mlab as mlab
from matplotlib.pyplot import figure
import matplotlib.pyplot as plt
# Info on baseball_scraper package and Statcast fields
    # https://pypi.org/project/baseball-scraper/
    # https://github.com/spilchen/baseball_scraper/blob/master/docs/statcast.md
    # https://baseballsavant.mlb.com/csv-docs
import baseball_scraper as bs
from baseball_scraper import statcast
print("imports complete")
##########################################################################################
# Variables
##########################################################################################
start_date = '2017-04-02'
end_date = '2017-10-01'

##########################################################################################
# Pull Data
##########################################################################################
# data_raw = bs.statcast(start_dt=start_date, end_dt=end_date)
# data_raw.to_csv('statcast_' + start_date + '_' + end_date + '.csv')
data_raw = pd.read_csv('statcast_' + start_date + '_' + end_date + '.csv')
data_raw.info()
data_raw.head(10)

##########################################################################################
# Investigate Data
##########################################################################################
# Key columns from statcast data
cols = ['game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'balls', 'strikes', 'pitch_type', 'pitch_name',
        'type', 'effective_speed', 'zone', 'events', 'description',
        'bb_type', 'hit_distance_sc', 'launch_speed', 'launch_angle',
        'stand', 'p_throws',
        'estimated_ba_using_speedangle', 'estimated_woba_using_speedangle', 'woba_value', 'woba_denom', 'babip_value',
        ]
df_raw = data_raw[cols]
df_raw.info()
df_raw['pitch_type'].unique()
df_raw['pitch_name'].unique()
df_raw['type'].unique()
df_raw['events'].unique()
df_raw['description'].unique()

# Based on the unique column values above, we might need to account for:
# > Null pitch types/names -- not all pitches have recorded pitch types. Should we also remove entire at bats where
#       ...there is a missing pitch type?
# > Want to remove position players pitching (this happens in blowouts)
# > Remove pitches (or at bats with pitches) of type Eephus (literally a lobbed pitch), Screwball (not really a pitch
#       ...anymore, and might be confused with Changeup), definitely Pitch Outs, possibly Knuckleballs (pitchers who
#       ...pitch Knuckleballs typically mostly throw Knuckelballs with only the occasional fastball)
# FYI: "Sinker" = "2-Seam Fastball" (a pitch that runs to the pitchers arm side and sinks compared to the 4-Seam which
#       ...has a rising effect due to seam generated lift)
# "Fastball" is in there as well as 4-Seam Fastball and Sinker (or 2-Seam Fastball). How often are these in there, and
#       ...are they simple another type of fastball being misclassified? Might need to remove. Investigate frequency.
# Consider removing plate appearances where there is  bunt attempt, pitch out, and maybe hit by pitch. At the very
#       ...least remove those pitches from our evaluated set.

df_raw.groupby(['pitch_name'])[['type']].count().sort_values('type', ascending=False)
# Confirming it's probably ok to remove entire plate appearances with pitchs in them of a type below. These are so
#       ...infrequent that it won't reduce our dataset much.
#       ['Knuckle', 'Fork', 'Eephus', 'Pitch Out', 'Fastball', 'Screwball']

df_raw.groupby(['description'])[['type']].count().sort_values('type', ascending=False)
# Probably ok to remove entire plate appearances with bunt attempts, pitch outs, and hit by pitches
#       ['foul_bunt', 'hit_by_pitch', 'missed_bunt', 'pitchout', 'bunt_foul_tip']

df_raw.groupby(['events'])[['type']].count().sort_values('type', ascending=False)
# Remove plate appearances wtih events of:
#       ['hit_by_pitch', 'sac_bunt', 'caught_stealing_2b', 'strikeout_double_play', 'other_out', 'caught_stealing_3b',
#       'pickoff_2b', 'pickoff_1b', 'catcher_interf', 'caught_stealing_home', 'pickoff_caught_stealing_2b',
#       'game_advisory', 'pickoff_caught_stealing_home', 'stolen_base_2b', 'stolen_base_home',
#       'pickoff_caught_stealing_3b']
# How do we want to handle field_error? The result is the batter got on, but this isn't a "win" for the batter, as
#       ...the pitcher successfully got the batter to make what should have been an out. If we look at expected stats,
#       ...then this won't be an issue because the actual result doesn't matter. If we look at actual stats, then
#       ...I think we should remove.

##########################################################################################
# Clean Data
##########################################################################################
df = df_raw.copy()
filt_pitch_name = ['Knuckle', 'Fork', 'Eephus', 'Pitch Out', 'Fastball', 'Screwball']
filt_description = ['foul_bunt', 'hit_by_pitch', 'missed_bunt', 'pitchout', 'bunt_foul_tip']
filt_events = ['hit_by_pitch', 'sac_bunt', 'caught_stealing_2b', 'strikeout_double_play', 'other_out',
                 'caught_stealing_3b', 'pickoff_2b', 'pickoff_1b', 'catcher_interf', 'caught_stealing_home',
                 'pickoff_caught_stealing_2b', 'game_advisory', 'pickoff_caught_stealing_home', 'stolen_base_2b',
                 'stolen_base_home', 'pickoff_caught_stealing_3b']

df['id_ab'] = df['game_pk'].astype(str) + df['at_bat_number'].astype(str)
df['is_filt_pitch'] = 0
df.loc[df['pitch_name'].isin(filt_pitch_name), 'is_filt_pitch'] = 1
df['is_filt_desc'] = 0
df.loc[df['description'].isin(filt_description), 'is_filt_desc'] = 1
df['is_filt_event'] = 0
df.loc[df['events'].isin(filt_events), 'is_filt_event'] = 1

df['is_filt_any'] = df['is_filt_pitch'] + df['is_filt_desc'] + df['is_filt_event']
filt_id_ab = df.loc[df['is_filt_any'] > 0].id_ab.values.tolist()
df = df.loc[~df['id_ab'].isin(filt_id_ab)]
df.head(1000).to_csv('sample_filtered_data.csv')
##########################################################################################
# Basic grouping
##########################################################################################
df = df.sort_values(['game_date', 'game_pk', 'at_bat_number', 'pitch_number'],
                    ascending=True, na_position='first')
df['pitch_type_prev'] = df.groupby(['game_pk', 'at_bat_number'])['pitch_type'].shift(1)
df['pitch_name_prev'] = df.groupby(['game_pk', 'at_bat_number'])['pitch_name'].shift(1)
df['type_prev'] = df.groupby(['game_pk', 'at_bat_number'])['type'].shift(1)
df.head(1000).to_csv('sample_shifted_data.csv')

df_1 = df.groupby(['pitch_name']).agg(
    {'type': 'count',
     'bb_type': 'count',
     'woba_value': 'sum',
     'woba_denom': 'sum'})
df_1['woba'] = df_1['woba_value'] / df_1['woba_denom']
df_1.sort_values('woba', ascending=False).head(10)

df_2 = df.groupby(['pitch_name', 'pitch_name_prev']).agg(
    {'type': 'count',
     'bb_type': 'count',
     'woba_value': 'sum',
     'woba_denom': 'sum'})
df_2['woba'] = df_2['woba_value'] / df_2['woba_denom']
df_2.sort_values('bb_type', ascending=False).head(30)