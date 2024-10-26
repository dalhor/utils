# ======================================================================
# File: TH_51_stress_memory_heatmap.py
# Role: Load a mutli-session CSV and generate a heatmap html file
# Is written with the results of stress_memory application in mind
# ======================================================================
# Context:
#       Showcases performances across multiple applications stressed by
#       multiple applications (each stressed has all stressors)
# Overview:
#       Given a multi-session CSV such as one generated by TH_40...py
#       computes mean_elongation and represent them as heatmap
#       for all stressed/stressor couples.
# Algo:
#       1/ load multi_session csv,
#       2/ compute new rows end-begin for each couple of begin and end rows
#       3/ filter out irrelant rows
#       4/ aggregate all measurements values across activation to compute mean
#       5/ Separate into ref_dataframe with only one App and dataframe with two apps
#       6/ Compute mean_elongation into dataframe thanks to ref_dataframe
#       7/ Pivot both dataframes into two-way tables
#       8/ Plot heatmap using plotly and both dataframes
# ======================================================================
# Command-line:
#       python TH_51_stress_memory_heatmap.py -i <csvfile> -o <pictures_folder>
#       python TH_51_stress_memory_heatmap.py -h
# ======================================================================
#
#

import sys, getopt
import os
import pandas as pd

import plotly.graph_objs as go
from plotly.subplots import make_subplots

import yaml
yaml_folder = "~/targets_info/"

HEATMAP_HTML_FNAME = "TH_51_heatmap.html"
TH_PROG_USAGE= "python TH_51_stress_memory_heatmap.py -i <JSON_results_folder> -o <pictures_folder>"

nano_to_milli = 0.000001

def command_print_usage():
    print(TH_PROG_USAGE)

def main_get_options(argv):
    is_valid_i=False
    is_valid_o=False
    is_valid_t=False
    JSON_results_folder = ''
    pictures_folder = ''
    target = -1
    try:
        opts, _ = getopt.getopt(argv,"hi:o:t:", ["ifolder", "ofolder", "target"])
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
        elif opt in ("-t", "--target"):
            target = arg
            is_valid_t = True
    return is_valid_i and is_valid_o and is_valid_t, JSON_results_folder, pictures_folder, target

if __name__ == "__main__":
    # get cli arguments
    is_valid,poc_csv,pictures_folder,target = main_get_options(sys.argv[1:])

    if not is_valid:
        print("[ERROR] invalid command.\n")
        command_print_usage()
        exit()

    config = None
    with open(yaml_folder + str(target) + ".yml", 'r') as file:
        config = yaml.safe_load(file)

    # path to the directory of these python scripts
    THpy_dir_path = os.path.dirname(os.path.realpath(__file__))

    # read csv given from -i input argument
    csv_types = {
        "a_appli_name": "string",
        "b_appli_name": "string",
        "c_appli_name": "string",
        "d_appli_name": "string"
    }
    dataframe = pd.read_csv(poc_csv, dtype=csv_types)


    main_columns = ["core0AppElf", "core1AppElf", "core0AppId", "core1AppId", \
        "evt_id", "part_id", "is_begin_not_end", "measurement_value", "activation", "obs_point_name"]
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

    dataframe = dataframe[(dataframe["evt_id"] == "ticks") & (dataframe["part_id"]==3)] 

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
    dataframe = dataframe[(dataframe["is_begin_not_end"] == "end-begin") & (dataframe["evt_id"] == "ticks") & (dataframe["obs_point_name"] == "PERPRO_TIMWIN_0") & (dataframe["limiter_cores_checked"] == 0)]
    # Remove column that bring no extra information
    dataframe = dataframe.drop(columns=["is_begin_not_end", "evt_id", "obs_point_name", "limiter_cores_checked"])

    columns = list(dataframe.columns)
    index_columns = [col for col in columns if col not in ["activation", "measurement_value"]]
    # Make summarising stats (mean) for different activation of otherwise same column values
    dataframe = dataframe.groupby(index_columns, dropna=False) \
                .agg(mean_value=("measurement_value", "mean")) \
                .reset_index() # Original columns were squished by groupby so reset_index unsquishes them

    dataframe["mean_value"] = dataframe["mean_value"] * nano_to_milli * config["ticker_period"]

    # Separate dataframe into ref_dataframe with only core0 active and dataframe with both core actives
    ref_dataframe = dataframe[dataframe["core1AppId"] == 0]
    dataframe = dataframe[dataframe["core1AppId"] != 0]

    # Merge the two dataframes to have column of ref value for each case of both core actives, to compute mean_elongation
    columns = list(dataframe.columns)
    index_columns = [col for col in columns if col not in ["core1AppId", "core1AppElfId", "mean_value"]]
    dataframe = dataframe.merge(ref_dataframe, on=index_columns, how='left', suffixes=("", "_ref"))
    dataframe["mean_elongation"] = dataframe["mean_value"] / dataframe["mean_value_ref"]


    # Make the heatmap plot now

    # Turn each dataframe into a two-way table of mean-value or mean_elongation across core0AppElfId/core1AppElfId (matching the heatmap data)
    ref_dataframe = ref_dataframe.pivot(index=["core0AppElfId"], 
                columns=["core1AppElfId"], values="mean_value")
    # Here no need for reset_index as we don't want to go back to a one-way table

    dataframe = dataframe.pivot(index=["core0AppElfId"],
                columns=["core1AppElfId"], values="mean_elongation")

    dataframe.to_csv(pictures_folder + '/' + "heatmap.csv")
    ref_dataframe.to_csv(pictures_folder + '/' + "ref_heatmap.csv")

    # figure is made of two subplots left to right, which share the same axes
    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.3, 0.7],
        shared_xaxes=True,
        shared_yaxes=True
    )

    # left subplot is a heatmap with no x axis (no core1AppElfId)
    ref_heatmap = go.Heatmap(
        z=ref_dataframe.values,
        colorscale="Blues",
        x=[" "],
        y=ref_dataframe.index,
        zmin=0,
        zmax=21,
        texttemplate="%{z}ms",
        showscale=False)
    
    fig.add_trace(ref_heatmap, row=1, col=1)

    # right subplot is a heatmap of mean_elongation
    heatmap = go.Heatmap(
        z=dataframe.values,
        x=dataframe.columns,
        y=dataframe.index,
        zmin=1,
        zmax=5,
        texttemplate="x %{z}",
        colorscale = [(0, "forestgreen"), (0.085, "yellowgreen"), (0.28, "gold"), (0.6, "tomato"), (0.8, "red"), (1, "darkred")]
    )

    fig.add_trace(heatmap, row=1, col=2)

    fig.update_layout(
        yaxis_autorange="reversed",
        title=dict(
            text="App exec time increase factor (horizontal)<br>when stressed (by vertical app hosted on a secondary core)",
            x=0.5,
            y=0.95,
            xanchor='center',
            yanchor='top')
        )

    fig.update_yaxes(automargin=True)
    fig.update_xaxes(side="bottom")

    # save figure as html file
    fig.write_html(pictures_folder + '/' + HEATMAP_HTML_FNAME)
