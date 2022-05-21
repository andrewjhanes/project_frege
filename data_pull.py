##########################################################################################
# Import and Setup
##########################################################################################
# import setup as s
import logging
import sys
import pandas as pd
import numpy as np
import datetime as dt
from datetime import date, datetime
import matplotlib.mlab as mlab
from matplotlib.pyplot import figure
import matplotlib.pyplot as plt
from statsmodels.tsa.arima_process import ArmaProcess
import statsmodels.api as sm
import statsmodels.formula.api as smf
from causalimpact import CausalImpact
# from: https://github.com/jldbc/pybaseball/blob/master/docs/statcast_pitcher.md
import pybaseball
from pybaseball import statcast_pitcher
from pybaseball import playerid_lookup
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
data_raw = bs.statcast(start_dt=start_date, end_dt=end_date)
data_raw.info()
data_raw.head(10)
data_raw.to_csv('statcast_' + start_date + '_' + end_date + '.csv')

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
# Investigate Data
##########################################################################################
df = df_raw.copy()

##########################################################################################
# Basic grouping
##########################################################################################
