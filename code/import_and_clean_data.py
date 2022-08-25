# --- IMPORTS ---
import numpy as np
import pandas as pd
import sqlite3

def generatePeopleDF(filepath_tn, filepath_imdb):
    # Suppresses SettingWithCopyWarning warnings
    pd.set_option('mode.chained_assignment', None)
    
    # --- FILEPATH IMPORTS ---
    # The Numbers movie information table
    tn_movies_df = pd.read_csv(filepath_tn)

    for column_title in ['production_budget', 'domestic_gross', 'worldwide_gross']:
        tn_movies_df[column_title].replace('[^\d]', '', inplace=True, regex=True)
        tn_movies_df[column_title] = tn_movies_df[column_title].astype(str).astype(np.int64)
    
    # IMDB database
    # ***IMPORTANT*** Make sure to unzip the "im.db.zip" file
    con = sqlite3.connect(filepath_imdb) 
    cursor = con.cursor()
    
    imdb_directors_df = pd.read_sql('''
    SELECT
        *
    FROM
        directors
    ''', con)

    imdb_writers_df = pd.read_sql('''
    SELECT
        *
    FROM
        writers
    ''', con)

    imdb_known_for_df = pd.read_sql('''
    SELECT
        *
    FROM
        known_for
    ''', con)

    imdb_persons_df = pd.read_sql('''
    SELECT
        *
    FROM
        persons
    ''', con)

    imdb_movie_basics_df = pd.read_sql('''
    SELECT
        *
    FROM
        movie_basics
    ''', con)

    # --- CREATING & CLEANING TEMP DATAFRAMES ---
    # - DIRECTORS DFS -
    dir_df = imdb_directors_df.merge(
        imdb_persons_df,
        how='left',
        on='person_id'
    ).merge(
        imdb_movie_basics_df,
        how='left',
        on='movie_id'
    ).merge(
        tn_movies_df,
        how='left',
        left_on='primary_title',
        right_on='movie'
    ).drop(columns=['birth_year', 'primary_profession', 'start_year', 'movie', 'runtime_minutes', 'id', 'release_date'])
    
    # Removing duplicates
    dir_df.drop_duplicates(inplace=True)

    # Remove any dead directors
    dir_df = dir_df[dir_df['death_year'].isna()]

    # Remove any movies that did not have a matching TN entry or have no revenue data
    dir_df.dropna(subset=['domestic_gross', 'worldwide_gross'], how='all', inplace=True)

    # Add a total_gross column and remove 0 revenue data (indicative of missing data)
    dir_df['total_gross'] = dir_df.domestic_gross + dir_df.worldwide_gross
    dir_df.drop(dir_df.loc[dir_df.total_gross == 0].index, inplace=True)
    
    # Remove any movies that did not have genre information, then convert genre column to list
    dir_df.dropna(subset=['genres'], inplace=True)
    dir_df['genres'] = dir_df.genres.apply(lambda x: x.lower().split(','))
    
    # Consolidate primary_title, domestic_gross, worldwide_gross, and total_gross into one dictionary in the movie_info column in a new DF
    grp_dir_df = dir_df.copy()
    grp_dir_df['movie_info'] = dir_df[['primary_title', 'genres', 'domestic_gross', 'worldwide_gross', 'total_gross', 'production_budget']].to_dict(orient='records')

    # Group by director
    grp_dir_df = grp_dir_df.movie_info.groupby(grp_dir_df.primary_name).apply(list).reset_index()

    # Add num_movies column, get rid of directors with < 3 movies
    grp_dir_df['num_movies'] = grp_dir_df.movie_info.str.len()
    grp_dir_df.drop(grp_dir_df[grp_dir_df['num_movies'] < 3].index, inplace=True)
    grp_dir_df.reset_index(inplace=True)
    
    # Uses ungrouped dataframe to find mean, median, and standard deviation of total gross revenue per director (also assigns genre information)
    grp_dir_df['genres'] = np.empty((len(grp_dir_df), 0)).tolist()
    grp_dir_df['mean_total_gross'] = np.nan
    grp_dir_df['median_total_gross'] = np.nan
    grp_dir_df['std_total_gross'] = np.nan

    for d in grp_dir_df.index:
        temp = dir_df.loc[dir_df.primary_name == grp_dir_df.primary_name[d]]
        grp_dir_df.mean_total_gross.iloc[d] = np.mean(temp.total_gross)
        grp_dir_df.median_total_gross.iloc[d] = np.median(temp.total_gross)
        grp_dir_df.std_total_gross.iloc[d] = np.std(temp.total_gross, ddof=1)
        for genre in temp.genres:
            grp_dir_df.genres[d].extend(genre)
    
    # Remove duplicate genres
    grp_dir_df.genres = grp_dir_df.genres.apply(set).apply(list)

    # Drop directors with an average < $100,000,000
    grp_dir_df.drop(grp_dir_df[grp_dir_df.mean_total_gross < 100000000].index, inplace=True)
    
    # 0 stddev = duplicate movies
    grp_dir_df.drop(grp_dir_df[grp_dir_df.std_total_gross == 0].index, inplace=True)

    # Calculates & creates coefficient of variation column
    grp_dir_df['coefficient_of_variation'] = grp_dir_df.std_total_gross / grp_dir_df.mean_total_gross
    grp_dir_df.sort_values('coefficient_of_variation', inplace=True)
    
    # Final cleaning & adding profession-identifying column
    grp_dir_df['profession'] = 'director'
    grp_dir_df.reset_index(inplace=True)
    grp_dir_df.drop(columns=['level_0', 'index'], inplace=True)
    
    # - WRITERS DFS -
    wri_df = imdb_writers_df.merge(
        imdb_persons_df,
        how='left',
        on='person_id'
    ).merge(
        imdb_movie_basics_df,
        how='left',
        on='movie_id'
    ).merge(
        tn_movies_df,
        how='left',
        left_on='primary_title',
        right_on='movie'
    ).drop(columns=['birth_year', 'primary_profession', 'start_year', 'movie', 'runtime_minutes', 'id', 'release_date'])
    
    # Removing duplicates
    wri_df.drop_duplicates(inplace=True)

    # Remove any dead writers
    wri_df = wri_df[wri_df['death_year'].isna()]

    # Remove any movies that did not have a matching TN entry or have no revenue data
    wri_df.dropna(subset=['domestic_gross', 'worldwide_gross'], how='all', inplace=True)

    # Add a total_gross column and remove 0 revenue data (indicative of missing data)
    wri_df['total_gross'] = wri_df.domestic_gross + wri_df.worldwide_gross
    wri_df.drop(wri_df.loc[wri_df.total_gross == 0].index, inplace=True)
    
    # Remove any movies that did not have genre information, then convert genre column to list
    wri_df.dropna(subset=['genres'], inplace=True)
    wri_df['genres'] = wri_df.genres.apply(lambda x: x.lower().split(','))
    
    # Consolidate primary_title, domestic_gross, worldwide_gross, and total_gross into one dictionary in the movie_info column in a new DF
    grp_wri_df = wri_df.copy()
    grp_wri_df['movie_info'] = wri_df[['primary_title', 'genres', 'domestic_gross', 'worldwide_gross', 'total_gross', 'production_budget']].to_dict(orient='records')

    # Group by writer
    grp_wri_df = grp_wri_df.movie_info.groupby(grp_wri_df.primary_name).apply(list).reset_index()

    # Add num_movies column, get rid of writers with < 3 movies
    grp_wri_df['num_movies'] = grp_wri_df.movie_info.str.len()
    grp_wri_df.drop(grp_wri_df[grp_wri_df['num_movies'] < 3].index, inplace=True)
    grp_wri_df.reset_index(inplace=True)
    
    # Uses ungrouped dataframe to find mean, median, and standard deviation of total gross revenue per writer (also assigns genre information)
    grp_wri_df['genres'] = np.empty((len(grp_wri_df), 0)).tolist()
    grp_wri_df['mean_total_gross'] = np.nan
    grp_wri_df['median_total_gross'] = np.nan
    grp_wri_df['std_total_gross'] = np.nan

    for w in grp_wri_df.index:
        temp = wri_df.loc[wri_df.primary_name == grp_wri_df.primary_name[w]]
        grp_wri_df.mean_total_gross.iloc[w] = np.mean(temp.total_gross)
        grp_wri_df.median_total_gross.iloc[w] = np.median(temp.total_gross)
        grp_wri_df.std_total_gross.iloc[w] = np.std(temp.total_gross, ddof=1)
        for genre in temp.genres:
            grp_wri_df.genres[w].extend(genre)
    
    # Remove duplicate genres
    grp_wri_df.genres = grp_wri_df.genres.apply(set).apply(list)

    # Drop writers with an average < $100,000,000
    grp_wri_df.drop(grp_wri_df[grp_wri_df.mean_total_gross < 100000000].index, inplace=True)
    
    # 0 stddev = duplicate movies
    grp_wri_df.drop(grp_wri_df[grp_wri_df.std_total_gross == 0].index, inplace=True)

    # Calculates & creates coefficient of variation column
    grp_wri_df['coefficient_of_variation'] = grp_wri_df.std_total_gross / grp_wri_df.mean_total_gross
    grp_wri_df.sort_values('coefficient_of_variation', inplace=True)
    
    # Final cleaning & adding profession-identifying column
    grp_wri_df['profession'] = 'writer'
    grp_wri_df.reset_index(inplace=True)
    grp_wri_df.drop(columns=['level_0', 'index'], inplace=True)
    
    # Resets SettingWithCopyWarning suppression
    pd.reset_option("mode.chained_assignment")
    
    # - ACTORS DFS -
    act_df = imdb_known_for_df.merge(
        imdb_persons_df,
        how='left',
        on='person_id'
    ).merge(
        imdb_movie_basics_df,
        how='left',
        on='movie_id'
    ).merge(
        tn_movies_df,
        how='left',
        left_on='primary_title',
        right_on='movie'
    ).drop(columns=['birth_year', 'start_year', 'movie', 'runtime_minutes', 'id', 'release_date'])
    
    # Removing duplicates & non-actors/actresses
    act_df.drop_duplicates(inplace=True)
    act_df.dropna(subset=['primary_profession'], inplace=True)
    act_df = act_df[act_df.primary_profession.str.contains('actor|actress', case=False)]

    # Remove any dead actors/actresses
    act_df = act_df[act_df['death_year'].isna()]

    # Remove any movies that did not have a matching TN entry or have no revenue data
    act_df.dropna(subset=['domestic_gross', 'worldwide_gross'], how='all', inplace=True)

    # Add a total_gross column and remove 0 revenue data (indicative of missing data)
    act_df['total_gross'] = act_df.domestic_gross + act_df.worldwide_gross
    act_df.drop(act_df.loc[act_df.total_gross == 0].index, inplace=True)
    
    # Remove any movies that did not have genre information, then convert genre column to list
    act_df.dropna(subset=['genres'], inplace=True)
    act_df['genres'] = act_df.genres.apply(lambda x: x.lower().split(','))
    
    # Consolidate primary_title, domestic_gross, worldwide_gross, and total_gross into one dictionary in the movie_info column in a new DF
    grp_act_df = act_df.copy()
    grp_act_df['movie_info'] = act_df[['primary_title', 'genres', 'domestic_gross', 'worldwide_gross', 'total_gross', 'production_budget']].to_dict(orient='records')

    # Group by actor
    grp_act_df = grp_act_df.movie_info.groupby(grp_act_df.primary_name).apply(list).reset_index()

    # Add num_movies column, get rid of actors with < 3 movies
    grp_act_df['num_movies'] = grp_act_df.movie_info.str.len()
    grp_act_df.drop(grp_act_df[grp_act_df['num_movies'] < 3].index, inplace=True)
    grp_act_df.reset_index(inplace=True)
    
    # Uses ungrouped dataframe to find mean, median, and standard deviation of total gross revenue per writer (also assigns genre information)
    grp_act_df['genres'] = np.empty((len(grp_act_df), 0)).tolist()
    grp_act_df['mean_total_gross'] = np.nan
    grp_act_df['median_total_gross'] = np.nan
    grp_act_df['std_total_gross'] = np.nan
    
    # This particular loop sometimes takes a while to iterate through all the actors
    for a in grp_act_df.index: 
        temp = act_df.loc[act_df.primary_name == grp_act_df.primary_name[a]]
        grp_act_df.mean_total_gross.iloc[a] = np.mean(temp.total_gross)
        grp_act_df.median_total_gross.iloc[a] = np.median(temp.total_gross)
        grp_act_df.std_total_gross.iloc[a] = np.std(temp.total_gross, ddof=1)
        for genre in temp.genres:
            grp_act_df.genres[a].extend(genre)
    
    # Remove duplicate genres
    grp_act_df.genres = grp_act_df.genres.apply(set).apply(list)

    # Drop actors with an average < $100,000,000
    grp_act_df.drop(grp_act_df[grp_act_df.mean_total_gross < 100000000].index, inplace=True)
    
    # 0 stddev = duplicate movies
    grp_act_df.drop(grp_act_df[grp_act_df.std_total_gross == 0].index, inplace=True)

    # Calculates & creates coefficient of variation column
    grp_act_df['coefficient_of_variation'] = grp_act_df.std_total_gross / grp_act_df.mean_total_gross
    grp_act_df.sort_values('coefficient_of_variation', inplace=True)
    
    # Final cleaning & adding profession-identifying column
    grp_act_df['profession'] = 'actor'
    grp_act_df.reset_index(inplace=True)
    grp_act_df.drop(columns=['level_0', 'index'], inplace=True)
    
    # Resets SettingWithCopyWarning suppression
    pd.reset_option("mode.chained_assignment")
    
    # --- CONCATENATION OF PERTINENT CLEANED DFS ---
    final_df = pd.concat([grp_dir_df, grp_wri_df, grp_act_df], keys=['directors', 'writers', 'actors'])
    
    return final_df