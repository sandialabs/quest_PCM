import pandas as pd

# -------------------------------------------------------------------------
def filter_data_timesteps(time_setup, df_DA, df_RT, cumsum_cols=None):
    """
    Filter the DataFrames based on the time periods defined in the configuration.

    Used by helper functions to ensure only relevant time steps are exported to EGRET JSON files.

    Args:
        setup (dict): Configuration dictionary containing time period settings.
        df_DA (pd.DataFrame): Day-Ahead time series DataFrame.
        df_RT (pd.DataFrame): Real-Time time series DataFrame.

    Returns:
        tuple: (filtered_df_DA, filtered_df_RT) - Filtered DataFrames for DA and RT.
    """
    cumsum_cols = cumsum_cols or []
    filtered_df_DA = None
    filtered_df_RT = None

    # ---- Day-Ahead (simple filtering) ----
    if df_DA is not None:
        df_DA['date'] = pd.to_datetime(df_DA[['Year','Month','Day']])
        filtered_df_DA = df_DA[
            (df_DA['date'] >= time_setup['start_date']) &
            (df_DA['date'] <= time_setup['end_date']) &
            (df_DA['Period'].isin(time_setup['DA_periods']))
        ]

    # ---- Real-Time (with cumsum behavior) ----
    if df_RT is not None:
        df_RT['date'] = pd.to_datetime(df_RT[['Year','Month','Day']])
        df_rt_filt = df_RT[
            (df_RT['date'] >= time_setup['start_date']) &
            (df_RT['date'] <= time_setup['end_date'])
        ]

        periods = sorted(time_setup["RT_periods"])
        rows = []

        for (date, day_df) in df_rt_filt.groupby("date"):

            for i, p in enumerate(periods):
                row_p = day_df[day_df["Period"] == p].iloc[0]
                new_row = row_p.copy()

                # Determine the period range to sum
                if i < len(periods) - 1:
                    p_next = periods[i + 1] - 1
                else:
                    p_next = day_df["Period"].max()

                block = day_df[(day_df["Period"] >= p) & (day_df["Period"] <= p_next)]

                # Sum only the cumsum columns
                for col in cumsum_cols:
                    new_row[col] = block[col].sum()

                rows.append(new_row)

        filtered_df_RT = pd.DataFrame(rows)

    return filtered_df_DA, filtered_df_RT

def deep_merge(d1, d2):
    """
    Recursively merge two dictionaries.
    """
    result = dict(d1)  # shallow copy of d1
    for k, v in d2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result



    