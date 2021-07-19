import time
import os
import argparse
import yaml
import wf_execute_sql

def filterByColumnExpression(columns_opts) -> str:
  expression = ''
  for column_opts in columns_opts:
    column_name = column_opts['name']
    column_value = column_opts['value']
    if (len(column_value) > 1):
      in_expr = ''
      for val in column_value:        
        in_expr += f"'{val}', "
      expression = f"{column_name} IN [{in_expr[-1]}]"
    else:
      expression = f"{column_name} = '{column_value}'"
  return expression

def filterByLabelExpression(label: str, label_column: str) -> str:
  if (label_column):
    return f"{label_column} = '{label}'"
  return f"""AND (custom_labels.label_0 = '{label}'
      OR custom_labels.label_1 = '{label}'
      OR custom_labels.label_2 = '{label}'
      OR custom_labels.label_3 = '{label}'
      OR custom_labels.label_4 = '{label}'
    )
    """

def execute_filter(cfg, context):
  macros = cfg['macros']
  name = 'filtering'
  filter_opts = cfg['filter']
  t0 = time.time()
  ts = time.strftime('%H:%M:%S %z')
  print(f'[{ts}] Starting "{name}" step')
  try:
    # standard filter (by availability):
    expression = "AND availability = 'in stock'"
    filter_by = filter_opts['filter-by']
    if (filter_by == 'label'):
      # filter by label
      expression = expression + " AND " + filterByLabelExpression(filter_opts['select-label'] or 'PDSA_Products', filter_opts['select-label-column'])
    elif (filter_by == 'column'):
      # filter by column
      expression = expression + " AND " + filterByColumnExpression(filter_opts['columns'])
    else:
      raise Exception('Unsupported filter mode: ' + filter_by)
    macros['filter_expression'] = expression
    macros['max_rows'] = filter_opts['max_rows'] or 100
    wf_execute_sql.run(cfg, context)
    # it should create a table {project_id}.{dataset}.Products_{merchant_id}_Filtered
  except:
    print(f'An error occured on "{name}" step')
    print(f'\tcontext dump: {context}')
    raise
  elapsed = time.time() - t0
  print(f'Finished "{name}" step, it took {elapsed} sec')
  context['stat'][name] = elapsed

def create_page_feed(cfg, context):
  macros = cfg['macros']
  name = 'create page feed'
  pagefeed_opts = cfg['page-feed']
  t0 = time.time()
  ts = time.strftime('%H:%M:%S %z')
  print(f'[{ts}] Starting "{name}" step')
  try:
    label_column = pagefeed_opts['label-column']
    macros['label-column'] = label_column
    macros['feedname'] = pagefeed_opts['feed-name']
    macros['custom_label_select'] = f"${label_column} AS Custom_label"
    # TODO:
    ## for one-to-one mapping
    # macros['custom_label_select'] = "CONCAT('product_', offer_id) AS Custom_label"
    ## for one-to-many mapping
    # macros['custom_label_select'] = "CONCAT('brand_', brand) as Custom_label"
    wf_execute_sql.run(cfg, context)
    # it should create a table {project_id}.{dataset}.product_page_feed_{merchant_id}_{feedname}
    context['xcom']['pagefeed-table'] = f"{macros['project_id']}.{macros['dataset']}.product_page_feed_{macros['merchant_id']}_{macros['feedname']}"
  except:
    print(f'An error occured on "{name}" step')
    print(f'\tcontext dump: {context}')
    raise
  elapsed = time.time() - t0
  print(f'Finished "{name}" step, it took {elapsed} sec')
  context['stat'][name] = elapsed

def generate_campaign_for_adeditor(context):
  pass

def get_config(args: argparse.Namespace):
  config_file_name = args.config or 'config.yaml'
  """ Read config.yml file and return Config object."""
  with open(config_file_name, "r") as config_file:
    cfg_dict = yaml.load(config_file, Loader=yaml.SafeLoader)
    return cfg_dict


def main():
  config = get_config('config.yaml')
  if not len(config['scenarios']):
    print('No scenarios are defined, exiting')
    exit()
  
  context = {'stat': {}, 'xcom': {}}
  for scenario in config['scenarios']:
    ts = time.strftime('%H:%M:%S %z')
    print(f'[{ts}] Starting processing {scenario["name"]}" scenario')
    mode = scenario['mode']
    filter_opts = scenario['filter']
    if (not filter_opts):
      # default filter
      filter_opts = {
        'filter-by': 'label',
        'select-label': 'PDSA_Products'
      }

    # filtering
    cfg = {
      'sql_file': 'scripts/filter-products.sql',
      'macros': {
        'project_id': config['project_id'],
        'dataset': 'gmcdsa',
        'merchant_id': config['merchant_id'],
      }
    }
    cfg['filter'] = filter_opts
    execute_filter(cfg, context)

    # creating page feed
    cfg = {
      'sql_file': 'scripts/create-page-feed.sql',
      'macros': {
        'project_id': config['project_id'],
        'dataset': 'gmcdsa',
        'merchant_id': config['merchant_id'],
      }
    }
    cfg['page-feed'] = scenario['page-feed']
    create_page_feed(cfg, context)

    # generating ad campaigns
    # TODO: fetch data from context['xcom']['pagefeed-table'] table and generate CSV with data for Ads Editor
    generate_campaign_for_adeditor(context)

    # TODO: support updating
    #   generate a CSV with data from pagefeed

if __name__ == '__main__':
  main()
