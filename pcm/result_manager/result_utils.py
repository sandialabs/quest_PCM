import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator
import matplotlib.dates as mdates
import plotly.graph_objects as go
import pandas as pd 
import os
import datetime

def format_time_axis(ax, x_values):
    """Dynamically format x-axis based on time span."""
    
    # Ensure datetime
    x = pd.to_datetime(x_values)
    span_days = (x.max() - x.min() + datetime.timedelta(days=1)).days

    if span_days <= 2:
        # High resolution (hours)
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 6)) 
        )
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%b %d'))
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 3)))

    elif span_days <= 14:
        # Medium (days)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 12)))

    elif span_days <= 60:
        # Weeks
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
    else:
        # Long horizon (months)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=15))

    ax.grid(True, which='major', axis='x', linestyle='-', alpha=0.6)
    ax.grid(True, which='minor', axis='x', linestyle='--', alpha=0.3)
    ax.tick_params(axis='x', which='major')
    ax.tick_params(axis='x', which='minor', length=0)
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

def plot_stackgraphs(result, reference_vals, plot_dict, plot_name, plotly_enabled = True, png_enabled = True, subdir_name = ""):
    """Create stacked dispatch/cost plots (PNG and Plotly outputs).

    This function accepts positive and negative series in a
    single DataFrame and separates them to produce stacked
    visualizations for both Matplotlib (PNG) and Plotly (HTML).

    Parameters
    - result (pd.DataFrame): DataFrame where each column is a
        named series (time indexed) to be stacked.
    - reference_vals (pd.Series or pd.DataFrame): Optional
        reference time series (e.g., demand) plotted on top.
    - plot_dict (dict): Metadata describing plotting options and
        axes (see `populate_plot_dict` usage in callers).
    - plot_name (str): Base filename used for saved outputs.
    - plotly_enabled (bool): If True, write Plotly HTML output.
    - png_enabled (bool): If True, write Matplotlib PNG output.

    The function writes outputs under `plot_dict['result_directory']`.
    """

    pos = result.clip(lower=0)
    neg = result.clip(upper=0)
    # Separate positive and negative parts
    df_pos = result.clip(lower=0)
    df_pos = df_pos.loc[:, (df_pos != 0).any(axis=0)]
    
    df_neg = result.clip(upper=0)
    df_neg = df_neg.loc[:, (df_neg != 0).any(axis=0)]
    # Compute positive stack
    df_pos_cumul = df_pos.cumsum(axis=1)
    df_pos_base = df_pos_cumul.subtract(df_pos, axis=0)
    # Compute negative stack (note: cumsum stacks downward)
    df_neg_cumul = df_neg.cumsum(axis=1)
    df_neg_base = df_neg_cumul.subtract(df_neg, axis=0)
    
    color_dict = plot_dict["color_dict"]
    if png_enabled:
        fig, ax = plt.subplots(figsize=(10, 8))
        handled = set()
        # Positive stack
        for col in df_pos.columns:
            label = col if col not in handled else "_nolegend_"
            handled.add(col)
            if plot_dict["plot_type"] == "fill":
                ax.fill_between(plot_dict["plotter_x_axis"], df_pos_base[col], df_pos_cumul[col],
                                label=label, color=color_dict[col], alpha=0.8)
            if plot_dict["plot_type"] == "bar":
                ax.bar(plot_dict["plotter_x_axis"], height = df_pos[col], bottom = df_pos_base[col], 
                            label=label, color=color_dict[col], width = plot_dict["width_days"], alpha=0.8)
        # Negative stack
        for col in df_neg.columns:
            label = col if col not in handled else "_nolegend_"
            handled.add(col)
            if plot_dict["plot_type"]  == "fill":
                ax.fill_between(plot_dict["plotter_x_axis"], df_neg_base[col], df_neg_cumul[col],
                                label=label, alpha=0.8, color=color_dict[col])
            if plot_dict["plot_type"]  == "bar":
                ax.bar(plot_dict["plotter_x_axis"], height = df_neg[col], bottom = df_neg_base[col], 
                            label=label, color=color_dict[col], width = plot_dict["width_days"], alpha=0.8)
        if not reference_vals.empty:
            ax.plot(plot_dict["plotter_x_axis"], reference_vals, color='black', linewidth=2, label=plot_dict['reference_val_name'], linestyle='--')
        ax.legend(loc="center left",
                bbox_to_anchor=(1, 0.5), fontsize=15, frameon=False)
        plt.subplots_adjust(right=0.75)
        ax.set_ylabel(plot_dict["ylabel"], fontsize=20)
        ax.set_title(plot_dict["title"], fontsize=25)
        ax.tick_params(axis='both', which='major', labelsize=14)
        ax.margins(x=0, y=0)
        ax.grid(True, linestyle='--', alpha=0.7)
        format_time_axis(ax, plot_dict["plotter_x_axis"])
        if subdir_name:
            os.makedirs(os.path.join(plot_dict["result_directory"], "png_plots", subdir_name), exist_ok=True)
        plt.savefig(os.path.join(plot_dict["result_directory"], "png_plots", subdir_name, plot_name + ".png"), bbox_inches='tight', dpi=600, pad_inches=0)
        plt.close()

    if not plotly_enabled:
            return
    # Make an interactive plotly fig
    fig = go.Figure()
    # Positive stack
    handled = set()
    for col in df_pos.columns:
        show_legend = col not in handled
        handled.add(col)
        if plot_dict["plot_type"] == "fill":
            fig.add_trace(go.Scatter(
                x=plot_dict["plotter_x_axis"],
                y=df_pos[col],             # cumulative top
                mode='lines',
                line=dict(width=0.05, color=color_dict[col]),
                fill='tonexty',                # fill down to previous trace
                stackgroup='one',
                name=col,
                showlegend = show_legend,
                hovertemplate=f"{col}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))
        if plot_dict["plot_type"] == "bar":
                fig.add_trace(go.Bar(
                x=plot_dict["plotter_x_axis"],
                y=df_pos[col],
                name=col,
                showlegend = show_legend,
                marker=dict(color=color_dict[col]),
                hovertemplate=f"{col}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))

    # Negative stack
    for col in df_neg.columns:
        show_legend = col not in handled
        handled.add(col)
        if plot_dict["plot_type"] == "fill":
            fig.add_trace(go.Scatter(
                x=plot_dict["plotter_x_axis"],
                y=df_neg[col],
                mode='lines',
                line=dict(width=0.05, color=color_dict[col]),
                fill='tonexty',
                stackgroup='two',
                name=col,
                showlegend = show_legend,
                hovertemplate=f"{col}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))
        if plot_dict["plot_type"] == "bar":
                fig.add_trace(go.Bar(
                x=plot_dict["plotter_x_axis"],
                y=df_neg[col],
                name=col,
                showlegend = show_legend,
                marker=dict(color=color_dict[col]),
                hovertemplate=f"{col}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))

    if not reference_vals.empty:
        fig.add_trace(go.Scatter(
            x=plot_dict["plotter_x_axis"],
            y=reference_vals.iloc[:,0].values,
            mode='lines',
            line=dict(color='black', width=2, dash='dash'),
            name=plot_dict['reference_val_name'],
            hovertemplate=f"{plot_dict['reference_val_name']}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
        ))
    # Layout
    layout_kwargs = dict(title=plot_dict["title"],
        yaxis_title=plot_dict["ylabel"],
        template="plotly_white",
        hovermode="x unified",
    )

    # Only add barmode if plotting bars
    if plot_dict["plot_type"]  == "bar":
        layout_kwargs["barmode"] = "relative"
        
    fig.update_layout(**layout_kwargs)
    # Save to HTML file
    if subdir_name:
        os.makedirs(os.path.join(plot_dict["result_directory"], "plotly_plots", subdir_name), exist_ok=True)
        
    fig.write_html(os.path.join(plot_dict["result_directory"], "plotly_plots", subdir_name, plot_name + ".html"))

def plot_lines(result, plot_dict, plot_name, plotly_enabled = True, png_enabled = True, subdir_name = ""):
    """Plot multiple time-series as lines (PNG and Plotly outputs).

    Parameters
    - result (pd.DataFrame): Time-indexed DataFrame containing one or
        more series to plot. Columns will be used as legend labels.
    - plot_dict (dict): Metadata describing labels, axis and output
        locations used by the plotting helpers.
    - plot_name (str): Base filename used for saved outputs.
    - plotly_enabled (bool): If True, write interactive Plotly HTML.
    - png_enabled (bool): If True, write static Matplotlib PNG.
    - subdir_name (str): Optional subdirectory under results for files.

    The function produces both static PNGs (if enabled) and an HTML
    file with interactive controls that allow selecting individual
    series when multiple traces are present.
    """

    # Ensure column names are strings for nicer legends
    result.columns = result.columns.astype(str)
   
    # --- Plot with matplotlib ---
    if png_enabled:
        fig, ax = plt.subplots(figsize=(12, 6))
        for col in result.columns:
            if plot_dict["plot_type"] == "step":
                ax.step(plot_dict["plotter_x_axis"], result[col], label=f"{col}")
            elif plot_dict["plot_type"] == "bar":
                ax.bar(plot_dict["plotter_x_axis"], result[col], label=f"{col}",width = plot_dict["width_days"], alpha=0.8)
            else:
                ax.plot(plot_dict["plotter_x_axis"], result[col], label=f"{col}")
        ax.legend(loc="center left",
                    bbox_to_anchor=(1, 0.5), fontsize=15, frameon=False)
        plt.subplots_adjust(right=0.75)
        ax.set_ylabel(plot_dict["ylabel"], fontsize=20)
        ax.set_title(plot_dict["title"], fontsize=25)
        ax.tick_params(axis='both', which='major', labelsize=14)
        ax.margins(x=0, y=0)
        ax.grid(True, linestyle='--', alpha=0.7)
        format_time_axis(ax, plot_dict["plotter_x_axis"])
        if subdir_name:
            os.makedirs(os.path.join(plot_dict["result_directory"], "png_plots", subdir_name), exist_ok=True)
        plt.savefig(os.path.join(plot_dict["result_directory"], "png_plots", subdir_name, plot_name + ".png"), bbox_inches='tight', dpi=600, pad_inches=0)
        plt.close()
    # --- Plot with plotly ---
    if not plotly_enabled:
        return
    
    fig = go.Figure()
    trace_names = []
    trace_idx = 0  
    for col in result.columns:
        if plot_dict["plot_type"] == "bar":
                fig.add_trace(go.Bar(
                x=plot_dict["plotter_x_axis"],
                y=result[col],
                name=col,
                visible=(trace_idx == 0),
                hovertemplate=f"{col}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))
        else:
            fig.add_trace(go.Scatter(
                x=plot_dict["plotter_x_axis"], 
                y=result[col],
                mode="lines", 
                name=col,
                visible=(trace_idx == 0),
                line_shape='hv' if plot_dict["plot_type"] == "step" else 'linear' , 
                hovertemplate=f"{col} {plot_dict['ylabel']}: %{{y:.2f}} {plot_dict['unit']}<extra></extra>"
            ))
        trace_names.append(col)
        trace_idx += 1
    # --- Build dropdown ---
    buttons = []
    n_traces = len(trace_names)
    if n_traces>1:
        for i, col in enumerate(trace_names):
            visible = [False] * n_traces
            visible[i] = True

            buttons.append(
                dict(
                    label=col,
                    method="update",
                    args=[
                        {"visible": visible},
                        {"title": {"text": f"{plot_dict['title']}", "x":0.5}}
                    ]
                )
            )
    fig.update_layout(
        title={"text": f"{plot_dict['title']}", "x": 0.5},
        xaxis_title="Time",
        yaxis_title=plot_dict["ylabel"],
        hovermode="x unified",
        updatemenus=[dict(
            buttons=buttons,
            direction="down",
            x=0.01,
            y=1.15,
            showactive=True)] if n_traces > 1 else None 
    )
    base_dir = plot_dict["result_directory"]

    plotly_dir = os.path.join(base_dir, "plotly_plots")
    png_dir = os.path.join(base_dir, "png_plots")
    # If plotly is not enabled, we might need need to generate html plot for LMP
    if os.path.isdir(plotly_dir):
        base_save_dir = plotly_dir
    else:
        base_save_dir = png_dir

    if subdir_name:
        save_dir = os.path.join(base_save_dir, subdir_name)
    else:
        save_dir = base_save_dir

    os.makedirs(save_dir, exist_ok=True)
    fig.write_html(os.path.join(save_dir, f"{plot_name}.html"))

     

     