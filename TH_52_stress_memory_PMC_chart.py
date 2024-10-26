# ======================================================================
# File: TH_52_stress_memory_PMC_chart.py
# Role: Load a mutli-session CSV and generate a plotting table chart
# Is written with the results of stress_memory application in mind
# ======================================================================
# Context:
#       Showcases performances across multiple applications stressed by
#       multiple applications (each stressed has all stressors)
# Overview:
#       Given a multi-session CSV such as one generated by TH_40...py
#       computes mean_elongation and represent them as heatmap
#       for all stressed/stressor couples.
# ======================================================================
# Command-line:
#       python TH_52_stress_memory_PMC_chart.py -i <csvfile> -o <pictures_folder>
#       python TH_52_stress_memory_PMC_chart.py -h
# ======================================================================
#
#

import sys, getopt
import os
import pandas as pd

import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots

import plotly.io as pio
pio.renderers.default = "notebook"


CHART_HTML_FNAME = "TH_52_PMC_chart.html"
TH_PROG_USAGE= "python TH_52_stress_memory_PMC_chart.py -i <JSON_results_folder> -o <pictures_folder>"

nano_to_milli = 0.000001

def command_print_usage():
    print(TH_PROG_USAGE)

def main_get_options(argv):
    is_valid_i=False
    is_valid_o=False
    JSON_results_folder = ''
    pictures_folder = ''
    try:
        opts, _ = getopt.getopt(argv,"hi:o:t:", ["ifolder", "ofolder"])
    except getopt.GetoptError:
        command_print_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            command_print_usage()
            sys.exit()
        elif opt in ("-i", "--ifolder"):
            JSON_results_folder = arg
            is_valid_i=True
        elif opt in ("-o", "--ofile"):
            pictures_folder = arg
            is_valid_o=True
    return is_valid_i and is_valid_o, JSON_results_folder, pictures_folder

if __name__ == "__main__":
    # get cli arguments
    is_valid,poc_csv,pictures_folder = main_get_options(sys.argv[1:])

    if not is_valid:
        print("[ERROR] invalid command.\n")
        command_print_usage()
        exit()

    # path to the directory of these python scripts
    THpy_dir_path = os.path.dirname(os.path.realpath(__file__))

    # read csv given from -i input argument
    csv_types = {
        "a_appli_name": "string",
        "b_appli_name": "string",
        "c_appli_name": "string",
        "d_appli_name": "string"
    }
    dataframe = pd.read_csv(poc_csv, dtype=csv_types, engine='python')

    main_columns = ["core0AppElf", "core1AppElf", "core0AppId", "core1AppId", \
        "evt_id", "evt_type", "part_id", "is_begin_not_end", "measurement_value", "activation", "obs_point_name"]
    if (not all(col in dataframe.columns for col in main_columns)):
        print("[ERROR] csv does not have all columns necessary, main_columns:", main_columns, "dataframe columns: ", dataframe.columns)
        quit()
    extra_columns = [col for col in dataframe.columns if col not in main_columns]

    # remove columns with only NaN on all rows as they bring forward no data 
    # dataframe[extra_columns].dropna(axis=1, how="all", inplace=True)
    dataframe = dataframe[dataframe["measurement_value"] != -1]
    
    # make unique string value for each Application (core*AppId are not unique by default) 
    dataframe["core0AppElfId"] = dataframe["core0AppElf"] + "_" + dataframe["core0AppId"].astype(str)
    dataframe["core1AppElfId"] = dataframe["core1AppElf"] + "_" + dataframe["core1AppId"].astype(str)
    # core0AppElf and core1AppElf columns are redondant now
    dataframe = dataframe.drop(columns=["core0AppElf", "core1AppElf"])

    dataframe = dataframe.drop(columns="obs_point_id") # obs_point_id is redondant with evt_id and is_begin_not_end combined 

    dataframe = dataframe[(dataframe["evt_type"] == "core_PMC") & (dataframe["part_id"]==3)] 

    # Make is_begin_not_end column a list of columns to prepare for difference computing (unfitting column/row combination get value nan)
    columns = list(dataframe.columns)
    index_columns = [col for col in columns if col not in ["is_begin_not_end", "measurement_value"]]
    index_columns2 = index_columns[:]
    index_columns2.append("is_begin_not_end")
    dataframe_dupli = dataframe[dataframe.duplicated(subset=index_columns2, keep=False)]
    dataframe_dupli.to_csv(pictures_folder + "/dupli_results.csv")



    dataframe = dataframe.pivot(index=index_columns,  
                columns="is_begin_not_end", values="measurement_value") \
                .reset_index() # Original columns were squished inside the index so reset_index unsquishes them
                
    # Compute new column containing difference of end tick time and beg tick time 
    dataframe["end-begin"] = dataframe[0] - dataframe[1]

    # Remerge the is_begin_not_end inside a single column
    dataframe = dataframe.melt(id_vars=index_columns,
                value_name="measurement_value", var_name="is_begin_not_end") \
                .dropna(subset=["measurement_value"]) # Remove nan value from unfitting column/row combination of pivot
    
    # Filter for end-begin, ticks, PERPRO_TIMWIN_0, 0 limiter_cores_checked
    dataframe = dataframe[(dataframe["is_begin_not_end"] == "end-begin") & (dataframe["evt_type"] == "core_PMC") & (dataframe["obs_point_name"] == "PERPRO_TIMWIN_0") & (dataframe["limiter_cores_checked"] == 0)]
    # Remove column that bring no extra information
    dataframe = dataframe.drop(columns=["is_begin_not_end", "obs_point_name", "limiter_cores_checked", "ucName", "core2AppElf", "core3AppElf"])

    columns = list(dataframe.columns)
    index_columns = [col for col in columns if col not in ["activation", "measurement_value"]]
    # Make summarising stats (mean) for different activation of otherwise same column values
    dataframe = dataframe.groupby(index_columns, dropna=False) \
                .agg(mean_value=("measurement_value", "mean")) \
                .reset_index() # Original columns were squished by groupby so reset_index unsquishes them

    evt_names = dataframe['evt_name'].unique()

    # Create subplots
    fig = make_subplots(rows=len(evt_names), cols=1, shared_xaxes=False,  # Disable shared_xaxes to allow independent labels
                        subplot_titles=[f"Event: {evt}" for evt in evt_names])

    # Add each event in a different row
    for i, evt in enumerate(evt_names):
        df_event = dataframe[dataframe['evt_name'] == evt]
        
        # Add lines to the subplot with labels for each application
        fig.add_trace(
            go.Scatter(x=df_event['core0AppElfId'], y=df_event['mean_value'], 
                    mode='lines+markers+text',  # Adds text directly on the points
                    name=f"{evt}", 
                    hoverinfo='text+y',  # Displays the application label and the average value on hover
                    textposition="bottom center"  # Positions the text below the points
                    ),  
            row=i+1, col=1
        )

        # Update the axes for each subplot with custom labels
        fig.update_xaxes(title_text="Application", row=i+1, col=1)
        fig.update_yaxes(title_text="Average Evt Count", row=i+1, col=1, tickformat='.2f')

    # Global formatting of the chart
    fig.update_layout(
        height=500 * len(evt_names), 
        title_text="Comparison of values by application for each event",
        hovermode="x unified",  # Unifies the hover information
    )

    # Display all subplots on the same page
    fig.show()
    fig.write_html(pictures_folder + '/' + CHART_HTML_FNAME)