# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:hydrogen
#     text_representation:
#       extension: .py
#       format_name: hydrogen
#       format_version: '1.2'
#       jupytext_version: 1.1.1
#   kernelspec:
#     display_name: thoth-notebooks
#     language: python
#     name: thoth-notebooks
# ---

# %% [markdown] {"toc": true}
# <h1>Table of Contents<span class="tocSkip"></span></h1>
# <div class="toc"><ul class="toc-item"><li><span><a href="#Retrieve-inspection-jobs-from-Ceph" data-toc-modified-id="Retrieve-inspection-jobs-from-Ceph-1"><span class="toc-item-num">1&nbsp;&nbsp;</span>Retrieve inspection jobs from Ceph</a></span></li><li><span><a href="#Describe-the-structure-of-an-inspection-job-result" data-toc-modified-id="Describe-the-structure-of-an-inspection-job-result-2"><span class="toc-item-num">2&nbsp;&nbsp;</span>Describe the structure of an inspection job result</a></span></li><li><span><a href="#Mapping-InspectionRun-JSON-to-pandas-DataFrame" data-toc-modified-id="Mapping-InspectionRun-JSON-to-pandas-DataFrame-3"><span class="toc-item-num">3&nbsp;&nbsp;</span>Mapping InspectionRun JSON to pandas DataFrame</a></span><ul class="toc-item"><li><span><a href="#Feature-importance-analysis" data-toc-modified-id="Feature-importance-analysis-3.1"><span class="toc-item-num">3.1&nbsp;&nbsp;</span>Feature importance analysis</a></span><ul class="toc-item"><li><span><a href="#Status" data-toc-modified-id="Status-3.1.1"><span class="toc-item-num">3.1.1&nbsp;&nbsp;</span>Status</a></span></li><li><span><a href="#Specification" data-toc-modified-id="Specification-3.1.2"><span class="toc-item-num">3.1.2&nbsp;&nbsp;</span>Specification</a></span></li><li><span><a href="#Job-log" data-toc-modified-id="Job-log-3.1.3"><span class="toc-item-num">3.1.3&nbsp;&nbsp;</span>Job log</a></span></li></ul></li></ul></li><li><span><a href="#Profile-InspectionRun-duration" data-toc-modified-id="Profile-InspectionRun-duration-4"><span class="toc-item-num">4&nbsp;&nbsp;</span>Profile InspectionRun duration</a></span></li><li><span><a href="#Plot-InspectionRun-duration" data-toc-modified-id="Plot-InspectionRun-duration-5"><span class="toc-item-num">5&nbsp;&nbsp;</span>Plot InspectionRun duration</a></span></li><li><span><a href="#Library-usage" data-toc-modified-id="Library-usage-6"><span class="toc-item-num">6&nbsp;&nbsp;</span>Library usage</a></span></li><li><span><a href="#Grouping-and-filtering" data-toc-modified-id="Grouping-and-filtering-7"><span class="toc-item-num">7&nbsp;&nbsp;</span>Grouping and filtering</a></span><ul class="toc-item"><li><span><a href="#Grouping-based-on-hardware-platform" data-toc-modified-id="Grouping-based-on-hardware-platform-7.1"><span class="toc-item-num">7.1&nbsp;&nbsp;</span>Grouping based on hardware platform</a></span></li><li><span><a href="#Grouping-based-on-exit-status" data-toc-modified-id="Grouping-based-on-exit-status-7.2"><span class="toc-item-num">7.2&nbsp;&nbsp;</span>Grouping based on exit status</a></span></li><li><span><a href="#Creation-of-duration-dataframe-from-filtered-inspection-results" data-toc-modified-id="Creation-of-duration-dataframe-from-filtered-inspection-results-7.3"><span class="toc-item-num">7.3&nbsp;&nbsp;</span>Creation of duration dataframe from filtered inspection results</a></span></li></ul></li><li><span><a href="#Visualizing-grouped-data" data-toc-modified-id="Visualizing-grouped-data-8"><span class="toc-item-num">8&nbsp;&nbsp;</span>Visualizing grouped data</a></span></li></ul></div>
# %% [markdown]
# # Amun InspectionRun Analysis
# %% [markdown]
# **Introduction**
#
# The goal of this notebook is to show the behaviour of micro-benchmarks tested on the selected software/hardware architecture. This notebook will evaluate the feasibility and accuracy of the tests in order to prove or discard the possibility of running micro-benchmarks tests for ML applications. 
#
# The analysis consider ~300 inspection jobs obtained considering:
#
# - same libraries
# - same versions
# - same environment
# - same micro-benchmark for performance test

# %% [markdown]
# ---
# %%
import logging
import functools
import re

import textwrap
import typing

from typing import Any, Dict, List, Tuple, Union
from typing import Callable, Iterable

from collections import namedtuple

logger = logging.getLogger()

# %% {"require": ["notebook/js/codecell"]}
import pandas as pd
import numpy as np

from pandas_profiling import ProfileReport as profile
from pandas.io.json import json_normalize

from thoth.storages import InspectionResultsStore

# %%
import cufflinks as cf
import plotly
import plotly.offline as py

from plotly import graph_objs as go
from plotly import figure_factory as ff
from plotly import tools

from plotly.offline import iplot, init_notebook_mode

# plotly
init_notebook_mode()

# cufflinks
cf.go_offline()

# %% [markdown]
# ---

# %% [markdown]
# ## Retrieve inspection jobs from Ceph

# %%
%env THOTH_DEPLOYMENT_NAME     thoth-core-upshift-stage
%env THOTH_CEPH_BUCKET         thoth
%env THOTH_CEPH_BUCKET_PREFIX  data/thoth
%env THOTH_S3_ENDPOINT_URL     https://s3.upshift.redhat.com/

# %%
inspection_store = InspectionResultsStore(region='eu-central-1')
inspection_store.connect()

# %% [markdown]
# ---
# %% [markdown] {"heading_collapsed": true}
# ## Describe the structure of an inspection job result

# %% {"hidden": true}
pd.set_option('max_colwidth', 800)


# %% {"hidden": true}
def extract_structure_json(input_json, upper_key: str, level: int, json_structure):
    """Convert a json file structure into a list with rows showing tree depths, keys and values"""
    level += 1
    for key in input_json.keys():
        if type(input_json[key]) is dict:
            json_structure.append([level, upper_key, key, [k for k in input_json[key].keys()]])
            
            extract_structure_json(input_json[key], f"{upper_key}__{key}", level, json_structure)
        else:
            json_structure.append([level, upper_key, key, input_json[key]])
            
    return json_structure

def filter_dfs(df_s, filter_df):
    """Filter the specific dataframe created for a certain key, combination of keys or for a tree depth"""
    if type(filter_df) is str:
        available_keys = set(df_s["Current_key"].values)
        available_combined_keys = set(df_s["Upper_keys"].values)
        
        if filter_df in available_keys:
            ndf = df_s[df_s["Current_key"].str.contains(f"^{filter_df}$", regex=True)]
            
        elif filter_df in available_combined_keys:
            ndf = df_s[df_s["Upper_keys"].str.contains(f"{filter_df}$", regex=True)]
        else:
            print("The key is not in the json")
            ndf = "". join([f"The available keys are (WARNING: Some of the keys have no leafs):{available_keys} ", f"The available combined keys are: {available_combined_keys}"])
    elif type(filter_df) is int:
        max_depth = df_s["Tree_depth"].max()
        if filter_df <= max_depth:
            ndf = df_s[df_s["Tree_depth"] == filter_df]
        else:
            ndf = f"The maximum tree depth available is: {max_depth}"
    return ndf


# %% [markdown] {"hidden": true}
# We can take a look at the inspection job structure from the point of view of the tree depth, considering a key or a combination of keys in order to understand the common inputs for all inspections.

# %% {"hidden": true}
df_structure = pd.DataFrame(extract_structure_json(doc, "", 0, []))
df_structure.columns = ["Tree_depth", "Upper_keys", "Current_key", "Value"]

# %% [markdown] {"hidden": true}
# Check the structure of an inspection job

# %% {"hidden": true}
df_structure

# %% [markdown] {"hidden": true}
# Check memory requested for build and run.

# %% {"hidden": true}
filter_dfs(df_structure, "memory")

# %% [markdown] {"hidden": true}
# Check hardware requested for build and run.

# %% {"hidden": true}
filter_dfs(df_structure, "__specification__build__requests__hardware")

# %% {"hidden": true}
filter_dfs(df_structure, "__specification__run__requests__hardware")

# %% [markdown] {"hidden": true}
# Verify hardware info

# %% {"hidden": true}
filter_dfs(df_structure, "__job_log__hwinfo")

# %% [markdown] {"hidden": true}
# Check CPU information

# %% {"hidden": true}
filter_dfs(df_structure, "__job_log__hwinfo__cpu")

# %% [markdown] {"hidden": true}
# Check Platform information

# %% {"hidden": true}
filter_dfs(df_structure, "__job_log__hwinfo__platform")

# %% [markdown] {"hidden": true}
# Check source of libraries

# %% {"hidden": true}
filter_dfs(df_structure, "__specification__python__requirements_locked___meta")

# %% [markdown] {"hidden": true}
# Check which libraries are used.

# %% {"hidden": true}
for package in filter_dfs(df_structure, "__specification__python__requirements_locked__default")["Current_key"].values:
    dfp = filter_dfs(df_structure, f"__specification__python__requirements_locked__default__{package}")
    print("{:15}  {}".format(package, dfp[dfp["Current_key"].str.contains("version")]["Value"].values[0]))

# %% [markdown] {"hidden": true}
# Check OS used

# %% {"hidden": true}
filter_dfs(df_structure, "base")

# %% [markdown] {"hidden": true}
# Check the micro-benchmark used

# %% {"hidden": true}
filter_dfs(df_structure, "script")

# %% [markdown] {"hidden": true}
# ---
# %% [markdown]
# ## Mapping InspectionRun JSON to pandas DataFrame

# %%
inspection_results = []

for document_id, document in inspection_store.iterate_results():
    # pop build logs to save some memory (not necessary for now)
    document['build_log'] = None
    
    inspection_results.append(document)

# %% [markdown]
# ### Feature importance analysis
#
# For the purposes of the performance analysis we take under consideration the impact of a variable on the performance score, the variance of the features is therefore an important indicator. We can assume that the more variance feature evinces, the higher is its impact on the performance measure stability.
#
# We can perform profiling as the first stage of this analysis to identify constants which won't affect the prediction.

# %%
f"The original DataFrame contains  {len(df.columns)}  columns"

# %% [markdown]
# These are the top-level keys:

# %%
inspection_results[0].keys()

# %% [markdown]
# #### Status

# %% {"require": ["base/js/events", "datatables.net", "d3", "jupyter-datatables"]}
df_status = df.filter(regex='status')

date_columns = df_status.filter(regex="started_at|finished_at").columns
for col in date_columns:
    df_status[col] = df[col].apply(pd.to_datetime)

# %%
p = profile(df_status)
p

# %% [markdown]
# According to the profiling, we can drop the values with the constant value:

# %%
rejected = p.description_set['variables'].query("distinct_count <= 1 & type != 'UNSUPPORTED'")
rejected

# %%
df.drop(rejected.index, axis=1, inplace=True)

# %% [markdown]
# #### Specification

# %%
df_spec = df.filter(regex='specification')

# %%
p = profile(df_spec)
p

# %%
rejected = p.description_set['variables'].query("distinct_count <= 1 & type != 'UNSUPPORTED'")
rejected

# %% [markdown]
# exclude versions, we might wanna use them later on

# %%
rejected = rejected.filter(regex="^((?!version).)*$", axis=0)
rejected

# %%
df.drop(rejected.index, axis=1, inplace=True)

# %% [markdown]
# #### Job log

# %%
df_job = df.filter(regex='job_log')

# %%
p = profile(df_job)
p

# %%
rejected = p.description_set['variables'].query("distinct_count <= 1 & type != 'UNSUPPORTED'")
rejected

# %%
df.drop(rejected.index, axis=1, inplace=True)


# %% [markdown]
# ---

# %%
def process_inspection_results(
    inspection_results: List[dict],
    exclude: Union[list, set] = None,
    apply: List[Tuple] = None,
    drop: bool = True,
    verbose: bool = False
) -> pd.DataFrame:
    """Process inspection result into pd.DataFrame."""
    if not inspection_results:
        return ValueError("Empty iterable provided.")
    
    exclude = exclude or []
    apply = apply or ()
    
    df = json_normalize(inspection_results, sep = "__")  # each row resembles InspectionResult
    
    if len(df) <= 1:
        return df
    
    for regex, func in apply:
        for col in df.filter(regex=regex).columns:
            df[col] = df[col].apply(func)
    
    keys = [k for k in inspection_results[0] if not k in exclude]
    for k in keys:
        if k in exclude:
            continue
        d = df.filter(regex=k)
        p = profile(d)
        
        rejected = p.description_set['variables'] \
            .query("distinct_count <= 1 & type != 'UNSUPPORTED'") \
            .filter(regex="^((?!version).)*$", axis=0)  # explicitly include versions
        
        if verbose:
            print("Rejected columns: ", rejected.index)
        
        if drop:
            df.drop(rejected.index, axis=1, inplace=True)
        
    df = df \
        .eval("status__job__duration   = status__job__finished_at   - status__job__started_at", engine='python') \
        .eval("status__build__duration = status__build__finished_at - status__build__started_at", engine='python')
        
    return df

# %%
df = process_inspection_results(
    inspection_results,
    exclude=['build_log', 'created', 'inspection_id'],
    apply=[
        ("created|started_at|finished_at", pd.to_datetime)
    ]
)

# %% [markdown]
# ---
# %% [markdown]
# ## Profile InspectionRun duration

# %%
df_duration = df.filter(like='duration') \
    .rename(columns=lambda s: s.replace("status__", "").replace("__", "_")) \
    .apply(lambda ts: pd.to_timedelta(ts).dt.total_seconds())

# %%
p = profile(df_duration)
p

# %%
stats = p.description_set['variables'].drop(["histogram", "mini_histogram"], axis=1)
stats

# %% [markdown]
# ## Plot InspectionRun duration

# %% [markdown]
# Make sure that the versions are constant

# %%
df.filter(regex='python.*version').drop_duplicates()

# %% [markdown]
# Visualize statistics

# %%
fig = df_duration.iplot(
    kind='box',
    title="InspectionRun duration",
    yTitle="duration [s]",
    asFigure=True,
)

# %%
df_duration \
    .iplot(
    fill='tonexty',
    kind='scatter',
    title="InspectionRun duration",
    yTitle="duration [s]"
)

# %%
df_duration = df_duration \
    .eval("job_duration_mean           = job_duration.mean()", engine='python') \
    .eval("build_duration_mean         = build_duration.mean()", engine='python') \
    .eval("job_duration_upper_bound    = job_duration + job_duration.std()", engine='python') \
    .eval("job_duration_lower_bound    = job_duration - job_duration.std()", engine='python') \
    .eval("build_duration_upper_bound  = build_duration + build_duration.std()", engine='python') \
    .eval("build_duration_lower_bound  = build_duration - build_duration.std()", engine='python')

upper_bound = go.Scatter(
    name='Upper Bound',
    x=df_duration.index,
    y=df_duration.job_duration_upper_bound,
    mode='lines',
    marker=dict(color="lightgray"),
    line=dict(width=0),
    fillcolor='rgba(68, 68, 68, 0.3)',
    fill='tonexty' )

trace = go.Scatter(
    name='Duration',
    x=df_duration.index,
    y=df_duration.job_duration,
    mode='lines',
    line=dict(color='rgb(31, 119, 180)'),
    fillcolor='rgba(68, 68, 68, 0.3)',
    fill='tonexty' )

lower_bound = go.Scatter(
    name='Lower Bound',
    x=df_duration.index,
    y=df_duration.job_duration_lower_bound,
    marker=dict(color="lightgray"),
    line=dict(width=0),
    mode='lines')

data = [lower_bound, trace, upper_bound]

m = stats.loc['job_duration']['mean']
layout = go.Layout(
    yaxis=dict(title='duration [s]'),
    shapes=[
        {
            'type': 'line',
            'x0': 0,
            'x1': len(df_duration.index),
            'y0': m,
            'y1': m,
            'line': {
                'color': 'red',
                'dash': 'longdash'
            }
        }
    ],
    title='InspectionRun job duration',
    showlegend = False)

fig = go.Figure(data=data, layout=layout)

iplot(fig, filename='pandas-time-series-error-bars')

# %%
bins = np.lib.histograms._hist_bin_auto(df_duration.job_duration.values, None)

df_duration.job_duration.iplot(
    title="InspectionRun job distribution",
    xTitle="duration [s]",
    yTitle="count",
    kind='hist',
    bins=int(np.ceil(bins))
)

# %% [markdown]
# ---
# %% [markdown]
# ## Library usage


# %% {"code_folding": [8, 47, 58, 67, 134]}
# -*- coding: utf-8 -*-

"""Thoth InspectionRun dashboard app."""

pd.set_option('precision', 4)
pd.set_option('colheader_justify', 'center')


def create_duration_dataframe(inspection_df: pd.DataFrame):
    """Compute statistics and duration DataFrame."""
    if len(inspection_df) <= 0:
        raise ValueError("Empty DataFrame provided")

    try:
        inspection_df.drop("build_log", axis=1, inplace=True)
    except KeyError:
        pass

    data = (
        inspection_df
        .filter(like="duration")
        .rename(columns=lambda s: s.replace("status__", "").replace("__", "_"))
        .apply(lambda ts: pd.to_timedelta(ts).dt.total_seconds())
    )
    
    def compute_duration_stats(group):
        return (
            group
            .eval("job_duration_mean           = job_duration.mean()", engine="python")
            .eval("job_duration_upper_bound    = job_duration + job_duration.std()", engine="python")
            .eval("job_duration_lower_bound    = job_duration - job_duration.std()", engine="python")
            .eval("build_duration_mean         = build_duration.mean()", engine="python")
            .eval("build_duration_upper_bound  = build_duration + build_duration.std()", engine="python")
            .eval("build_duration_lower_bound  = build_duration - build_duration.std()", engine="python")
        )
    
    if isinstance(inspection_df.index, pd.MultiIndex):
        n_levels = len(inspection_df.index.levels)

        # compute duration stats for each group separately
        data = data.groupby(level=list(range(n_levels - 1)), sort=False).apply(compute_duration_stats)
    else:
        data = compute_duration_stats(data)
    
    return data.round(4)


def create_duration_box(data: pd.DataFrame, columns: Union[str, List[str]] = None, **kwargs):
    """Create duration Box plot."""
    columns = columns if columns is not None else data.filter(regex="duration$").columns
    
    figure = data[columns].iplot(
        kind="box", title=kwargs.pop("title", "InspectionRun duration"), yTitle="duration [s]", asFigure=True
    )
    
    return figure


def create_duration_scatter(data: pd.DataFrame, columns: Union[str, List[str]] = None, **kwargs):
    columns = columns if columns is not None else data.filter(regex="duration$").columns
    
    figure = data[columns].iplot(
        kind="scatter", title=kwargs.pop("title", "InspectionRun duration"), yTitle="duration [s]", asFigure=True
    )
    
    return figure


def create_duration_scatter_with_bounds(data: pd.DataFrame, col: str, index: Union[list, pd.Index, pd.RangeIndex] = None, **kwargs):
    """Create duration Scatter plot."""
    df_duration = (
        data[[col]]
        .eval(f"upper_bound = {col} + {col}.std()", engine="python")
        .eval(f"lower_bound = {col} - {col}.std()", engine="python")
    )
    
    index = index if index is not None else df_duration.index
    
    if isinstance(index, pd.MultiIndex):
        index = index.levels[-1] if len(index.levels[-1]) == len(df) else np.arange(len(df))

    upper_bound = go.Scatter(
        name="Upper Bound",
        x=index,
        y=df_duration.upper_bound,
        mode="lines",
        marker=dict(color="lightgray"),
        line=dict(width=0),
        fillcolor="rgba(68, 68, 68, 0.3)",
        fill="tonexty",
    )

    trace = go.Scatter(
        name="Duration",
        x=index,
        y=df_duration[col],
        mode="lines",
        line=dict(color="rgb(31, 119, 180)"),
        fillcolor="rgba(68, 68, 68, 0.3)",
        fill="tonexty",
    )

    lower_bound = go.Scatter(
        name="Lower Bound",
        x=index,
        y=df_duration.lower_bound,
        marker=dict(color="lightgray"),
        line=dict(width=0),
        mode="lines",
    )

    data = [lower_bound, trace, upper_bound]
    m = df_duration[col].mean()

    layout = go.Layout(
        yaxis=dict(title="duration [s]"),
        shapes=[
            {
                "type": "line",
                "x0": 0,
                "x1": len(index),
                "y0": m,
                "y1": m,
                "line": {"color": "red", "dash": "longdash"},
            }
        ],
        title=kwargs.pop("title", "InspectionRun duration"),
        showlegend=False,
    )

    fig = go.Figure(data=data, layout=layout)

    return fig


def create_duration_histogram(data: pd.DataFrame, columns: Union[str, List[str]] = None, bins: int = None, **kwargs):
    """Create duration histogram."""
    columns = columns if columns is not None else data.filter(regex="duration$").columns

    if not bins:
        bins = np.max([np.lib.histograms._hist_bin_auto(data[col].values, None) for col in columns])

    figure = data[columns].iplot(
        title=kwargs.pop("title", "InspectionRun distribution"),
        yTitle="count",
        kind="hist",
        bins=int(np.ceil(bins)),
        asFigure=True,
    )

    return figure


# %%
df = process_inspection_results(
    inspection_results,
    exclude=['build_log', 'created', 'inspection_id'],
    apply=[
        ("created|started_at|finished_at", pd.to_datetime)
    ]
)

# %%
df_duration = create_duration_dataframe(df)

# %%
fig = create_duration_box(df_duration, ['build_duration', 'job_duration'])

py.iplot(fig)

# %%
fig = create_duration_scatter(df_duration, 'job_duration', title="InspectionRun job duration")

py.iplot(fig)

# %%
fig = create_duration_scatter(df_duration, 'build_duration', title="InspectionRun build duration")

py.iplot(fig)

# %%
fig = create_duration_histogram(df_duration, ['job_duration'])

py.iplot(fig)


# %% [markdown]
# ## Grouping and filtering
#
# [Trello](https://trello.com/c/7IiBLufs/560-grouping-of-inspection-job-results-based-on-given-criteria-nokr)
#
# The goal of this part is to have a function which divides inspection jobs into “categories”, the function accepts loaded inspection JSON files and a key which should be used to split input inspection documents.

# %% {"code_folding": [0]}
def _resolve_query(query: str, context: pd.DataFrame = None, resolvers: tuple = None, engine:str = None, parser: str = "pandas"):
    """Resolve query in the given context."""
    import re
    from pandas.core.computation.expr import Expr
    from pandas.core.computation.eval import _ensure_scope
    
    if not query:
        return context
    
    q = query
    q = re.sub(r"\[\(", "", q)
    q = re.sub(r"\b(\d)+\b", "", q)
    q = re.sub(r"[+\-\*:!<>=~.|&%]", " ", q)
    
    # get our (possibly passed-in) scope
    resolvers = resolvers or ()
    if isinstance(context, pd.DataFrame):
        index_resolvers = context._get_index_resolvers()
        resolvers = tuple(resolvers) + (dict(context.iteritems()), index_resolvers)
    
    repl = []
    for idx, resolver in enumerate(resolvers):
        keys = resolver.keys()
        
        for op in set(q.split()):
            matches = [(op, k) for k in keys if re.search(op, k)]

            if len(matches) == 1:
                op, key = matches[0]
                repl.append((idx, op, resolver[key]))
                
            elif len(matches) > 1:
                raise KeyError(f"Ambiguous query operand provided: `{op}`")
    
    for idx, op, val in repl:
        resolvers[idx][op] = val
    
    env = _ensure_scope(level=1, resolvers=resolvers, target=context)
    expr = Expr(query, engine=engine, parser=parser, env=env)
    
    def _resolve_operands(operands) -> list:
        for op in operands:
            # complex query
            if op.is_scalar:
                continue
                
            if hasattr(op, 'operands'):
                yield from _resolve_operands(op.operands)
                
            yield str(op)
            
    operands = set(_resolve_operands(expr.terms.operands))
    
    for op in operands:
        try:
            query = query.replace(op, env.resolvers[op].name)
        except KeyError:
            pass

    return context.query(query)


# %% {"code_folding": [0]}
def group_inspection_dataframe(inspection_df: pd.DataFrame, groupby: Union[str, list, set] = None, exclude: Union[str, list, set] = None):
    """"""
    import re
    
    groupby = groupby or []
    exclude = exclude or []
    
    if isinstance(groupby, str):
        groupby = [groupby]

    if isinstance(exclude, str):
        exclude = [exclude]

    groups = []

    for key in groupby:
        columns_idx = inspection_df.columns.str.contains(key)
        columns = inspection_df.columns[columns_idx]

        if not len(columns):
            raise KeyError(f"Could NOT find suitable column given the keys: `{groupby}`")

        groups.extend(columns)

    index_groups = []

    for col in inspection_df[groups].columns:
        # check that the column name is not excluded
        if any(re.search(e, col) for e in exclude):
            continue

        try:
            # check that grouping is possible
            inspection_df.groupby(col).indices

            index_groups.append(col)
        except TypeError:
            logger.warning(f"Column '{col}' dtype NOT understood. Dropped.")

    index_groups = pd.Series(index_groups).unique().tolist()

    # construct multi-index if grouping is requested
    indices = inspection_df.groupby(index_groups).indices

    levels = []
    for level, values in indices.items():
        if isinstance(level, tuple):
            levels.extend([(*level, v) for v in values])
        else:
            levels.extend([(level, v) for v in values])

    index = pd.MultiIndex.from_tuples(levels, names=[*index_groups, None])

    return (
        inspection_df
        .set_index(index)
        .drop(index_groups, axis=1)
        .sort_index(level=-1)
    )


# %% {"code_folding": [0]}
def filter_inspection_dataframe(inspection_df: pd.DataFrame, like: str = None, regex: str = None, axis: int = None):
    """"""
    if not any([like, regex]):
        return inspection_df

    filtered_df = inspection_df.filter(like=like, regex=regex, axis=axis)

    if not any(filtered_df.columns.str.contains("duration")):
        # duration columns must be present
        filtered_df = filtered_df.join(inspection_df.filter(like="duration"))

    inspection_df = filtered_df
        
    return inspection_df


# %% {"code_folding": [0, 11]}
def query_inspection_dataframe(
    inspection_df: List[dict],
    *,
    query: str = None,
    groupby: Union[str, list, set] = None,
    exclude: Union[str, list, set] = None,
    like: str = None,
    regex: str = None,
    axis: int = None,
    sort_index: Union[bool, int, List[int]] = True,
    engine: str = None
) -> pd.DataFrame:
    """Query inspection DataFrame.
    
    The order of operations is as follows:
    
        query resolution -> grouping -> filtering
    
    :param inspection_df: inspection DataFrame to be filtered as returned by `process_inspection_results`
    :param groupby: column or list of columns to group the DataFrame by
    :param exclude: patterns that should be excluded from grouping
    :param query: pandas query to be evaluated on the filtered DataFrame
    :param like, regex, axis: parameters passed to the `pd.DataFrame.filter` function
    :param engine: engine to evaluate the query passed to `where` parameter, see `pd.eval` for more information
        
        The string provided does NOT need to match the whole column name, the function tries to determine
        the most suitable column name automatically.
        
    :param **groupby_kwargs: additional parameters passed to the `pd.DataFrame.groupby` function
    """
    # resolve query
    inspection_df = _resolve_query(query=query, context=inspection_df)
     
    if groupby:
        inspection_df = group_inspection_dataframe(inspection_df, groupby=groupby, exclude=exclude)
        
    # filter
    df = filter_inspection_dataframe(inspection_df, like=like, regex=regex, axis=axis)
    
    if sort_index:
        if isinstance(sort_index, bool):
            levels = np.arange(df.index.nlevels -1).tolist()
        else:
            levels = sort_index
            
        return df.sort_index(level=levels)

# %%
df = process_inspection_results(
    inspection_results,
    exclude=['build_log', 'created', 'inspection_id'],
    apply=[
        ("created|started_at|finished_at", pd.to_datetime)
    ],
    drop=False
)

# %% [markdown]
# ### Grouping based on hardware platform

# %%
query_inspection_dataframe(df, groupby="platform", exclude="node")

# %% [markdown]
# It is also possible to group by multiple columns

# %%
query_inspection_dataframe(df, groupby=["ncpus", "platform"], exclude="node")

# %% [markdown]
# And finally if we are only interested in certain columns, we can filter them as well

# %%
query_inspection_dataframe(df, groupby=["platform", "ncpus"], like="duration", exclude="node")

# %% [markdown]
# Full-fledged filtering example can also filter based on the values

# %%
query_inspection_dataframe(df, query="ncpus == 32", groupby=["platform", "ncpus"], like="duration", exclude="node")

# %% [markdown]
# ### Grouping based on exit status

# %%
query_inspection_dataframe(df, like="job", groupby=["reason", "exit_code"], exclude="build")

# %% [markdown]
# ### Creation of duration dataframe from filtered inspection results

# %% [markdown]
# Creating the duration dataframe works as expected, by computing statistics for each group separately

# %%
filtered_df = query_inspection_dataframe(
    df,
    groupby=["platform", "ncpus"],
    like="duration",
    query="ncpus == 32 | ncpus == 64",
    exclude=["node", "platform__version"]
)

df_duration = create_duration_dataframe(filtered_df)
df_duration.head()


# %% [markdown]
# ## Visualizing grouped data

# %% {"code_folding": [0, 25, 43]}
def get_column_group(df: pd.DataFrame, columns: Union[List[Union[str, int]], pd.Index] = None, label: str = None) -> pd.DataFrame:
    """"""
    columns = columns or df.columns
    
    if all(isinstance(c, int) for c in columns):
        columns = [df.columns[i] for i in columns]
    
    if not label:
        cols = [col.split('_') for col in columns]
        
        common_words = set(functools.reduce(np.intersect1d, cols))
        if common_words:
            label = "_".join(w for w in cols[0] if w in common_words).strip('_')
        else:
            label = str(tuple(columns))
    
    Group = namedtuple("Group", columns)
    
    groups = []
    for i, row in df[columns].iterrows():
        groups.append(Group(*row))
    
    return pd.Series(groups, name=label)


def get_index_group(df: pd.DataFrame, names: List[Union[str, int]] = None, label: str = None) -> pd.Series:
    """"""
    names = names or list(filter(bool, df.index.names[:-1]))
    
    if all(isinstance(n, int) for n in names):
        names = [df.index.names[i] for i in names]
    
    index = df.index.to_frame(index=False)
    group = get_column_group(index[names])
    
    index = index.drop(columns=names)
    group_indices = pd.DataFrame(group).join(index).values.tolist()

    group_index = pd.MultiIndex.from_tuples(group_indices, names=[group.name, *index.columns[:-1], None])
    
    return group_index


def set_index_group(df: pd.DataFrame, names: List[Union[str, int]] = None, label: str = None) -> pd.DataFrame:
    """"""
    group_index = get_index_group(df, names, label)
    
    return df.set_index(group_index)


# %% [markdown]
# ---

# %% {"code_folding": [6]}
def make_subplots(
    data: pd.DataFrame,
    columns: List[str] = None,
    *,
    kind: str = 'box',
    **kwargs
):
    """"""
    if kind not in ('box', 'histogram', 'scatter', 'scatter_with_bounds'):
        raise ValueError(f"Can NOT handle plot of kind: {kind}.")

    index = data.index.droplevel(-1).unique()

    if len(index.names) > 2:
        logger.warning(
            f"Can only handle hierarchical index of depth <= 2, got {len(index.names)}. Grouping index.")

        return make_subplots(set_index_group(data, range(index.nlevels - 1)), columns, kind=kind, **kwargs)

    grid = ff.create_facet_grid(
        data.reset_index(),
        facet_row=index.names[1] if index.nlevels > 1 else None,
        facet_col=index.names[0],
        trace_type='box',  # box does not need data specification
        ggplot2=True
    )

    shape = np.shape(grid._grid_ref)[:-1]

    sub_plots = tools.make_subplots(
        rows=shape[0],
        cols=shape[1],
        shared_yaxes=True,
        shared_xaxes=False,
        print_grid=False,
    )

    if isinstance(index, pd.MultiIndex):
        index_grid = zip(*index.labels)
    else:
        index_grid = itertools.product(np.arange(shape[1]), repeat=2)
        
    for idx, grp in data.groupby(level=np.arange(index.nlevels).tolist()):
        if not isinstance(columns, str) and kind == 'scatter_with_bounds':
            if columns is None:
                raise ValueError(
                    "`scatter_with_bounds` requires `col` argument, not provided.")
            try:
                columns, = columns 
            except ValueError:
                raise ValueError(
                    "`scatter_with_bounds` does not allow for multiple columns.")

        fig = eval(f"create_duration_{kind}(grp, columns, **kwargs)")

        row, col = map(int, next(index_grid))
        for trace in fig.data:
            sub_plots.append_trace(trace, row + 1, col + 1)

    layout = sub_plots.layout
    layout.update(
        title=kwargs.get("title", fig.layout.title),
        shapes=grid.layout.shapes,
        annotations=grid.layout.annotations,
        showlegend=False
    )
    
    x_dom_vals = [k for k in layout.to_plotly_json().keys() if 'xaxis' in k]
    y_dom_vals = [k for k in layout.to_plotly_json().keys() if 'yaxis' in k]
    
    layout_shapes = pd.DataFrame(layout.to_plotly_json()['shapes']).sort_values(['x0', 'y0'])

    h_shapes = layout_shapes[~layout_shapes.x0.duplicated(keep=False)]
    v_shapes = layout_shapes[~layout_shapes.y0.duplicated(keep=False)][::-1]

    # update axis domains and layout
    for idx, x_axis in enumerate(x_dom_vals):
        x0, x1 = h_shapes.iloc[idx % shape[1]][['x0', 'x1']]
        
        layout[x_axis].domain = (x0 + 0.03, x1 - 0.03)
        layout[x_axis].update(showticklabels=False, zeroline=False)

    for idx, y_axis in enumerate(y_dom_vals):
        y0, y1 = v_shapes.iloc[idx % shape[0]][['y0', 'y1']]
        
        layout[y_axis].domain = (y0 + 0.03, y1 - 0.03)
        layout[y_axis].update(zeroline=False)
    
    for annot in layout.annotations:
        annot['text'] = re.sub(r"^(.{10}).*(.{10})$", "\g<1>...\g<2>", annot['text'])

    # custom user layout updates
    user_layout = kwargs.pop('layout', None)
    if user_layout:
        layout.update(user_layout)

    return sub_plots

# %%
d = query_inspection_dataframe(df, groupby=["platform", "ncpus"], exclude="node")
d = create_duration_dataframe(d)

display(d.head())

# fele free to try different values {box, histogram, scatter, scatter_with_bounds}
fig = make_subplots(data=d, kind='box')

py.iplot(fig)
